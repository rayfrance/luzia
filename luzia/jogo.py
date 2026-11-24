"""Motor do jogo da Luzia: centelhas (avanços), luz própria e refletida, conversão, trajetória e dossiê.

Regras em `docs/luzia-ux.md` e `docs/specs/2026-11-18-centelhas-conversao.md`. Tudo mora em `private/luzia.db` (fora do git):
- centelhas: estado de luz em `avanco` (apagada, refletida, convertendo, propria, descartada) e história em `avanco_evento`;
- o progresso de um prisma é o lm das centelhas próprias dividido pelo lm de todas as centelhas da meta;
- lúmens: livro `lumen` (só de acréscimo), um lançamento por mudança de luz de uma centelha;
- `nivel_registro` fica só para leitura: é o histórico do modelo anterior, de níveis.
Os arquivos antigos só são lidos pela migração (`migrar.py`).
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime
from pathlib import Path

from . import arquivos, banco, trajetoria

PRIVATE = arquivos.PRIVATE
DOSSIES = PRIVATE / 'dossies'

ESTADOS = ('propria', 'convertendo', 'refletida', 'apagada', 'descartada')
ABERTOS = ('apagada', 'refletida', 'convertendo')
PARA_CONVERTER = ('refletida', 'convertendo')
NOTA_CONVERTE = 3  # nota 3 ou 4 confirma o entendimento; 0 a 2 deixa a centelha convertendo
MARCOS = 'marcos_luz'  # marcos do dossiê no modelo de centelhas ('marcos_dossie' guarda os do modelo de níveis)
ORDEM_ESTADO = {'propria': 0, 'convertendo': 1, 'refletida': 2, 'apagada': 3, 'descartada': 4}
ROTULO_ESTADO = {'propria': 'Luz própria', 'convertendo': 'Convertendo', 'refletida': 'Luz refletida',
                 'apagada': 'Por acender', 'descartada': 'Descartada'}
BASE_TIPO = {'estudar': 20, 'praticar': 20, 'explicar': 15, 'explorar': 10}
MOTIVOS = {'nao_faz_sentido': 'não faz sentido para mim', 'ja_domino': 'já domino', 'agora_nao': 'agora não'}
# Origem do feixe (nome antigo) → origem gravada na coluna do avanço (spec, seção 5); o nome antigo fica no conteúdo.
ORIGEM_COLUNA = {'rota': 'triagem', 'entrega': 'entrega', 'sessão': 'sessao', 'sessao': 'sessao',
                 'trecho': 'acender', 'guardada': 'lampejo'}
# O que o avanço guarda em colunas de estado; todo o resto do feixe vai inteiro em `conteudo_json`.
CAMPOS_ESTADO = {'id', 'status', 'estado', 'historico', 'nota', 'lm_ganho', 'tentativas', 'revisitas',
                 'revisita_aberta', 'valor_lm', 'conta', 'criado_em', 'skill_plano', 'entrega_id', 'onde', 'confirmada_em'}
COLUNAS_ESTADO = ('nota', 'lm_ganho', 'tentativas', 'onde', 'confirmada_em')
COLUNAS_EVENTO = ('onde', 'nota', 'resumo', 'motivo')
# Status no formato das evidências antigas (P3/P4 e telas que ainda leem 'feita'/'pendente').
ESTADO_ANTIGO = {'propria': 'feita', 'convertendo': 'em andamento', 'refletida': 'pendente',
                 'apagada': 'pendente', 'descartada': 'descartada'}


def agora() -> str:
    return datetime.now().isoformat(timespec='seconds')


# ------------------------------------------------------------------ prismas e skills
def ativos(plan: dict, con: sqlite3.Connection | None = None, espera_ms: int | None = None) -> list[str]:
    """Prismas ativos da trajetória, na ordem do plano e depois os incluídos por pedido (arquivados ficam de fora).

    Quem já tem uma conexão a passa em `con`; `espera_ms` encurta a espera do hook.
    """
    if con is None:
        with trajetoria.abrir(espera_ms) as nova:
            return ativos(plan, nova)
    todos = {p['nome']: p for p in trajetoria.prismas(con, incluir_arquivados=True)}
    out = [s['nome'] for s in plan.get('skills', []) if todos.get(s['nome'], {}).get('estado') != 'arquivado']
    out += [n for n, p in todos.items() if p['estado'] == 'ativo' and n not in out]
    return out


def nomes_de_skills(plan: dict) -> list[str]:
    """Skills do plano e prismas incluídos por pedido (para casar nomes sem abrir o banco a cada feixe)."""
    nomes = [s['nome'] for s in plan.get('skills', [])]
    with trajetoria.abrir() as con:
        nomes += [p['nome'] for p in trajetoria.prismas(con) if p['nome'] not in nomes]
    return nomes


def skill_de(nome: str, plan: dict, nomes: list[str] | None = None) -> str:
    """Casa o nome de skill de um feixe com a skill do plano (tolerante a variações)."""
    if nomes is None:
        nomes = nomes_de_skills(plan)
    if nome in nomes:
        return nome
    base = (nome or '').lower()
    for n in nomes:
        chave = n.lower().split('(')[0].split('/')[0].strip()
        if chave and (chave in base or base in n.lower()):
            return n
    return nome


def valor(feixe: dict, plan: dict, prog: dict | None = None, nomes: list[str] | None = None) -> tuple[int, list[list]]:
    """Valor em lúmens por regra visível, calculado UMA vez, quando a centelha nasce (nunca é recalculado).

    Profundidade do conceito (base do tipo + minutos) + lacuna no prisma (até 60% da profundidade, pelo quanto ainda
    não é próprio) + peso para a meta (40% da profundidade se o prisma é um dos 2 com menor luz própria, 20% nos
    outros, 0 se já está em 100%). Entre 10 e 100 lm. `prog`: o progresso por prisma (`luz(...)['por_prisma']`).
    """
    prog = luz(plan)['por_prisma'] if prog is None else prog
    skill = feixe.get('skill_plano') or skill_de(feixe.get('skill', ''), plan, nomes)
    tipo = feixe.get('tipo') if feixe.get('tipo') in BASE_TIPO else 'explicar'
    minutos = max(5, min(30, int(feixe.get('duracao_min') or 10)))
    prof = BASE_TIPO[tipo] + minutos
    pct = int(prog.get(skill, {}).get('pct', 0))
    ordem = sorted(prog, key=lambda n: (prog[n].get('pct', 0), n))
    if pct >= 100:
        peso, motivo = 0, 'prisma já é todo luz própria'
    elif skill in ordem[:2] or skill not in prog:
        peso, motivo = round(prof * 0.4), 'uma das maiores lacunas'
    else:
        peso, motivo = round(prof * 0.2), 'prisma da trajetória'
    conta = [['Profundidade do conceito', f'{tipo} · {minutos} min', prof],
             ['Lacuna no prisma', f'{100 - pct}% ainda não é seu', round(prof * 0.6 * (100 - pct) / 100)],
             ['Peso para a meta', motivo, peso]]
    return max(10, min(100, sum(c[2] for c in conta))), conta


# ------------------------------------------------------------------ avanços (estado em `avanco`, história em `avanco_evento`)
SQL_HISTORICO = "SELECT * FROM avanco_evento WHERE json_extract(extra_json, '$.fonte') = 'historico'"


def _json(valor) -> str:
    return json.dumps(valor, ensure_ascii=False)


def _conteudo(f: dict) -> dict:
    """O que o feixe tem além das colunas de estado (vai inteiro para `conteudo_json`)."""
    return {k: v for k, v in f.items() if k not in CAMPOS_ESTADO}


def _origem_coluna(origem):
    return ORIGEM_COLUNA.get(origem, origem) if isinstance(origem, str) else origem


def _colunas(f: dict) -> tuple:
    """Os campos de conteúdo do avanço (os que `sincronizar` pode mudar), para ver se algo mudou de fato."""
    return (f.get('skill_plano'), f.get('tipo'), f.get('titulo'), _conteudo(f), f.get('duracao_min'),
            f.get('valor_lm'), f.get('conta'), _origem_coluna(f.get('origem')), f.get('dimensao'))


def _evento_de(r: sqlite3.Row) -> dict:
    """Linha de `avanco_evento` no formato do histórico antigo (`quando`, `evento`, e só os campos preenchidos)."""
    try:
        extra = json.loads(r['extra_json'] or '{}')
    except ValueError:
        extra = {}
    h = {'quando': r['quando'], 'evento': r['evento']}
    h.update({c: r[c] for c in COLUNAS_EVENTO if r[c] is not None})
    if isinstance(extra, dict):
        h.update({k: v for k, v in extra.items() if k != 'fonte'})
    return h


def _feixe(r: sqlite3.Row, historico: list[dict]) -> dict:
    """Linha de `avanco` no formato de feixe de sempre (as colunas mandam; o conteúdo traz o resto)."""
    try:
        f = json.loads(r['conteudo_json'] or '{}')
    except ValueError:
        f = {}
    if not isinstance(f, dict):
        f = {}
    f['id'] = r['id']
    for campo in ('titulo', 'tipo', 'dimensao', 'duracao_min'):
        if r[campo] is not None:
            f[campo] = r[campo]
        else:
            f.setdefault(campo, None)
    if 'origem' not in f:  # o nome antigo da origem (rota, sessão...) fica no conteúdo; a coluna usa o novo
        f['origem'] = r['origem']
    f.update(estado=r['estado'], valor_lm=r['valor_lm'], nota=r['nota'], lm_ganho=r['lm_ganho'],
             tentativas=r['tentativas'], criado_em=r['criado_em'], skill_plano=r['prisma'],
             entrega_id=r['entrega_id'], onde=r['onde'], confirmada_em=r['confirmada_em'],
             conta=json.loads(r['conta_json']) if r['conta_json'] else None, historico=historico)
    if f.get('origem') == 'entrega' and r['entrega_id'] is None:
        # vem do que a IA montou na triagem, não do git: o título "da entrega" que ela inventou nunca aparece como entrega
        f.pop('entrega', None)
        f['da_triagem'] = True
    f.pop('revisita_aberta', None)
    return f


def _historicos(con: sqlite3.Connection, fid: str | None = None) -> dict[str, list[dict]]:
    sql, args = (SQL_HISTORICO, ()) if fid is None else (SQL_HISTORICO + ' AND avanco_id = ?', (fid,))
    out: dict[str, list[dict]] = {}
    for r in con.execute(sql + ' ORDER BY id', args):
        out.setdefault(r['avanco_id'], []).append(_evento_de(r))
    return out


def _carregar(con: sqlite3.Connection, historico: bool = True) -> dict[str, dict]:
    hist = _historicos(con) if historico else {}
    return {r['id']: _feixe(r, hist.get(r['id'], [])) for r in con.execute('SELECT * FROM avanco ORDER BY rowid')}


def _ocultos(con: sqlite3.Connection) -> set[str]:
    """Prismas arquivados: os avanços ainda abertos deles não são oferecidos até o prisma ser reativado."""
    return {r['nome'] for r in con.execute("SELECT nome FROM prisma WHERE estado = 'arquivado'")}


def avancos(con: sqlite3.Connection, estado: str | None = None, prisma: str | None = None,
            tipo: str | None = None, historico: bool = True, arquivados: bool = False) -> list[dict]:
    """Avanços do banco, na ordem do catálogo (estado, depois maior valor). Os filtros se combinam (E).

    As centelhas abertas de prisma arquivado ficam de fora (as próprias e descartadas continuam: são história).
    """
    onde, args = [], []
    for coluna, valor_ in (('estado', estado), ('prisma', prisma), ('tipo', tipo)):
        if valor_ is not None:
            onde.append(f'{coluna} = ?')
            args.append(valor_)
    ordem = ' '.join(f"WHEN '{e}' THEN {n}" for e, n in ORDEM_ESTADO.items())
    sql = ('SELECT * FROM avanco' + (' WHERE ' + ' AND '.join(onde) if onde else '')
           + f' ORDER BY CASE estado {ordem} ELSE 9 END, -COALESCE(valor_lm, 0), rowid')
    hist = _historicos(con) if historico else {}
    ocultos = set() if arquivados else _ocultos(con)
    return [_feixe(r, hist.get(r['id'], [])) for r in con.execute(sql, args)
            if not (r['prisma'] in ocultos and r['estado'] in ABERTOS)]


def _um(fid: str, con: sqlite3.Connection | None = None) -> dict | None:
    if con is None:
        with trajetoria.abrir() as nova:
            return _um(fid, nova)
    r = con.execute('SELECT * FROM avanco WHERE id = ?', (fid,)).fetchone()
    return None if r is None else _feixe(r, _historicos(con, fid).get(fid, []))


def _inserir_avanco(con: sqlite3.Connection, f: dict) -> None:
    dur = f.get('duracao_min')
    con.execute(
        'INSERT OR IGNORE INTO avanco (id, prisma, tipo, titulo, conteudo_json, duracao_min, valor_lm, conta_json, origem,'
        ' entrega_id, dimensao, estado, nota, lm_ganho, tentativas, revisitas, revisita_aberta, criado_em, onde)'
        ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (f['id'], f.get('skill_plano'), f.get('tipo'), f.get('titulo'), _json(_conteudo(f)),
         dur if isinstance(dur, int) and not isinstance(dur, bool) else None, f.get('valor_lm'),
         _json(f['conta']) if f.get('conta') is not None else None, _origem_coluna(f.get('origem')), f.get('entrega_id'),
         f.get('dimensao'),
         f.get('estado') or 'apagada', f.get('nota'), int(f.get('lm_ganho') or 0), int(f.get('tentativas') or 0),
         0, 0, f.get('criado_em') or agora(), f.get('onde')))


def _atualizar_conteudo(con: sqlite3.Connection, f: dict, antes: dict) -> None:
    """Grava só o que o sync mudou: o conteúdo é relido dentro da transação (um `resumo` gravado agora por
    `conquistar` não se perde) e recebe apenas as chaves que diferem do que o sync leu."""
    dur = f.get('duracao_min')
    atual = json.loads(con.execute('SELECT conteudo_json FROM avanco WHERE id = ?', (f['id'],)).fetchone()[0] or '{}')
    novo = _conteudo(f)
    atual.update({k: v for k, v in novo.items() if antes.get(k, object()) != v})
    for k in set(antes) - set(novo):
        atual.pop(k, None)
    con.execute(
        'UPDATE avanco SET prisma = ?, tipo = ?, titulo = ?, conteudo_json = ?, duracao_min = ?, valor_lm = ?,'
        ' conta_json = ?, origem = ?, dimensao = ? WHERE id = ?',
        (f.get('skill_plano'), f.get('tipo'), f.get('titulo'), _json(atual),
         dur if isinstance(dur, int) and not isinstance(dur, bool) else None, f.get('valor_lm'),
         _json(f['conta']) if f.get('conta') is not None else None, _origem_coluna(f.get('origem')),
         f.get('dimensao'), f['id']))


def _atualizar_estado(con: sqlite3.Connection, fid: str, estado: str | None, campos: dict) -> None:
    """Muda o estado atual do avanço; campo sem coluna (ex.: `resumo`) vai para o conteúdo."""
    sets, args, extras = [], [], {}
    if estado:
        sets.append('estado = ?')
        args.append(estado)
    for k, v in campos.items():
        if k in COLUNAS_ESTADO:
            sets.append(f'{k} = ?')
            args.append(v)
        else:
            extras[k] = v
    if extras:
        atual = json.loads(con.execute('SELECT conteudo_json FROM avanco WHERE id = ?', (fid,)).fetchone()[0] or '{}')
        sets.append('conteudo_json = ?')
        args.append(_json({**atual, **extras}))
    if sets:
        con.execute(f'UPDATE avanco SET {", ".join(sets)} WHERE id = ?', (*args, fid))


def _evento(con: sqlite3.Connection, fid: str, evento: str, **campos) -> None:
    """Acrescenta ao livro um fato da história do avanço (`fonte` 'historico'; o que não tem coluna vai em extra)."""
    colunas = {c: campos.pop(c, None) for c in COLUNAS_EVENTO}
    con.execute('INSERT INTO avanco_evento (avanco_id, quando, evento, onde, nota, resumo, motivo, extra_json)'
                ' VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (fid, agora(), evento, colunas['onde'], colunas['nota'], colunas['resumo'], colunas['motivo'],
                 _json({'fonte': 'historico', **campos})))


# ------------------------------------------------------------------ catálogo de centelhas
def sincronizar(plan: dict) -> dict[str, dict]:
    """Traz para o catálogo as centelhas que a Luzia sugeriu, sem perder estados e histórico.

    Só insere centelhas novas (com o valor calculado agora, uma vez) e atualiza o conteúdo do que mudou de fato:
    o painel lê a cada 4 s, então nada é regravado quando nada mudou. O valor de quem já existe nunca muda.
    """
    from . import acoes
    nomes = nomes_de_skills(plan)
    with trajetoria.abrir() as con:
        cat = _carregar(con)
        antes = {fid: _colunas(f) for fid, f in cat.items()}
        novos: list[str] = []
        antigos = None  # eventos registrados antes do catálogo existir (lidos só se houver centelha nova)
        for f in acoes.derivadas(plan):
            fid = f['id']
            conteudo = {k: v for k, v in f.items() if k not in CAMPOS_ESTADO and k not in ('nota', 'resumo', 'quando')}
            atual = cat.get(fid)
            if atual is None:
                if antigos is None:
                    antigos = acoes.status_map(con)
                st = antigos.get(fid, {}).get('status')
                cat[fid] = {**conteudo, 'id': fid, 'estado': 'convertendo' if st == 'em andamento' else 'apagada',
                            'criado_em': agora(), 'historico': [], 'tentativas': 0, 'lm_ganho': 0, 'nota': None}
                novos.append(fid)
            else:
                # título renomeado e prisma escolhido num pedido `dividir` (prisma_fixo) não voltam ao do plano
                atual.update({k: v for k, v in conteudo.items()
                              if not (k == 'titulo' and atual.get('renomeado'))
                              and not (k == 'skill' and atual.get('prisma_fixo'))})
        for f in cat.values():
            f['skill_plano'] = f.get('prisma_fixo') or skill_de(f.get('skill', ''), plan, nomes)
        sem_valor = [fid for fid, f in cat.items() if fid in novos or f.get('valor_lm') is None]
        if sem_valor:
            prog = luz(plan, con)['por_prisma']
            for fid in sem_valor:
                cat[fid]['valor_lm'], cat[fid]['conta'] = valor(cat[fid], plan, prog, nomes)
        mudaram = [fid for fid, f in cat.items() if fid not in novos and _colunas(f) != antes[fid]]
        if novos or mudaram:
            with banco.transacao(con):
                for fid in novos:
                    _inserir_avanco(con, cat[fid])
                for fid in mudaram:
                    _atualizar_conteudo(con, cat[fid], antes[fid][3])
    return cat


def catalogo(plan: dict, descartados: bool = False) -> list[dict]:
    cat = sincronizar(plan)
    with trajetoria.abrir() as con:
        ocultos = _ocultos(con)
    lista = [f for f in cat.values() if (descartados or f.get('estado') != 'descartada')
             and not (f.get('skill_plano') in ocultos and f.get('estado') in ABERTOS)]
    for f in lista:
        f['status'] = ESTADO_ANTIGO.get(f.get('estado'), 'pendente')
    return sorted(lista, key=lambda f: (ORDEM_ESTADO.get(f.get('estado'), 9), -int(f.get('valor_lm') or 0)))


def _mudar(fid: str, estado: str | None, evento: str, campos: dict | None = None, exige: tuple | None = None,
           **extra) -> dict | None:
    """Muda a centelha numa transação; `exige`: estados aceitos, conferidos com a trava na mão (o hook pode ter mudado)."""
    with trajetoria.abrir() as con:
        with banco.transacao(con):
            r = con.execute('SELECT estado FROM avanco WHERE id = ?', (fid,)).fetchone()
            if r is None or (exige is not None and r['estado'] not in exige):
                return None
            _atualizar_estado(con, fid, estado, campos or {})
            _evento(con, fid, evento, **extra)
        return _um(fid, con)


def iniciar(fid: str, onde: str = '', evento: str = 'iniciado'):
    """Começa (ou retoma) a conversão: `apagada` ou `refletida` → `convertendo`. A luz de origem fica no conteúdo."""
    f = _um(fid)
    if not f or f.get('estado') in ('descartada', 'propria'):
        return None
    if f.get('estado') == 'convertendo':
        return _mudar(fid, None, 'retomado' if evento == 'iniciado' else evento, exige=('convertendo',), onde=onde)
    return _mudar(fid, 'convertendo', evento, {'luz_origem': f.get('estado')}, exige=(f.get('estado'),), onde=onde)


def enfileirar(fid: str):
    """Manda a centelha para a fila do agente: ela passa a convertendo (o agente guia a conversão)."""
    return iniciar(fid, evento='enviado ao agente')


def descartar(fid: str, motivo: str):
    """Tira a centelha da meta (sai do total). Luz própria não se descarta."""
    f = _um(fid)
    if not f or f.get('estado') in ('propria', 'descartada'):
        return None
    return _mudar(fid, 'descartada', 'descartado', exige=(f.get('estado'),), motivo=MOTIVOS.get(motivo, motivo),
                  estado_antes=f.get('estado'))


def restaurar(fid: str):
    """Volta ao estado de antes do descarte (padrão: apagada)."""
    f = _um(fid)
    if not f or f.get('estado') != 'descartada':
        return None
    antes = next((h.get('estado_antes') for h in reversed(f.get('historico') or []) if h.get('evento') == 'descartado'), None)
    return _mudar(fid, antes if antes in ABERTOS else 'apagada', 'restaurado', exige=('descartada',))


def motivos_descartados() -> list[dict]:
    with trajetoria.abrir() as con:
        return [{'titulo': f.get('titulo'), 'skill': f.get('skill'), 'motivo': (f.get('historico') or [{}])[-1].get('motivo')}
                for f in avancos(con, estado='descartada')]


def convertendo(espera_ms: int | None = None) -> list[dict]:
    """Centelhas em conversão (sem histórico), para a linha de status e o aviso de início de sessão."""
    with trajetoria.abrir(espera_ms) as con:
        return avancos(con, estado='convertendo', historico=False)


# ------------------------------------------------------------------ lúmens (livro `lumen`, só de acréscimo)
def _lumen(con: sqlite3.Connection, skill: str, lm: int, luz_: str, fonte: str, ref: str = '') -> dict:
    """Acrescenta um lúmen ao livro, dentro da transação de quem chama."""
    rec = {'quando': agora(), 'skill': skill, 'lm': int(lm), 'luz': luz_, 'fonte': fonte, 'ref': ref}
    con.execute('INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, ?, ?, ?, ?)',
                (rec['quando'], skill, rec['lm'], luz_, fonte, ref))
    return rec


def lancar(skill: str, lm: int, luz_: str, fonte: str, ref: str = '') -> dict:
    with trajetoria.abrir() as con, banco.transacao(con):
        return _lumen(con, skill, lm, luz_, fonte, ref)


def livro(desde: str | None = None, limite: int | None = None) -> list[dict]:
    """Lúmens na ordem em que entraram (quando, skill, lm, luz, fonte, ref). `desde`: data/hora mínima; `limite`: só os últimos."""
    sql = 'SELECT quando, prisma AS skill, lm, luz, fonte, ref FROM lumen'
    args: list = []
    if desde:
        sql += ' WHERE quando >= ?'
        args.append(desde)
    if limite:
        sql += ' ORDER BY id DESC LIMIT ?'
        args.append(int(limite))
    else:
        sql += ' ORDER BY id'
    with trajetoria.abrir() as con:
        linhas = [dict(r) for r in con.execute(sql, args)]
    return linhas[::-1] if limite else linhas


# ------------------------------------------------------------------ conversão: avaliar (a Luzia) e confirmar (o sim)
def avaliar(fid: str, nota: int, resumo: str, plan: dict) -> dict:
    """A Luzia aplica a rubrica 0–4 numa centelha em conversão.

    Nota 3 ou 4: o entendimento fica confirmado (`confirmada_em`) e a centelha espera o sim da pessoa (`confirmar`).
    Nota 0 a 2: continua convertendo, com a dica do que faltou (`resumo`) e mais uma tentativa.
    """
    sincronizar(plan)
    f = _um(fid)
    if not f:
        return {'erro': 'centelha não encontrada'}
    if f.get('estado') == 'propria':
        return {'erro': 'esta centelha já é luz própria'}
    if f.get('estado') != 'convertendo':
        return {'erro': f'esta centelha ainda não está em conversão: comece por /luzia:fazer {fid}'}
    nota = max(0, min(4, int(nota)))
    with trajetoria.abrir() as con:
        with banco.transacao(con):
            if nota >= NOTA_CONVERTE:
                _atualizar_estado(con, fid, None, {'nota': nota, 'confirmada_em': agora(), 'resumo': resumo})
                _evento(con, fid, 'confirmada', nota=nota, resumo=resumo)
            else:
                con.execute('UPDATE avanco SET tentativas = tentativas + 1 WHERE id = ?', (fid,))
                _atualizar_estado(con, fid, None, {'nota': nota, 'confirmada_em': None, 'dica': resumo})
                _evento(con, fid, 'tente de novo', nota=nota, resumo=resumo)
        f = _um(fid, con)
    return {'confirmada': nota >= NOTA_CONVERTE, 'tente_de_novo': nota < NOTA_CONVERTE, 'nota': nota, 'feixe': f}


def confirmar(fid: str, plan: dict) -> dict:
    """O sim da pessoa: a centelha confirmada pela Luzia vira luz própria (lúmen no livro, uma vez só).

    Tudo numa transação: o estado é relido com a trava na mão, então dois "sim" ao mesmo tempo lançam um lúmen só.
    """
    marco = None
    with trajetoria.abrir() as con:
        with banco.transacao(con):
            r = con.execute('SELECT * FROM avanco WHERE id = ?', (fid,)).fetchone()
            if r is None:
                return {'erro': 'centelha não encontrada'}
            if r['estado'] == 'propria':
                return {'erro': 'esta centelha já é luz própria'}
            if r['estado'] != 'convertendo' or not r['confirmada_em']:
                return {'erro': 'a Luzia ainda não confirmou o seu entendimento: converse sobre a centelha primeiro '
                                f'(/luzia:fazer {fid})'}
            antes = luz(plan, con)
            conteudo = json.loads(r['conteudo_json'] or '{}')
            fonte = 'conversao' if conteudo.get('luz_origem') == 'refletida' else 'acesa'
            lm = int(r['valor_lm'] or 0)
            _lumen(con, r['prisma'], lm, 'propria', fonte, fid)
            _atualizar_estado(con, fid, 'propria', {'lm_ganho': lm})
            _evento(con, fid, 'luz própria', nota=r['nota'], lm=lm)
            depois = luz(plan, con)
            marco = _marco(con, depois)
        f = _um(fid, con)
        if marco is not None:
            marco = {'n': marco, 'dossie': str(dossie(plan, f'marco {marco} de 3', con))}
    pa = antes['por_prisma'].get(r['prisma'], {}).get('pct', 0)
    pd = depois['por_prisma'].get(r['prisma'], {}).get('pct', 0)
    return {'ganho': lm, 'feixe': f, 'prisma': r['prisma'], 'pct_antes': pa, 'pct_depois': pd, 'luz': depois, 'marco': marco}


def _marco(con: sqlite3.Connection, t: dict) -> int | None:
    """Marcos do dossiê em 1/3, 2/3 e 100% do lm próprio da trajetória (cada um uma vez)."""
    feitos = list(trajetoria.perfil_ler(con, MARCOS, []) or [])
    novo = None
    for i, corte in enumerate((100 / 3, 200 / 3, 100), 1):
        if t['tot'] and 100 * t['propria'] / t['tot'] >= corte - 1e-9 and i not in feitos:
            feitos.append(i)
            novo = i
    if novo is not None:
        trajetoria.perfil_gravar(con, MARCOS, feitos)
    return novo


# ------------------------------------------------------------------ reconhecimento do observador (hooks)
def reconhecer(sessao: str, chave: str, skill: str, centelha: str, nova: dict | None = None, onde: str = '',
               extensao: str = '', ferramenta: str = '', modo: str = '', interveio: bool = False,
               estado: dict | None = None) -> dict | None:
    """Um reconhecimento do observador numa centelha, numa tentativa curta (`banco._reconhecer` aplica as regras).

    `chave`: 'prompt' (a pessoa dirigiu: vira luz própria) ou 'agente' (o agente aplicou: vira luz refletida).
    `nova`: a centelha a criar se ainda não existe (titulo, tipo, duracao_min, valor_lm, conta, conteudo).
    Devolve o que aconteceu ({'centelha', 'estado', 'lm', 'luz', 'novo', 'mudou'}) ou None (nada a mostrar).
    Se o banco estiver ocupado, vai inteiro para os pendentes (nada se perde) e a função devolve o resultado esperado,
    provisório; `estado` (opcional) recebe `provisorio=True`. Nunca levanta por causa do banco.
    """
    dados = {'sessao': sessao, 'chave': chave, 'prisma': skill, 'centelha': centelha,
             'nova_json': json.dumps(nova, ensure_ascii=False) if nova else None, 'onde': onde or None,
             'extensao': extensao, 'ferramenta': ferramenta, 'modo': modo, 'interveio': 1 if interveio else 0}
    retorno: dict = {}
    if banco.gravar_ou_pendurar('reconhecimento', dados, retorno=retorno):
        return retorno.get('resultado')
    if estado is not None:
        estado['provisorio'] = True
    luz_ = 'propria' if chave == 'prompt' else 'refletida'
    return {'centelha': centelha, 'estado': luz_, 'lm': int((nova or {}).get('valor_lm') or 0), 'luz': luz_,
            'novo': bool(nova), 'mudou': True}


def para_casar(con: sqlite3.Connection) -> dict[str, list[dict]]:
    """Centelhas de cada prisma com as palavras que o observador procura (palavras + conceitos + título do chat)."""
    out: dict[str, list[dict]] = {}
    for r in con.execute('SELECT id, prisma, estado, titulo, origem, valor_lm, conteudo_json FROM avanco '
                         'WHERE prisma IS NOT NULL ORDER BY rowid'):
        try:
            c = json.loads(r['conteudo_json'] or '{}')
        except ValueError:
            c = {}
        c = c if isinstance(c, dict) else {}
        palavras = [str(w) for w in (c.get('palavras') or []) + (c.get('conceitos') or []) if w]
        if r['origem'] == 'chat' and r['titulo']:
            palavras.append(r['titulo'])
        out.setdefault(r['prisma'], []).append({'id': r['id'], 'estado': r['estado'], 'titulo': r['titulo'],
                                                'lm': r['valor_lm'], 'origem': r['origem'],
                                                'palavras': list(dict.fromkeys(palavras))})
    return out


# ------------------------------------------------------------------ trajetória: luz própria sobre o total da meta
SQL_LUZ = """SELECT prisma, estado, COUNT(*) AS n, SUM(COALESCE(valor_lm, 0)) AS lm FROM avanco
             WHERE estado != 'descartada' AND prisma IS NOT NULL GROUP BY prisma, estado"""
SQL_PROXIMAS = """SELECT id, prisma, estado, valor_lm FROM avanco WHERE estado IN ('convertendo', 'refletida', 'apagada')"""
SQL_DA_META = """SELECT DISTINCT prisma FROM avanco WHERE estado != 'descartada' AND COALESCE(origem, '') != 'chat'"""


def luz(plan: dict, con: sqlite3.Connection | None = None, espera_ms: int | None = None) -> dict:
    """Quanto da trajetória já é luz própria: por prisma ativo e no total (poucas consultas; o painel lê a cada 4 s).

    Por prisma: tot, propria, refletida (refletida + convertendo), convertendo, apagada, pct, pct_refletida, n,
    n_propria, n_converter, n_apagada, na_meta, proxima (a centelha a converter primeiro) e meta_estado.
    """
    if con is None:
        with trajetoria.abrir(espera_ms) as nova:
            return luz(plan, nova)
    nomes = ativos(plan, con)
    meta_estado = {r['nome']: r['meta_estado'] for r in con.execute('SELECT nome, meta_estado FROM prisma')}
    base = {n: {'propria': 0, 'convertendo': 0, 'refletida': 0, 'apagada': 0} for n in nomes}
    cont = {n: {'propria': 0, 'convertendo': 0, 'refletida': 0, 'apagada': 0} for n in nomes}
    for r in con.execute(SQL_LUZ):
        if r['prisma'] in base and r['estado'] in base[r['prisma']]:
            base[r['prisma']][r['estado']] = int(r['lm'])
            cont[r['prisma']][r['estado']] = int(r['n'])
    da_meta = {r['prisma'] for r in con.execute(SQL_DA_META)}
    ordem = {'convertendo': 0, 'refletida': 1, 'apagada': 2}
    proximas: dict[str, tuple] = {}
    for r in con.execute(SQL_PROXIMAS):
        chave = (ordem[r['estado']], -int(r['valor_lm'] or 0), r['id'])
        if r['prisma'] in base and (r['prisma'] not in proximas or chave < proximas[r['prisma']]):
            proximas[r['prisma']] = chave
    prismas_, por = [], {}
    for n in nomes:
        b, c = base[n], cont[n]
        tot = sum(b.values())
        refl = b['refletida'] + b['convertendo']
        p = {'nome': n, 'tot': tot, 'propria': b['propria'], 'refletida': refl, 'convertendo': b['convertendo'],
             'apagada': b['apagada'], 'pct': round(100 * b['propria'] / tot) if tot else 0,
             'pct_refletida': round(100 * refl / tot) if tot else 0,
             'n': sum(c.values()), 'n_propria': c['propria'], 'n_converter': c['refletida'] + c['convertendo'],
             'n_apagada': c['apagada'], 'na_meta': bool(tot) and b['propria'] == tot and n in da_meta,
             'proxima': proximas[n][2] if n in proximas else None, 'meta_estado': meta_estado.get(n, 'definida')}
        prismas_.append(p)
        por[n] = p
    tot = sum(p['tot'] for p in prismas_)
    propria = sum(p['propria'] for p in prismas_)
    por_estado = {e: sum(base[n][e] for n in nomes) for e in ('propria', 'convertendo', 'refletida', 'apagada')}
    return {'tot': tot, 'propria': propria, 'refletida': por_estado['refletida'] + por_estado['convertendo'],
            'pct': round(100 * propria / tot) if tot else 0, 'por_estado': por_estado, 'prismas': prismas_,
            'por_prisma': por, 'n_converter': sum(p['n_converter'] for p in prismas_)}


def ritmo(plan: dict, horizonte: str = '') -> dict:
    """Calibragem (não cronograma): centelhas por semana para a luz própria chegar à meta no prazo imaginado."""
    with trajetoria.abrir() as con:
        t = luz(plan, con)
        abertas = [f for f in avancos(con, historico=False) if f.get('estado') in ABERTOS]
    faltam = t['tot'] - t['propria']
    meses = next((int(x) for x in str(horizonte).split() if x.isdigit()), 12)
    medio = (sum(int(f.get('valor_lm') or 40) for f in abertas) / len(abertas)) if abertas else 40
    semanas = max(1.0, meses * 4.33)
    return {'lm_faltam': max(0, faltam), 'meses': meses,
            'feixes_semana': max(1, math.ceil(faltam / (medio * semanas))) if faltam else 0}


# ------------------------------------------------------------------ dossiê
TIPO_PEDIDO = {'incluir': 'incluir skill', 'arquivar': 'arquivar skill', 'reativar': 'reativar skill',
               'mudar_meta': 'mudar a meta', 'dividir': 'dividir skill', 'propor_meta': 'definir as ações da meta'}
SQL_PEDIDOS_ACEITOS = """
    SELECT p.tipo, p.prisma, p.motivo, p.criado_em, p.decidido_em, l.texto, l.modelo, l.criado_em AS leitura_em
    FROM pedido p LEFT JOIN leitura l ON l.id = p.leitura_id
    WHERE p.estado = 'aceito' ORDER BY COALESCE(p.decidido_em, p.criado_em), p.id"""


def dossie(plan: dict, titulo: str = 'agora', con: sqlite3.Connection | None = None) -> Path:
    """Dossiê de evidências em linguagem formal (skill, ação, autoria própria): só ações próprias contam como evidência."""
    if con is None:
        with trajetoria.abrir() as nova:
            return dossie(plan, titulo, nova)
    t = luz(plan, con)
    proprias = avancos(con, estado='propria')
    pedidos = con.execute(SQL_PEDIDOS_ACEITOS).fetchall()
    linhas = [
        f'# Dossiê de evidências · {titulo} · {agora()[:10]}', '',
        f"Trajetória: **{t['pct']}% de autoria própria** ({t['propria']} de {t['tot']} pontos de evidência da meta).", '',
        '## Ações com autoria própria (avaliadas pela rubrica 0–4 ou dirigidas pela pessoa)',
    ]
    for f in sorted(proprias, key=lambda x: (x.get('historico') or [{}])[-1].get('quando', '')):
        nota = f"nota {f.get('nota')}/4" if f.get('nota') is not None else 'dirigida pela pessoa'
        onde = f" · {f.get('onde')}" if f.get('onde') else ''
        quando = (f.get('historico') or [{}])[-1].get('quando', '')[:10]
        linhas.append(f"- {quando} · **{f.get('titulo')}** · {f.get('skill_plano') or f.get('skill')} · {nota} · "
                      f"{f.get('valor_lm')} pontos de evidência{onde}" + (f" — {f['resumo']}" if f.get('resumo') else ''))
    if not proprias:
        linhas.append('- nenhuma ainda')
    linhas += ['', '## Pedidos de mudança aceitos']
    for p in pedidos:
        linha = f"- {(p['decidido_em'] or p['criado_em'])[:10]} · {TIPO_PEDIDO.get(p['tipo'], p['tipo'])} · {p['prisma']}"
        if p['motivo']:
            linha += f" — {p['motivo']}"
        linhas.append(linha)
        if p['texto'] and p['modelo']:
            linhas.append(f"  - Análise: {p['texto']} (com base em {p['modelo']}, {(p['leitura_em'] or '')[:10]})")
        elif p['texto']:
            linhas.append('  - Análise: leitura indisponível')
    if not pedidos:
        linhas.append('- nenhum')
    linhas += ['', '## Por skill']
    for p in t['prismas']:
        linhas.append(f"- {p['nome']}: {p['pct']}% de autoria própria · {p['propria']} de {p['tot']} pontos de evidência · "
                      f"{p['n_propria']} de {p['n']} ações próprias")
    historico = trajetoria.historico_subidas(con)
    if historico:
        linhas += ['', '## Histórico (modelo anterior, por níveis)']
        linhas += [f"- {h['quando'][:10]} · {h['skill']} → nível {h['para']} ({h['lm']} pontos de evidência no período, "
                   f"{h['luz_propria']}% de autoria própria)" for h in historico]
    linhas += ['', '_Gerado localmente pela Luzia a partir das evidências registradas; não substitui a avaliação do seu líder._']
    DOSSIES.mkdir(parents=True, exist_ok=True)
    caminho = DOSSIES / f"dossie-{agora()[:10]}-{titulo.replace(' ', '-')}.md"
    caminho.write_text('\n'.join(linhas) + '\n', encoding='utf-8')
    return caminho
