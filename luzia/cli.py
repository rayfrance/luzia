"""CLI da Luzia (agnóstica de harness; no Claude Code é chamada pelos comandos /luzia:*).

O jogo (docs/specs/2026-11-18-centelhas-conversao.md): centelhas (avanços, no código) valem lúmens; o progresso de um
prisma (skill) é o lm das centelhas de luz própria sobre o lm de todas as centelhas da meta; o loop central é converter
luz refletida em própria (a Luzia guia, a pessoa explica, a Luzia confirma, a pessoa dá o sim).
- `hoje`, `triage`, `trajetoria` (`next-level`/`rota`), `entregas` (`feedback-progress`), `entrega <id>`,
  `acender-entrega <id>`, `identidade`, `leituras` (`analises`),
  `feedback-skills-opportunities`
- `centelhas [--estado converter|propria|apagada|todas]` (`avancos`, `acoes`), `fila`, `fazer`/`converter`/`prompt <id>`,
  `registrar <id> --nota --resumo` (a Luzia avalia), `confirmar <id>` (o sim: vira luz própria), `descartar <id> --motivo`,
  `restaurar <id>`, `enviar <id>`
- `foco --prompt-arquivo F | --arquivos P... [--cwd D] [--sessao S]` (foco sem hooks, para Antigravity, Codex e Cursor)
- `subir` (explica a mudança), `acender <prisma>` (`trecho`), `pedido <subacao> ...`, `dividir <prisma>` / `dividir-todos`
  (um prisma por habilidade), `dossie`, `career-map`, `modo`, `modelo`
- `acesso [sair-de-todos]` (sessões do painel; `career-map` já entra logado),
  `privacidade [mascarar-modelo on|off]` (mascarar ou não o que vai ao modelo; padrão: desligado)
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from . import (acoes, arquivos, banco, entregas, jogo, leituras, modelo, observer, pedidos, pipeline, planner, prismas, propriedade,
               trajetoria, triage)
from .privacy import Redactor, SemMascara

PAINEL = 'http://127.0.0.1:8501'  # nunca `localhost`: pode resolver para ::1, fora da porta exclusiva
MODOS = ('ativo', 'passivo', 'sob_demanda')
CLI = arquivos.CLI


LARGURA_BARRA = 12
GLIFOS_LUZ = {'propria': '█', 'convertendo': '▓', 'refletida': '▒', 'apagada': '░'}


def barra_luz_txt(propria: float = 0, convertendo: float = 0, refletida: float = 0, apagada: float = 0,
                  largura: int = LARGURA_BARRA) -> str:
    """Barra de luz em texto: um glifo por estado (█ própria, ▓ convertendo, ▒ refletida, ░ por acender), cada trecho
    proporcional ao lm. O estado nunca depende só de cor. `refletida` aqui é só a luz refletida ainda não em conversão."""
    partes = [('propria', propria), ('convertendo', convertendo), ('refletida', refletida), ('apagada', apagada)]
    partes = [(k, max(0.0, float(v or 0))) for k, v in partes]
    tot = sum(v for _, v in partes)
    if tot <= 0:
        return GLIFOS_LUZ['apagada'] * largura
    exatos = {k: v / tot * largura for k, v in partes}
    n = {k: int(x) for k, x in exatos.items()}
    for k, v in partes:  # quem tem lm aparece com pelo menos 1 glifo
        if v > 0 and n[k] == 0:
            n[k] = 1
    while sum(n.values()) < largura:  # o resto vai a quem tem a maior parte fracionária
        k = max((k for k, v in partes if v > 0), key=lambda k: exatos[k] - n[k])
        n[k] += 1
    while sum(n.values()) > largura:
        k = max(n, key=lambda k: n[k])
        n[k] -= 1
    return ''.join(GLIFOS_LUZ[k] * n[k] for k, _ in partes)


def barra_de(p: dict, largura: int = LARGURA_BARRA) -> str:
    """Barra de um prisma de `jogo.luz` (a chave `refletida` dele já inclui o que está convertendo)."""
    return barra_luz_txt(p.get('propria', 0), p.get('convertendo', 0),
                         max(0, p.get('refletida', 0) - p.get('convertendo', 0)), p.get('apagada', 0), largura)


def barra_total(t: dict, largura: int = LARGURA_BARRA) -> str:
    e = t.get('por_estado') or {}
    return barra_luz_txt(e.get('propria', 0), e.get('convertendo', 0), e.get('refletida', 0), e.get('apagada', 0), largura)


# ------------------------------------------------------------------ entradas e redação
def load_cfg(entrada_path: Path) -> dict:
    return json.loads(entrada_path.read_text(encoding='utf-8'))


def make_redactor(cfg: dict) -> Redactor:
    """Redator da triagem: só mascara com o interruptor `mascarar_modelo` ligado (padrão: envia real); mesmo redator do
    envio ao modelo (`pipeline.redator_modelo`), que nunca mascara as identidades da própria pessoa."""
    if not pipeline.mascarar_modelo():
        return SemMascara()
    return pipeline.redator_modelo()


def base_triagem(mascarado: bool, cfg: dict | None = None) -> str:
    """Rótulo da base da triagem: só as fontes que a pessoa deu (`entrada.json`) e se o envio saiu mascarado."""
    if cfg is None:
        fontes = ['sua entrada', 'currículo', 'commits', 'histórico autorizado']
    else:
        fontes = ['sua entrada'] + [nome for nome, tem in (
            ('currículo', cfg.get('cv_pdf')), ('GitHub', cfg.get('github')), ('commits', cfg.get('repo')),
            ('histórico das IAs', cfg.get('incluir_historico_ia') is True)) if tem]
    texto = ', '.join(fontes[:-1]) + ' e ' + fontes[-1] if len(fontes) > 1 else fontes[0]
    return texto + (' (mascarados antes do envio ao modelo)' if mascarado else '')


def skills_summary(plan: dict) -> list[dict]:
    return [{'nome': p['nome'], 'luz_propria_pct': p['pct'], 'lm_total': p['tot']} for p in jogo.luz(plan)['prismas']]


# ------------------------------------------------------------------ chamadas ao modelo
def execute_triage(entrada_path: Path, rotulo: str = 'plugin-triage', save_state: bool = True) -> tuple[dict, dict, dict]:
    pipeline.load_env()
    cfg = load_cfg(entrada_path)
    t0 = time.perf_counter()
    redactor = make_redactor(cfg)

    inputs = dict(cfg)
    inputs['cv_text'] = triage.read_pdf(Path(cfg['cv_pdf'])) if cfg.get('cv_pdf') else ''
    inputs['linkedin_text'] = triage.read_pdf(Path(cfg['linkedin_pdf'])) if cfg.get('linkedin_pdf') else ''
    inputs['github_data'] = {}
    if cfg.get('github'):
        try:
            inputs['github_data'] = triage.github_profile(cfg['github'])
        except Exception:
            inputs['github_data'] = {}
    if cfg.get('incluir_historico_ia') is True:  # só com o sim explícito da pessoa (`configurar --com-historico`)
        inputs['ai_history'] = triage.shared_ai_history(vault_dir=Path(cfg['vault']) if cfg.get('vault') else None)
    else:
        inputs['ai_history'] = {}

    payload = pipeline.build_payload(inputs, redactor)
    result, record = pipeline.run_plan(
        payload, prep_seconds=time.perf_counter() - t0, label=rotulo, hits=dict(redactor.hits),
        save_current_state=save_state, ja_mascarado=not isinstance(redactor, SemMascara),
    )
    return result.plan, record, dict(redactor.hits)


def daily_call(entrada_path: Path, rotulo: str) -> tuple[dict, dict, dict]:
    """Chamada leve do dia a dia (oportunidades da sessão): plano salvo + eventos mascarados e evidências.

    As entregas não passam mais pelo modelo: vêm só do git (`entregas.py`)."""
    pipeline.load_env()
    plan = pipeline.load_state().get('plano', {})
    cfg = load_cfg(entrada_path)
    t0 = time.perf_counter()
    redactor = make_redactor(cfg)
    payload = {
        'objetivo': plan.get('aonde_quer_chegar', {}),
        'skills': skills_summary(plan),
        'eventos_sessao': pipeline.session_events(),
        'evidencias_registradas': [
            {k: e.get(k) for k in ('entrega', 'dimensao', 'nota', 'skill')} for e in acoes.evidencias()
        ],
        'feixes_descartados_pela_pessoa': jogo.motivos_descartados(),
    }
    schema, intro = planner.OPPORTUNITIES_SCHEMA, 'Plano salvo + eventos mascarados da sessão atual no agente:'
    result, record = pipeline.run_plan(
        payload, prep_seconds=time.perf_counter() - t0, label=rotulo, hits=dict(redactor.hits),
        schema=schema, intro=intro,
    )
    pipeline.update_state({'oportunidades_tarefa_atual': result.plan.get('oportunidades_tarefa_atual', [])}, record)
    return result.plan, record, dict(redactor.hits)


def sem_centelha(args) -> str:
    """Mensagem para id vazio (como usar) ou inexistente."""
    if not args.valor:
        return f'Use: {args.comando} <id> (o id aparece em /luzia:centelhas).'
    return f'Centelha {args.valor} não encontrada.'


def nota_valida(bruta) -> int | None:
    """Nota da rubrica: inteiro de 0 a 4; qualquer outra coisa é None."""
    try:
        n = int(str(bruta).strip())
    except (TypeError, ValueError):
        return None
    return n if 0 <= n <= 4 else None


def gerar_trecho(skill: str, rotulo: str = 'cmd-trecho') -> dict:
    """Acende 3 centelhas novas para um prisma (quando ele fica sem centelha aberta ou a pessoa pede mais).

    Nascem `apagada`; o valor em lm é calculado uma vez, quando entram no catálogo (`jogo.sincronizar`)."""
    pipeline.load_env()
    plan = pipeline.load_state().get('plano', {})
    skill = jogo.skill_de(skill, plan)
    p = jogo.luz(plan)['por_prisma'].get(skill)
    if not p:
        return {'erro': 'prisma não encontrado na sua trajetória'}
    if p['na_meta']:
        return {'erro': 'este prisma já é todo luz própria'}
    t0 = time.perf_counter()
    s = next((x for x in plan.get('skills', []) if x['nome'] == skill), {})
    existentes = [f for f in acoes.todas(plan, descartados=True) if (f.get('skill_plano') or f.get('skill')) == skill]
    payload = {
        'objetivo': plan.get('aonde_quer_chegar', {}),
        'skill': {'nome': skill, 'luz_propria_pct': p['pct'], 'evidencia': s.get('evidencia', '')},
        'feixes_existentes': [{'titulo': f.get('titulo'), 'estado': f.get('estado')} for f in existentes],
        'feixes_descartados_pela_pessoa': [m for m in jogo.motivos_descartados() if jogo.skill_de(m.get('skill') or '', plan) == skill],
    }
    result, record = pipeline.run_plan(payload, prep_seconds=time.perf_counter() - t0, label=rotulo,
                                       schema=planner.TRECHO_SCHEMA,
                                       intro='Trajetória salva da pessoa e o prisma que precisa de 3 novas centelhas:')
    novas = [a for a in result.plan.get('acoes', []) if isinstance(a, dict) and a.get('titulo')][:3]
    if not novas:
        return {'erro': 'o modelo não devolveu centelhas; tente de novo'}
    for a in novas:  # a centelha é do prisma pedido, uma habilidade só, mesmo que o modelo escreva outro nome
        a['skill'] = skill
    trechos = plan.get('trechos', []) + [{'skill': skill, 'quando': record['quando'], 'acoes': novas}]
    pipeline.update_state({'trechos': trechos}, record)
    plan = pipeline.load_state().get('plano', {})
    ids = {acoes.aid('trecho', skill + a.get('titulo', '')) for a in novas}
    gerados = [f for f in acoes.todas(plan) if f['id'] in ids]
    return {'skill': skill, 'prisma': skill, 'feixes': gerados, 'avancos': gerados, 'record': record}


def acender_entrega(entrega_id: int, rotulo: str = 'cmd-acender-entrega') -> dict:
    """2 centelhas ligadas a uma entrega, nascem luz refletida: P3 (explicar o conceito aplicado) e P4 (defender a decisão e as alternativas).

    Uma chamada ao modelo só com os fatos da entrega (título, período, arquivos/áreas, prismas atravessados; mascarados
    no envio se `mascarar_modelo` estiver ligado).
    O prisma de cada avanço é sempre um dos prismas ativos da entrega. Sem modelo: erro claro e nada gravado.
    """
    pipeline.load_env()
    plan = pipeline.load_state().get('plano', {})
    jogo.sincronizar(plan)
    with trajetoria.abrir() as con:
        det = entregas.detalhe(con, int(entrega_id), incluir_leitura=False)
        if det is None:
            return {'erro': 'entrega não encontrada'}
        prog = jogo.luz(plan, con)['por_prisma']
        prismas = [p for p in det['prismas'] if p['prisma'] in prog]
        if not prismas:
            return {'erro': 'esta entrega não atravessa nenhum prisma ativo da sua trajetória'}
        abertos = [a for a in det['avancos_feitos'] if a.get('dimensao') in ('P3', 'P4') and a.get('estado') in jogo.ABERTOS]
        if {a['dimensao'] for a in abertos} >= {'P3', 'P4'}:
            return {'erro': 'esta entrega já tem centelhas P3 e P4 abertas', 'avancos': abertos, 'entrega': det}
        titulo = det['titulo']
        f = det['fatos']
        payload = {'entrega': {
            'titulo': titulo,
            'periodo': {'inicio': f['inicio'][:10], 'fim': f['fim'][:10], 'duracao_dias': f['duracao_dias']},
            'fatos': {'commits': f['commits'], 'arquivos': f['arquivos'], 'linhas': f['linhas'], 'areas': f['areas']},
            'prismas': [{'prisma': p['prisma'], 'termos': p['termos']} for p in prismas],
        }}
    t0 = time.perf_counter()
    try:
        result, record = pipeline.run_plan(payload, prep_seconds=time.perf_counter() - t0, label=rotulo,
                                           save_current_state=False, schema=planner.ENTREGA_SCHEMA,
                                           intro='Fatos medidos no git de uma entrega da pessoa:')
    except Exception as e:  # sem modelo, sem chave ou sem internet
        arquivos.registrar_erro('cli.acender_entrega', e)
        return {'erro': f'não deu para acender centelhas sem o modelo ({modelo.resumo_erro(e)})', 'entrega': det}
    brutas = [a for a in ((result.plan or {}).get('acoes') or []) if isinstance(a, dict) and a.get('titulo')]
    if len(brutas) < 2:
        return {'erro': 'o modelo não devolveu as 2 centelhas; tente de novo', 'entrega': det}
    p3, p4 = brutas[0], brutas[1]  # pelo esquema: a primeira é a P3 e a segunda a P4 (a posição manda)
    nomes_entrega = [p['prisma'] for p in prismas]
    nomes = list(prog)
    quando = jogo.agora()
    ids = []
    with trajetoria.abrir() as con, banco.transacao(con):
        for dim, a in (('P3', p3), ('P4', p4)):
            prisma = jogo.skill_de(str(a.get('skill') or ''), plan, nomes)
            prisma = prisma if prisma in nomes_entrega else nomes_entrega[0]
            novo = {**a, 'titulo': str(a['titulo']).strip()[:120], 'dimensao': dim,
                    'skill': prisma, 'skill_plano': prisma, 'origem': 'entrega', 'entrega': titulo,
                    'entrega_id': int(det['id']), 'estado': 'refletida', 'criado_em': quando,
                    'onde': f"entrega #{det['id']}"}  # o agente aplicou o conceito nesta entrega: a luz nasce refletida
            novo['id'] = acoes.aid('entrega', f"{det['id']}|{dim}|{novo['titulo']}")
            novo['valor_lm'], novo['conta'] = jogo.valor(novo, plan, prog, nomes)
            jogo._inserir_avanco(con, novo)
            ids.append(novo['id'])
    with trajetoria.abrir() as con:
        gerados = [jogo._um(i, con) for i in ids]
    return {'entrega': det, 'avancos': [g for g in gerados if g], 'record': record}


# ------------------------------------------------------------------ apresentação
# Voz (ux/auditoria.md): números antes de palavras, plural correto, nome curto do prisma, botões com verbo.
VERBOSE = False  # `--verbose`: mostra o rodapé técnico (tempo, memória, tokens) depois de cada chamada ao modelo
MESES = ('jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez')


def footer(rec: dict, hits: dict | None = None) -> None:
    if not VERBOSE:
        return
    masked = sum((hits or {}).values())
    print(
        f"\n`{rec.get('tempo_total_s', '?')} s · {rec.get('pico_memoria_mib', '?')} MiB · "
        f"{rec.get('tokens_entrada', '?')}→{rec.get('tokens_saida', '?')} tokens"
        f" · {masked} itens mascarados · {rec.get('modelo', '')} · versão {rec.get('versao', '?')}`"
    )


def curto(nome: str, n: int = 44) -> str:
    base = (nome or '').split('(')[0].strip()
    return base if len(base) <= n else base[: n - 1] + '…'


def nome_prisma(nome: str) -> str:
    """Nome curto do prisma, o mesmo do painel (`prismas.nome_curto`)."""
    return prismas.nome_curto(nome or '')


def titulo_curto(titulo: str, n: int = 32) -> str:
    t = ' '.join(str(titulo or '').split())
    return t if len(t) <= n else t[: n - 1].rstrip() + '…'


def plural(n, um: str, varios: str | None = None) -> str:
    return f"{n} {um if n == 1 else (varios or um + 's')}"


def numero(n) -> str:
    return f'{int(n or 0):,}'.replace(',', '.')


def data_curta(iso: str | None) -> str:
    """'2026-11-12' → '12 nov' (com o ano quando não é o ano corrente)."""
    s = str(iso or '')
    if len(s) < 10 or not s[:4].isdigit():
        return ''
    try:
        ano, mes, dia = int(s[:4]), int(s[5:7]), int(s[8:10])
        rot = f'{dia} {MESES[mes - 1]}'
    except (ValueError, IndexError):
        return s[:10]
    return rot if str(ano) == jogo.agora()[:4] else f'{rot} {ano}'


def periodo_curto(inicio: str | None, fim: str | None) -> str:
    a, b = str(inicio or '')[:10], str(fim or inicio or '')[:10]
    if not a:
        return ''
    if a == b:
        return data_curta(a)
    if a[:7] == b[:7]:
        return f'{int(a[8:10])}–{data_curta(b)}'
    return f'{data_curta(a)} – {data_curta(b)}'


# ------------------------------------------------------------------ botões (protocolo para qualquer agente)
def botoes(itens: list[dict], pergunta: str = 'Próximo passo?') -> None:
    vistos, lista = set(), []
    for b in itens:
        if b and b['rodar'] not in vistos:
            vistos.add(b['rodar'])
            lista.append(b)
    if not lista:
        lista = [BT_PAINEL]
    print(f'\nLUZIA_CLI={CLI}')
    print(f'LUZIA_PERGUNTA={pergunta}')
    print('LUZIA_BOTOES=' + json.dumps(lista[:3], ensure_ascii=False))


def bt_feixe(f: dict, prefixo: str | None = None) -> dict:
    """Botão que abre a centelha (`fazer`): continuar quando já converte, converter quando é luz refletida, acender no resto."""
    if prefixo is None:
        prefixo = {'convertendo': 'Continuar: ', 'refletida': 'Converter: '}.get(f.get('estado'), 'Acender: ')
    return {'rotulo': prefixo + titulo_curto(f.get('titulo', '')),
            'descricao': f"{f.get('tipo', '')} · {nome_prisma(f.get('skill_plano') or f.get('skill', ''))} · "
                         f"{f.get('duracao_min', '?')} min · {f.get('valor_lm')} lm",
            'rodar': f"fazer {f['id']}"}


def bt_confirmar(f: dict) -> dict:
    return {'rotulo': 'Acender luz própria', 'descricao': f"{f.get('valor_lm')} lm · {titulo_curto(f.get('titulo', ''), 30)}",
            'rodar': f"confirmar {f['id']}"}


def bt_converter(f: dict) -> dict:
    """O botão certo para a centelha: o sim da pessoa quando a Luzia já confirmou, senão continuar ou converter."""
    return bt_confirmar(f) if f.get('estado') == 'convertendo' and f.get('confirmada_em') else bt_feixe(f)


BT_PAINEL = {'rotulo': 'Abrir painel', 'descricao': 'mapa completo no navegador', 'rodar': 'career-map'}
BT_TRAJETORIA = {'rotulo': 'Ver trajetória', 'descricao': 'luz própria de cada prisma', 'rodar': 'trajetoria'}
BT_CONVERTER = {'rotulo': 'Ver centelhas para converter', 'descricao': 'luz refletida e conversões em curso',
                'rodar': 'centelhas --estado converter'}


def proximos_botoes(plan: dict, excluir: set | tuple = ()) -> list[dict]:
    """O que faz sentido agora, em ordem: continuar a conversão, converter luz refletida, acender, próxima por acender."""
    lista = [f for f in acoes.todas(plan) if f['id'] not in excluir]
    bts = [bt_converter(f) for f in lista if f['estado'] == 'convertendo'][:1]
    bts += [bt_feixe(f) for f in lista if f['estado'] == 'refletida'][:1]
    prismas_luz = jogo.luz(plan)['prismas']
    compostos = [p['nome'] for p in prismas_luz if prismas.composto(p['nome'])]
    if compostos:  # um prisma = uma habilidade: oferece separar os que juntam assuntos
        bts.append({'rotulo': 'Separar prismas compostos', 'descricao': f"{len(compostos)} juntam assuntos · luz e meta herdadas",
                    'rodar': 'dividir-todos'})
    abertos = {f.get('skill_plano') or f.get('skill') for f in lista if f['estado'] in jogo.ABERTOS}
    bts += [{'rotulo': f"Acender 3 de {nome_prisma(p['nome'])}", 'descricao': 'sem centelha aberta · ~10 s',
             'rodar': f'trecho "{p["nome"]}"'} for p in prismas_luz if not p['na_meta'] and p['nome'] not in abertos][:1]
    bts += [bt_feixe(f) for f in lista if f['estado'] == 'apagada']
    return bts or [BT_PAINEL]


ESTADO_IC = {'propria': '✦', 'convertendo': '◐', 'refletida': '◑', 'apagada': '○', 'descartada': '✕'}


def feixe_linha(f: dict) -> str:
    """Uma centelha em uma linha (para listas dentro de outras telas)."""
    extra = f" · nota {f.get('nota')}/4" if f.get('estado') == 'propria' and f.get('nota') is not None else ''
    tent = f" · {f.get('tentativas') + 1}ª tentativa" if f.get('tentativas') and f.get('estado') == 'convertendo' else ''
    sk = f.get('skill_plano') or f.get('skill', '')
    return (f"{ESTADO_IC.get(f.get('estado'), '○')} **{f.get('titulo', '')}** · {f.get('tipo', '')} · "
            f"{nome_prisma(sk)} · {f.get('duracao_min', '?')} min · {f.get('valor_lm', '?')} lm{extra}{tent} `#{f['id']}`")


def centelha_txt(f: dict) -> str:
    """Uma centelha em duas linhas: o estado com o título, depois tipo, prisma, lm e id."""
    sk = f.get('skill_plano') or f.get('skill', '')
    est = f.get('estado')
    return (f"{ESTADO_IC.get(est, '○')} {jogo.ROTULO_ESTADO.get(est, '')} · **{f.get('titulo', '')}**\n"
            f"  {f.get('tipo', '')} · {nome_prisma(sk)} · {f.get('valor_lm', '?')} lm · #{f['id']}")


def onde_txt(f: dict) -> str:
    if f.get('onde'):
        return f"Apareceu em {f['onde']}"
    return (origem_tag(f) or 'da meta').capitalize()


def origem_tag(a: dict) -> str:
    """Origem da centelha (o mesmo rótulo do painel): da sessão, da triagem ou da entrega."""
    o = str(a.get('origem') or '').lower()
    if a.get('entrega_id') or (o == 'entrega' and not a.get('da_triagem')):
        return 'da entrega'
    if a.get('da_triagem') or o in ('rota', 'triagem', 'entrega'):
        return 'da triagem'
    if o in ('sessão', 'sessao', 'guardada', 'lampejo', 'cartao', 'chat'):
        return 'da sessão'
    return ''


def oferecer(lista: list[dict], pergunta: str = 'Próximo passo?') -> None:
    botoes([bt_feixe(a) for a in lista if a.get('estado') not in ('propria', 'descartada')] or [BT_PAINEL], pergunta)


def linha_rota(plan: dict, state: dict | None = None) -> dict:
    """A trajetória em uma linha: `Júnior 3 → Plena  ███▓▒▒░░░░░░  62% seu`."""
    jogo.sincronizar(plan)  # as centelhas do plano entram no catálogo antes de somar a luz
    t = jogo.luz(plan)
    ini, fim = pipeline.rotulos(state or pipeline.load_state())
    print(f"{ini} → {fim}  {barra_total(t)}  {t['pct']}% seu")
    return t


def prisma_linhas(p: dict) -> list[str]:
    """Duas linhas por prisma: o nome com a barra e o %, depois o que falta."""
    out = [f"{nome_prisma(p['nome'])}  {barra_de(p)}  {p['pct']}%"]
    if p['na_meta']:
        out.append('   Na meta · tudo é luz própria')
    elif not p['n']:
        out.append('   Nenhuma centelha ainda · acenda 3 para começar')
    else:
        out.append(f"   {p['propria']} de {p['tot']} lm · {p['n_converter']} para converter · {p['n_apagada']} por acender"
                   + (' · meta por decidir' if p.get('meta_estado') == 'a_propor' else ''))
    return out


def rota_texto(plan: dict, state: dict | None = None) -> dict:
    t = linha_rota(plan, state)
    with trajetoria.abrir() as con:
        leit_map = {p['nome']: leituras.obter(con, 'prisma', p['nome']) for p in t['prismas']}
    for p in t['prismas']:
        for linha in prisma_linhas(p):
            print(linha)
        print('   ' + leitura_txt(leit_map.get(p['nome'])))
    return t


def base_resumo(alvo_tipo: str | None, base: dict | None) -> str:
    """Os fatos que fundamentaram uma leitura, em uma linha (o que vai depois de "base:")."""
    b = base if isinstance(base, dict) else {}
    if alvo_tipo == 'prisma':
        lz = b.get('luz') or {}
        return (f"{lz.get('pct', 0)}% de luz própria ({lz.get('propria', 0)} de {lz.get('tot', 0)} lm), "
                f"{plural(len(b.get('avancos_conquistados') or []), 'centelha própria', 'centelhas próprias')}, "
                f"{plural(b.get('entregas_total', 0), 'entrega')}")
    if alvo_tipo == 'entrega':
        f = b.get('fatos') or {}
        return (f"{plural(f.get('commits', 0), 'commit')}, {plural(f.get('arquivos', 0), 'arquivo')}, "
                f"{plural(f.get('linhas', 0), 'linha')}, {plural(len(b.get('prismas') or []), 'prisma')}")
    if alvo_tipo == 'pedido':
        return (f"o pedido ({b.get('tipo', '')} em {nome_prisma(b.get('prisma', ''))}) e a trajetória atual "
                f"({plural(len(b.get('prismas_ativos') or []), 'prisma ativo', 'prismas ativos')})")
    return 'os fatos medidos pela Luzia'


def bt_leituras() -> dict | None:
    """'Atualizar N leituras' quando há leituras vencidas (ou faltando) e um modelo configurado."""
    if not modelo.pronto():
        return None
    with trajetoria.abrir() as con:
        n = len(leituras.vencidas(con, leituras.ENTREGAS_RELEVANTES))
    return {'rotulo': f"Atualizar {plural(n, 'análise')}", 'descricao': 'base mudou · até 8 por chamada',
            'rodar': 'leituras'} if n else None


def com_leituras(bts: list[dict]) -> list[dict]:
    """O botão de leituras entra em 2º lugar (só 3 botões aparecem): o primeiro passo continua sendo o primeiro."""
    extra = bt_leituras()
    return [*bts[:1], extra, *bts[1:]] if extra else bts


def motivo_sem_leitura() -> str:
    return ('sem análise ainda' if modelo.pronto()
            else 'sem análise: falta configurar o modelo (`modelo`, ou Ajustes no painel)')


def leitura_txt(leit: dict | None, base_txt: str | None = None, indisponivel: str = '') -> str:
    """Toda leitura de IA na tela: o texto primeiro e a assinatura curta com base, data e modelo; sem leitura, diz
    por quê (nunca vazio)."""
    if leit and leit.get('texto') and leit.get('modelo'):
        base_txt = base_txt or base_resumo(leit.get('alvo_tipo'), leit.get('base'))
        venc = ' · desatualizada' if leit.get('vencida') else ''
        data = data_curta(leit.get('criado_em')) or 'data desconhecida'
        return f"{leit['texto']} _— Análise da Luzia, {data} · base: {base_txt} · {leit['modelo']}{venc}_"
    motivo = indisponivel or motivo_sem_leitura()
    if indisponivel and not motivo.lower().startswith('sem análise'):
        motivo = 'sem análise: ' + motivo.replace('leitura indisponível: ', '').replace('análise indisponível: ', '')
    return f"_{motivo[:1].upper()}{motivo[1:]}._"


NOME_DIMENSAO = {'P1': 'Direção no prompt', 'P2': 'Coesão', 'P3': 'Aplicação de conceito', 'P4': 'Decisão de arquitetura'}
SEM_BASE_DIMENSAO = {'P1': 'sem base ainda (a triagem não leu seus prompts)',
                     'P2': 'sem base ainda (a entrega não tem commits medidos)',
                     'P3': 'falta você explicar',
                     'P4': 'falta você defender'}


def dims_medidas(prop: dict) -> str:
    ks = [k for k in ('P1', 'P2', 'P3', 'P4') if (prop.get('dimensoes') or {}).get(k)]
    if not ks:
        return ''
    if len(ks) == 4:
        return 'P1 a P4'
    return ks[0] if len(ks) == 1 else f"{', '.join(ks[:-1])} e {ks[-1]}"


def linhas_propriedade(prop: dict) -> list[str]:
    """P1–P4 de uma entrega com a base de cada nota (o mesmo que o painel mostra no detalhe)."""
    indice = prop.get('indice')
    medidas = dims_medidas(prop)
    out = [f"**{indice}% seu** (medido em {medidas})" if indice is not None and medidas
           else '**Propriedade:** ainda sem medida']
    for k in ('P1', 'P2', 'P3', 'P4'):
        d = (prop.get('dimensoes') or {}).get(k)
        if d:
            out.append(f"- {k} {NOME_DIMENSAO[k]}: **{d['nota']}** ({d.get('tipo', '')})"
                       + (f" — {d['base']}" if d.get('base') else ''))
        else:
            out.append(f"- {k} {NOME_DIMENSAO[k]}: — {SEM_BASE_DIMENSAO[k]}")
    return out


# ------------------------------------------------------------------ painel
def identidade_do_painel() -> tuple[str, dict]:
    """('ok', ping) quando quem responde em PAINEL prova o segredo de `private/painel.json` (HMAC de um desafio novo);
    ('ausente', {}) quando ninguém responde; ('estranho', {}) quando algo responde sem a prova (outro programa na porta,
    ou um painel de uma versão antiga da Luzia). O segredo nunca sai desta máquina nem vai na pergunta."""
    desafio = secrets.token_hex(16)
    try:
        with urllib.request.urlopen(f'{PAINEL}/api/ping?desafio={desafio}', timeout=2) as r:
            resposta = json.loads(r.read().decode('utf-8') or '{}')
    except Exception:
        return 'ausente', {}
    ident = arquivos.ler_json(arquivos.PRIVATE / 'painel.json', {})
    segredo = ident.get('segredo') if isinstance(ident, dict) else None
    prova = resposta.get('prova') if isinstance(resposta, dict) else None
    try:
        esperada = hmac.new(bytes.fromhex(segredo), desafio.encode('ascii'), hashlib.sha256).hexdigest()
    except (TypeError, ValueError):
        return 'estranho', {}
    if not isinstance(prova, str) or not hmac.compare_digest(prova, esperada):
        return 'estranho', {}
    return 'ok', resposta


def start_panel() -> None:
    lancador = Path(__file__).resolve().parent / 'lz.py'  # funciona também na cópia do plugin (pasta sem o nome luzia)
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
    subprocess.Popen(
        [sys.executable, str(lancador), 'server'], cwd=str(pipeline.ROOT),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, creationflags=flags,
    )
    for _ in range(20):
        if identidade_do_painel()[0] == 'ok':
            return
        time.sleep(0.3)


def _encerrar_painel(pid) -> None:
    """Encerra o painel que provou a identidade mas roda código antigo (o PID veio do ping autenticado). Nunca este
    processo nem um PID inválido; espera a porta ficar livre."""
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0 or pid == os.getpid():
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as e:
        arquivos.registrar_erro('cli encerrar painel antigo', e)
        return
    for _ in range(20):
        if identidade_do_painel()[0] == 'ausente':
            return
        time.sleep(0.25)


def _sem_tela() -> bool:
    """Sessão remota (SSH) ou POSIX sem servidor gráfico: o navegador "abre" sem ninguém ver; o link vai para o chat."""
    if os.environ.get('SSH_CONNECTION') or os.environ.get('SSH_TTY'):
        return True
    if sys.platform in ('win32', 'darwin'):
        return False
    return not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))


def set_mode(modo: str) -> None:
    observer.definir_modo(modo)


def roteiro(a: dict) -> None:
    print(f"## Luzia · Convertendo `#{a['id']}` · **{a.get('valor_lm')} lm**")
    print(f"**{a.get('titulo', '')}** · {a.get('tipo', '')} · {nome_prisma(a.get('skill_plano') or a.get('skill', ''))} · {a.get('duracao_min', '?')} min")
    if a.get('conta'):
        print('Vale: ' + ' + '.join(f"{c[0]} {c[2]} ({c[1]})" for c in a.get('conta', [])))
    if a.get('da_triagem'):
        print('▸ da triagem')
    elif origem_tag(a) == 'da sessão':
        print('▸ da sessão')
    elif a.get('entrega'):
        print(f"▸ {'Entrega #' + str(a['entrega_id']) if a.get('entrega_id') else 'Entrega: ' + str(a['entrega'])}"
              + (f" · prova {a['dimensao']}" if a.get('dimensao') else ''))
    if a.get('onde'):
        print(f"▸ Apareceu em {a['onde']}")
    print(f"\n**Por quê:** {a.get('por_que') or a.get('porque', '')}")
    if a.get('conceitos'):
        print(f"**Conceitos:** {', '.join(a.get('conceitos', []))}")
    como = a.get('como') or a.get('guia') or []
    if como:
        print('**Passo a passo:**')
        for i, p in enumerate(como, 1):
            print(f'{i}. {p}')
    if a.get('onde_explorar'):
        print(f"**Onde olhar:** {a['onde_explorar']}")
    print('\n---\nROTEIRO PARA O AGENTE (conduza como a Luzia, sem fazer o trabalho no lugar da pessoa):')
    print('1. Mostre a centelha acima de forma curta, com o valor em lúmens.')
    print(f"2. Siga este pedido da pessoa: «{a.get('prompt') or a.get('titulo', '')}»")
    print('3. Faça UMA pergunta por vez e espere a resposta. Se a ação pede explorar o repositório, mostre só 2 lugares.')
    print('4. Avalie a resposta final pela rubrica 0–4: ' + ' · '.join(f'{k} = {v}' for k, v in propriedade.RUBRICA.items())
          + '. Nota 3 ou 4 confirma o entendimento; 0 a 2 pede outra tentativa, com uma dica do que faltou.')
    print('5. Diga a nota e o porquê em uma linha, com um ponto forte e um próximo passo.')
    print(f'6. Registre: {CLI} registrar {a["id"]} --nota <0-4> --resumo "<1 linha do que a pessoa demonstrou>"')
    print(f'7. Com nota 3 ou 4, pergunte se a pessoa quer acender a luz própria. Só com o sim dela rode: {CLI} confirmar {a["id"]}')
    print('8. A saída de registrar e de confirmar termina com LUZIA_BOTOES: ofereça esses botões como próxima ação.')


def hoje(plan: dict, state: dict) -> None:
    """Ponto de partida: a trajetória, a centelha que mais vale converter e os próximos passos em botões."""
    print('## Luzia · Hoje')
    t = linha_rota(plan, state)
    lista = acoes.todas(plan)
    conv = sorted((f for f in lista if f['estado'] in jogo.PARA_CONVERTER),
                  key=lambda f: (0 if f['estado'] == 'convertendo' else 1, -int(f.get('valor_lm') or 0)))
    hoje_lm = sum(x['lm'] for x in jogo.livro(desde=jogo.agora()[:10]) if x.get('luz') == 'propria')
    partes = [plural(len(conv), 'centelha para converter', 'centelhas para converter'),
              f"{sum(int(f.get('valor_lm') or 0) for f in conv)} lm"]
    if hoje_lm:
        partes.append(f'+{hoje_lm} lm hoje')
    if acoes.fila():
        partes.append(f'{len(acoes.fila())} na fila')
    print(' · '.join(partes))
    metas = [p for p in t['prismas'] if p.get('meta_estado') == 'a_propor']
    if not conv:
        print('Nada para converter agora. Uma centelha por acender vira luz refletida quando o agente a aplica.')
        botoes(com_leituras(proximos_botoes(plan) + [BT_PAINEL]), 'Próximo passo?')
        return
    top = conv[0]
    print(f"\n{ESTADO_IC[top['estado']]} **{top.get('titulo', '')}**")
    print(f"  {onde_txt(top)} · {top.get('tipo', '')} · {top.get('duracao_min', '?')} min · +{top.get('valor_lm')} lm")
    if top.get('confirmada_em'):
        print('  A Luzia confirmou seu entendimento. Falta o seu sim.')
    for f in conv[1:3]:
        print(centelha_txt(f))
    bts = [bt_converter(top), BT_CONVERTER]
    bts += [{'rotulo': f"Decidir a meta de {nome_prisma(p['nome'])}", 'descricao': 'a meta ainda não tem centelhas',
             'rodar': 'trajetoria'} for p in metas][:1]
    botoes(com_leituras(bts + [BT_PAINEL]), 'Próximo passo?')


def _botoes_pedido(pid: int, p: dict) -> list[dict]:
    prop = p.get('proposta') or {}
    bts = [{'rotulo': f'Aceitar pedido #{pid}', 'descricao': f"aplica a mudança em {nome_prisma(p['prisma'])}",
            'rodar': f'pedido aceitar {pid}'}]
    if p.get('tipo') == 'dividir':
        bts.append({'rotulo': f'Ajustar pedido #{pid}',
                    'descricao': 'renomear uma habilidade ou mover uma centelha para outra',
                    'rodar': f'pedido ajustar {pid}'})  # sem valores: a Luzia pergunta o que mudar
    if p.get('tipo') in ('incluir', 'mudar_meta'):  # arquivar e reativar não têm nível nem meta a ajustar
        bts.append({'rotulo': f'Ajustar pedido #{pid}',
                    'descricao': f"proposta: {prop.get('nivel_partida', 1)} → meta {prop.get('meta', 3)}",
                    'rodar': f'pedido ajustar {pid}'})  # sem valores: a Luzia pergunta o novo nível e a nova meta
    bts.append({'rotulo': f'Recusar pedido #{pid}', 'descricao': 'a trajetória fica como está',
                'rodar': f'pedido recusar {pid}'})
    return bts


def _id_pedido(extras: list[str], sub: str) -> int:
    if not extras or not str(extras[0]).lstrip('#').isdigit():
        raise ValueError(f'informe o número do pedido: `pedido {sub} <número>`')
    return int(str(extras[0]).lstrip('#'))


def _print_proposta(p: dict) -> None:
    proposta = p.get('proposta') or {}
    if not proposta:
        return
    if p.get('tipo') == 'dividir':
        partes = proposta.get('partes') or []
        print(f"- **Proposta da Luzia:** {len(partes)} prismas de uma habilidade só, cada um herda o "
              f"**nível {proposta.get('nivel_partida')} → meta {proposta.get('meta')}/5**; o prisma antigo é arquivado "
              'com os lúmens dele (o progresso do nível novo conta a partir do aceite)')
        for x in partes:
            print(f"  - **{x['nome']}** · nível {x['nivel']} → meta {x['meta']} · palavras: {', '.join(x.get('palavras', [])[:6])}")
        for a in proposta.get('avancos') or []:
            print(f"  - Centelha `#{a['id']}` {a.get('titulo', '')} ({a.get('estado', '')}) → **{a['para']}**"
                  + (' (você moveu)' if a.get('movido') else ''))
        return
    ganho = int(proposta.get('ganho_niveis') or 0)
    print(f"- **Proposta da Luzia:** nível **{proposta.get('nivel_partida')} → meta {proposta.get('meta')}/5**"
          f" · a trajetória {'ganha' if ganho >= 0 else 'perde'} {plural(abs(ganho), 'nível', 'níveis')}")
    if p.get('tipo') in ('incluir', 'mudar_meta'):
        print('- **Análise do pedido:** ' + leitura_txt(p.get('leitura'), indisponivel=proposta.get('leitura_indisponivel', '')))
    for a in (proposta.get('acoes') or [])[:3]:
        print(f"  - Centelha inicial sugerida: **{a.get('titulo', '')}** ({a.get('tipo', '')})")


def _mover_de(itens: list[str] | None) -> dict[str, str]:
    """`--mover <avanço>=<habilidade>` (pode repetir) → {id do avanço: habilidade}; formato errado vira ValueError."""
    out = {}
    for item in itens or []:
        aid_, sep, parte = str(item).partition('=')
        if not sep or not aid_.strip() or not parte.strip():
            raise ValueError(f'use --mover <avanço>="<habilidade>" (recebi {item!r})')
        out[aid_.strip().lstrip('#').lower()] = parte.strip().strip('"')
    return out


def cmd_dividir(args, plan: dict, todos: bool = False) -> None:
    """Um prisma = uma habilidade: abre o pedido `dividir` (um prisma, ou todos os compostos) e mostra a proposta."""
    with trajetoria.abrir() as con:
        try:
            if todos:
                lista = pedidos.dividir_todos(con)
            else:
                nome = (args.valor or args.prisma or args.skill or '').strip()
                if not nome:
                    raise ValueError('informe o prisma: `dividir "<prisma>"` (ou `dividir-todos`)')
                p = pedidos.abrir(con, 'dividir', nome, args.motivo if args.motivo != 'nao_faz_sentido' else '')
                lista = [pedidos.propor(con, p['id'])]
        except (ValueError, RuntimeError) as e:
            print(f'Não foi possível dividir: {e}.')
            botoes([BT_TRAJETORIA, BT_PAINEL], 'Próximo passo?')
            return
    if not lista:
        print('Todos os seus prismas já são de uma habilidade só (ou já têm um pedido de divisão em aberto).')
        botoes([BT_TRAJETORIA, BT_PAINEL])
        return
    print('## Luzia · Dividir prismas')
    bts: list[dict] = []
    for p in lista:
        print(f"\n**Pedido `#{p['id']}`** · dividir **{p['prisma']}** (estado: **{p['estado']}**)")
        if p.get('erro'):
            print(f"- {p['erro']}: ajuste os nomes com `pedido ajustar {p['id']} --partes ...`.")
        _print_proposta(p)
        if len(bts) < 4:
            bts.extend(b for b in _botoes_pedido(p['id'], p) if 'Recusar' not in b['rotulo'])
    botoes(bts[:4] + [BT_PAINEL], 'Decide o pedido?')


def cmd_pedido(args, restantes: list[str], plan: dict) -> None:
    """Pedido de mudança pelo chat; todo erro vira uma mensagem clara terminando em botões (nunca traceback)."""
    sub = (args.valor or (restantes[0] if restantes else '')).strip().lower()
    extras = restantes[1:] if args.valor and restantes and restantes[0] == args.valor else list(restantes)
    with trajetoria.abrir() as con:
        try:
            _pedido(con, sub, extras, args)
        except (ValueError, RuntimeError) as e:
            print(f'Não foi possível concluir o pedido: {e}.')
            abertos = [x for x in pedidos.listar(con)  # o pedido que já está aberto para este prisma, se for o caso
                       if x['estado'] in ('aberto', 'proposto') and str(e).endswith(f"prisma {x['prisma']}")]
            bts = _botoes_pedido(abertos[0]['id'], abertos[0]) if abertos else []
            botoes(bts + [BT_TRAJETORIA, BT_PAINEL], 'Decide o pedido?')


def _pedido(con, sub: str, extras: list[str], args) -> None:
    if sub == 'abrir':
        if len(extras) < 2:
            print('Informe o tipo e o prisma: `pedido abrir <incluir|arquivar|reativar|mudar_meta> "<prisma>" --motivo "..."`')
            botoes([BT_TRAJETORIA, BT_PAINEL])
            return
        tipo, nome_pedido = extras[0], extras[1]
        motivo = args.motivo if args.motivo != 'nao_faz_sentido' else ''
        p = pedidos.abrir(con, tipo, nome_pedido, motivo)
        if tipo in ('incluir', 'mudar_meta', 'dividir'):
            p = pedidos.propor(con, p['id'], nivel=args.nivel, meta=args.meta)
        print(f"✦ **Pedido `#{p['id']}` aberto** · {p['tipo']} · **{nome_prisma(p['prisma'])}** · {p['estado']}")
        if p.get('motivo'):
            print(f"- **Motivo:** {p['motivo']}")
        _print_proposta(p)
        botoes(_botoes_pedido(p['id'], p), 'Decide o pedido?')
        return

    if sub == 'ajustar':
        pid = _id_pedido(extras, sub)
        atual = next((x for x in pedidos.listar(con) if x['id'] == pid), None)
        if atual is not None and atual['estado'] in ('aberto', 'proposto') and atual['tipo'] == 'dividir':
            mover = _mover_de(args.mover)
            if not args.partes and not mover:  # pergunta o que mudar em vez de refazer a mesma proposta
                nomes = ' '.join(f'"{x["nome"]}"' for x in (atual.get('proposta') or {}).get('partes') or [])
                print(f"O que você quer mudar na divisão de {atual['prisma']}? Diga os nomes das habilidades ou para "
                      f"qual delas vai uma centelha, e a Luzia roda `pedido ajustar {pid} --partes {nomes}` "
                      f'ou `pedido ajustar {pid} --mover <avanço>="<habilidade>"`.')
                _print_proposta(atual)
                botoes([b for b in _botoes_pedido(pid, atual) if 'Ajustar' not in b['rotulo']],
                       'Ajustar a divisão? Responda no chat, ou decida já:')
                return
            p = pedidos.propor(con, pid, partes=args.partes or None, mover=mover)
            print(f"✦ **Pedido `#{pid}` ajustado** · dividir **{p['prisma']}** (estado: **{p['estado']}**)")
            _print_proposta(p)
            botoes(_botoes_pedido(pid, p), 'Decide o pedido?')
            return
        if atual is not None and atual['estado'] in ('aberto', 'proposto'):
            if atual['tipo'] not in ('incluir', 'mudar_meta'):
                print(f"O pedido `#{pid}` ({atual['tipo']}) não tem nível nem meta a ajustar: aceite ou recuse.")
                botoes(_botoes_pedido(pid, atual), 'Decide o pedido?')
                return
            if args.nivel is None and args.meta is None:  # nunca reenvia os mesmos valores: pergunta os novos
                prop = atual.get('proposta') or {}
                print(f"Qual nível de partida (0 a 5) e qual meta (1 a 5) você quer para o {atual['prisma']}? "
                      f"Hoje a proposta é nível {prop.get('nivel_partida', '?')} → meta {prop.get('meta', '?')}. "
                      f"Diga os dois números e a Luzia roda `pedido ajustar {pid} --nivel <0-5> --meta <1-5>`.")
                botoes([b for b in _botoes_pedido(pid, atual) if 'Ajustar' not in b['rotulo']],
                       'Ajustar para qual nível e meta? Responda no chat, ou decida já:')
                return
        p = pedidos.propor(con, pid, nivel=args.nivel, meta=args.meta)
        print(f"✦ **Pedido `#{pid}` ajustado** · **{p['prisma']}** (estado: **{p['estado']}**)")
        _print_proposta(p)
        botoes(_botoes_pedido(pid, p), 'Decide o pedido?')
        return

    if sub == 'aceitar':
        pid = _id_pedido(extras, sub)
        p = pedidos.aceitar(con, pid)
        plan = pipeline.load_state().get('plano', {})
        print(f"✦ **Pedido `#{pid}` aceito** · trajetória v{p.get('versao', '?')} criada ({p['tipo']} · "
              f"{nome_prisma(p['prisma'])}).")
        botoes([BT_TRAJETORIA, *proximos_botoes(plan)[:2]], 'Próximo passo?')
        return

    if sub == 'recusar':
        pid = _id_pedido(extras, sub)
        pedidos.recusar(con, pid)
        print(f"Pedido `#{pid}` recusado. A trajetória fica como está.")
        botoes([BT_TRAJETORIA, BT_PAINEL])
        return

    lista = pedidos.listar(con)
    if not lista:
        print('Nenhum pedido de mudança.')
        botoes([BT_TRAJETORIA, BT_PAINEL])
        return
    print('## Luzia · Pedidos')
    bts: list[dict] = []
    for p in lista[:5]:
        print(f"- `#{p['id']}` · {p['tipo']} · **{nome_prisma(p['prisma'])}** · {p['estado']}"
              + (f" ({p['motivo']})" if p.get('motivo') else ''))
        if p['estado'] in ('aberto', 'proposto') and not bts:
            bts.extend(_botoes_pedido(p['id'], p))
    botoes(bts or [BT_TRAJETORIA, BT_PAINEL], 'Decide o pedido?' if bts else 'Próximo passo?')


BT_IDENTIDADE = {'rotulo': 'Conferir e-mails do git', 'descricao': 'nomes e e-mails dos seus commits',
                 'rodar': 'identidade'}


def linhas_diagnostico(diag: dict, aviso: str = '') -> list[str]:
    """Por que não apareceu entrega: só fatos (repositório, identidades, janela), sem leitura de IA."""
    ids = diag.get('identidades') or []
    janela = (f"desde {data_curta(diag['janela_desde'])} · lida em {data_curta(diag['ultima_leitura'])} · "
              f"{plural(diag.get('commits_seus', 0), 'commit seu', 'commits seus')}") if diag.get('janela_desde') else 'ainda não lida'
    return [
        f"- **Repositório:** {'configurado' if diag.get('repo_configurado') else 'não configurado (rode /luzia:configurar)'}"
        + (f' · {aviso}' if aviso else ''),
        f"- **E-mails do git:** {', '.join(ids) if ids else 'nenhum (rode /luzia:configurar ou `identidade adicionar`)'}",
        f'- **Janela:** {janela}',
    ]


def cmd_entregas(args, state: dict) -> None:
    """Entregas detectadas no git, uma linha cada (a leitura fica no detalhe); sem entrega, um diagnóstico curto.
    Nunca as tarefas montadas pela IA."""
    dias = args.ampliar if args.ampliar > 0 else 90
    jogo.sincronizar(state.get('plano', {}))
    with trajetoria.abrir() as con:
        res = entregas.atualizar(con, dias=dias)
        lista = entregas.listar(con)
        todos = jogo.avancos(con) if lista else []
        props = {e['id']: (entregas.detalhe(con, e['id'], incluir_leitura=False, todos_avancos=todos) or {}).get('propriedade') or {}
                 for e in lista[:10]}
        diag = None if lista else entregas.diagnostico(con)

    print('## Luzia · Entregas')
    bts: list[dict] = []
    dias_amp = max(180, dias * 2)
    ampliar = {'rotulo': f'Buscar {dias_amp} dias', 'descricao': 'entregas mais antigas',
               'rodar': f'entregas --ampliar {dias_amp}'}
    if not lista:
        print('Nenhuma entrega encontrada.')
        for linha in linhas_diagnostico(diag, res.get('aviso', '')):
            print(linha)
        botoes([ampliar, BT_IDENTIDADE, BT_PAINEL], 'Próximo passo?')
        return
    for e in lista[:10]:
        fatos = e.get('fatos', {})
        prop = props.get(e['id']) or {}
        idx = prop.get('indice')
        nomes = [nome_prisma(p['prisma']) for p in e.get('prismas', [])]
        partes = [f"{idx}% seu" if idx is not None else 'sem medida',
                  plural(fatos.get('duracao_dias', 1), 'dia')]
        if nomes:
            partes.append(', '.join(nomes[:3]) + (f' +{len(nomes) - 3}' if len(nomes) > 3 else ''))
        print(f"▸ **#{e['id']} {e['titulo']}** · " + ' · '.join(partes))
        if len(bts) < 2:
            bts.append({'rotulo': f"Ver #{e['id']}", 'descricao': titulo_curto(e['titulo'], 40), 'rodar': f"entrega {e['id']}"})
    bts.append(ampliar)
    bts.append(BT_PAINEL)
    botoes(com_leituras(bts), 'Qual entrega?')


def cmd_leituras(todas: bool = False) -> None:
    """Renova as leituras vencidas (ou que faltam) de prismas e entregas, em lotes de até 8 por chamada."""
    with trajetoria.abrir() as con:
        vencidas = leituras.vencidas(con, None if todas else leituras.ENTREGAS_RELEVANTES)
        mais_antigas = 0 if todas else len(leituras.vencidas(con)) - len(vencidas)
    print('## Luzia · Análises')
    bts = [BT_TRAJETORIA, {'rotulo': 'Ver entregas', 'descricao': 'quanto de cada entrega é seu',
                           'rodar': 'entregas'}, BT_PAINEL]
    if not vencidas:
        print('Todas as análises estão em dia.')
    elif not modelo.pronto():
        print(f"{plural(len(vencidas), 'análise desatualizada', 'análises desatualizadas')} · "
              'sem análise: falta configurar o modelo (`modelo`, ou Ajustes no painel).')
    else:
        pipeline.load_env()
        with trajetoria.abrir() as con:
            n = leituras.gerar(con, vencidas)
        if n:
            resto = len(vencidas) - n
            print(f"✦ {plural(n, 'análise atualizada', 'análises atualizadas')}, cada uma com base, modelo e data."
                  + (f" {plural(resto, 'ficou', 'ficaram')} para depois (o modelo não respondeu a um lote): rode `analises` de novo."
                     if resto > 0 else ''))
        else:
            print(f"O modelo não respondeu e nada foi gravado "
                  f"({plural(len(vencidas), 'análise segue desatualizada', 'análises seguem desatualizadas')}).")
    if mais_antigas > 0:
        print(f"Mais {plural(mais_antigas, 'análise', 'análises')} de entregas antigas: `analises --todas` atualiza também.")
    botoes(bts, 'Próximo passo?')


def cmd_identidade(args, restantes: list[str]) -> None:
    """Confere (e acrescenta) os nomes e e-mails do git que a Luzia usa para achar os commits da pessoa."""
    sub = (args.valor or '').strip().lower()
    with trajetoria.abrir() as con:
        if sub == 'adicionar':
            try:
                entregas.acrescentar_identidade(con, ' '.join(restantes))
            except ValueError as e:
                print(f'Não foi possível acrescentar: {e}.')
                botoes([BT_IDENTIDADE, BT_PAINEL], 'Quer tentar de novo?')
                return
            print('✦ Adicionado. A próxima leitura das entregas refaz a janela inteira.')
        diag = entregas.diagnostico(con)
    print('## Luzia · Identidade')
    for linha in linhas_diagnostico(diag):
        print(linha)
    print('\nPara acrescentar um nome ou e-mail que você usa nos commits: '
          '`identidade adicionar "<nome ou e-mail>"`.')
    botoes([{'rotulo': 'Ler entregas de novo', 'descricao': 'com estes e-mails', 'rodar': 'entregas'},
            BT_PAINEL], 'Próximo passo?')


def cmd_entrega_detalhe(entrega_id: int, plan: dict) -> None:
    jogo.sincronizar(plan)
    with trajetoria.abrir() as con:
        det = entregas.detalhe(con, entrega_id)
    if not det:
        print(f'Entrega `#{entrega_id}` não encontrada.')
        botoes([{'rotulo': 'Ver entregas', 'descricao': 'lista de entregas', 'rodar': 'entregas'}, BT_PAINEL])
        return
    fatos = det['fatos']
    print(f"## Luzia · Entrega #{det['id']}")
    print(f"**{det['titulo']}** ({det['fonte']})")
    if det.get('ids'):
        print('- **PR/ticket:** ' + ' · '.join(f'#{i}' for i in det['ids']))
    print(f"- **Período:** {periodo_curto(fatos['inicio'], fatos['fim'])} ({plural(fatos['duracao_dias'], 'dia')})")
    print(f"- **Volume:** {plural(fatos['commits'], 'commit')} · {plural(fatos['arquivos'], 'arquivo')} · "
          f"+{numero(fatos['linhas'])} linhas · áreas: {', '.join(fatos['areas']) or 'n/d'}")
    if det['prismas']:
        print('- **Prismas:** ' + ', '.join(
            nome_prisma(p['prisma']) + (f" (termos: {', '.join(p['termos'])})" if p.get('termos') else '') for p in det['prismas']
        ))
    prop = det.get('propriedade') or {}
    print()
    for linha in linhas_propriedade(prop):
        print(linha)
    print('\n' + leitura_txt(det.get('leitura')))

    if det['avancos_feitos']:
        print('\n**Feitos para esta entrega**')
        for a in det['avancos_feitos']:
            print(f'   {feixe_linha(a)}' + (f" → prova {a['dimensao']}" if a.get('dimensao') else ''))
    if det['avancos_uteis']:
        print('\n**Centelhas que ajudam**')
        for a in det['avancos_uteis'][:3]:
            print(f'   {feixe_linha(a)}')
    if det['lumens_ligados']:
        soma_lm = sum(int(l['lm']) for l in det['lumens_ligados'])
        print(f"\n**Lúmens no período · {soma_lm} lm** ({plural(len(det['lumens_ligados']), 'registro')})")
        for l in det['lumens_ligados'][:5]:
            print(f"- +{l['lm']} {nome_prisma(l['prisma'])} · {l['luz']} · {l['fonte']} · {data_curta(l['quando'])}")

    dims = prop.get('dimensoes') or {}
    lacunas = [d for d in ('P3', 'P4') if not dims.get(d)]
    abertos = [a for a in det['avancos_feitos'] if a.get('dimensao') in lacunas and a.get('estado') in jogo.ABERTOS]
    bts = [bt_feixe(a) for a in abertos[:2]]
    if lacunas and {a['dimensao'] for a in abertos} < set(lacunas):
        bts.append({'rotulo': f"Provar {' e '.join(lacunas)}",
                    'descricao': '2 centelhas curtas ligadas a esta entrega · ~10 s',
                    'rodar': f"acender-entrega {det['id']}"})
    bts += [bt_feixe(a) for a in det['avancos_uteis'][:2]]
    bts.append({'rotulo': 'Ver entregas', 'descricao': 'lista de entregas', 'rodar': 'entregas'})
    bts.append(BT_PAINEL)
    botoes(bts, 'Próximo passo?')


def cmd_foco(args) -> None:
    """Foco para agentes sem hooks: o mesmo reconhecimento do observador (uma só implementação em `observer.foco`).

    O texto do pedido vem de um arquivo temporário (`--prompt-arquivo`) e o código vem do `git diff` dos caminhos de
    `--arquivos`; nada disso é gravado, só o evento mascarado (prisma, extensão, lúmens).
    """
    # A CLI roda em `cd <plugin> && python -m luzia.cli`: o projeto da pessoa vem de --cwd (padrão: a pasta atual).
    cwd = os.path.abspath(args.cwd or os.getcwd())
    caminhos = list(args.arquivos or [])
    saida_botoes = [BT_TRAJETORIA, BT_PAINEL]
    if not args.prompt_arquivo and not caminhos:
        print('Use `foco --prompt-arquivo <arquivo temporário com o pedido>` quando a pessoa pedir algo, ou '
              '`foco --arquivos <caminhos editados> --cwd <pasta do projeto>` depois de editar. Opcional: `--sessao <id>`.')
        botoes(saida_botoes)
        return
    situacao, _ = observer.situacao_do_foco(cwd)  # antes de ler qualquer prompt ou código
    if situacao == 'nao_autorizado':
        print('✦ Luzia · foco: esta pasta não está autorizada para o foco (veja `observer.json`). '
              'Nada foi lido, observado nem gravado.')
        botoes(saida_botoes)
        return
    if situacao == 'fora_de_foco':
        print('✦ Luzia · fora de foco: nada foi observado. Para voltar, `modo ativo`.')
        botoes([{'rotulo': 'Voltar ao foco', 'descricao': 'em foco, com centelhas da sessão', 'rodar': 'modo ativo'}, BT_TRAJETORIA])
        return
    try:
        if args.prompt_arquivo:
            origem, ext = 'prompt', 'prompt'
            texto = Path(args.prompt_arquivo).read_text(encoding='utf-8', errors='replace')
        else:
            origem, ext = 'agente', (Path(caminhos[0]).suffix.lower() or 'arquivo')
            texto = observer.adicionado_nos_arquivos(caminhos, cwd)
    except (OSError, RuntimeError) as e:
        print(f'◐ O foco não leu o que pediu: {e}.')
        botoes(saida_botoes)
        return
    r = observer.foco(origem, texto, cwd, args.sessao, ext)
    achados = [a for a in r['achados'] if a.get('mudou')]
    if not achados:
        print('✦ Luzia · foco: nenhuma centelha mudou de luz aqui (ou já foi reconhecida nesta sessão). '
              'Não há nada a mostrar à pessoa.')
        botoes(saida_botoes)
        return
    if r['modo'] == 'passivo':
        resumo = ', '.join(f"{a['titulo']} +{a['lm']} lm" for a in achados)
        print(f'✦ Luzia · em foco, em silêncio: {resumo}. Luz registrada; não é preciso avisar a pessoa.')
        botoes(saida_botoes)
        return
    if origem == 'prompt':
        for a in achados:
            print(f'[Luzia · em foco · luz própria] A pessoa DIRIGIU "{a["titulo"]}" ({a["skill"]}) neste pedido: a centelha '
                  f'#{a["centelha"]} virou luz própria (+{a["lm"]} lm). Responda normalmente e, no FIM, em UMA linha: '
                  f'"✦ Luzia · {nome_prisma(a["skill"])}: você dirigiu {a["titulo"]} · +{a["lm"]} lm de luz própria"')
        botoes(saida_botoes)
        return
    a = max(achados, key=lambda x: x['lm'])  # um cartão por mudança: a centelha que mais vale converter
    print(observer.cartao_refletida(a['skill'], a['titulo'], a['centelha'], a['lm'], provisorio=a['provisorio']))
    if a['provisorio']:
        botoes(saida_botoes)
        return
    botoes([{'rotulo': 'Converter agora', 'descricao': f"{a['lm']} lm · você explica, a luz vira sua",
             'rodar': f"fazer {a['centelha']} --onde aqui"}, BT_CONVERTER, BT_TRAJETORIA], 'Converter agora?')


def cmd_acesso(valor: str, restantes: list[str]) -> None:
    """Sessões do painel. O chat roda como a pessoa no sistema, então `career-map` já entra logado; aqui ela vê quantas
    sessões estão abertas e pode encerrar todas (`acesso sair-de-todos`, só depois do sim explícito no botão)."""
    from . import acesso
    print('## Luzia · Acesso')
    if (valor or '').strip().lower() == 'sair-de-todos':
        if restantes[:1] == ['confirmar']:
            n = acesso.encerrar_todas()
            print(f"✦ {plural(n, 'sessão encerrada', 'sessões encerradas')}. Para voltar, abra o painel pelo chat (`career-map`).")
            botoes([BT_PAINEL], 'Quer abrir o painel de novo?')
            return
        print('Encerrar todas as sessões tira o painel de todos os navegadores em que ele está aberto. '
              'Para voltar, basta abrir o painel pelo chat. Seus dados não mudam.')
        botoes([{'rotulo': 'Sair de todos', 'descricao': 'encerra todas as sessões do painel',
                 'rodar': 'acesso sair-de-todos confirmar'}, BT_PAINEL], 'Quer encerrar todas as sessões do painel?')
        return
    n = acesso.sessoes_ativas()
    print(f"{plural(n, 'sessão aberta', 'sessões abertas')} no painel. Abrir pelo chat (`career-map`) já entra; a sessão "
          'dura 30 dias sem uso. "Sair", no painel, encerra só aquele navegador.')
    botoes([BT_PAINEL, {'rotulo': 'Sair de todos', 'descricao': 'encerra todas as sessões do painel',
                        'rodar': 'acesso sair-de-todos'}], 'Quer abrir o painel ou encerrar as sessões?')


def _registrar_agente_atual() -> None:
    """O painel diz em qual agente a pessoa está: quem abre pelo Claude Code não vê "Antigravity"."""
    if os.environ.get('CLAUDECODE') or os.environ.get('CLAUDE_CODE_ENTRYPOINT'):
        cfg = observer.config()
        if cfg.get('agente') != 'claude-code':
            cfg['agente'] = 'claude-code'
            arquivos.gravar_json(observer.CFG, cfg)


def abrir_painel() -> None:
    """Abre o painel já logado: link de uso único (2 min) no fragmento da URL. O link só aparece no chat quando o
    navegador não pôde ser aberto (ex.: agente remoto), uma vez e com o aviso de prazo."""
    import webbrowser
    from . import acesso
    estado, info = identidade_do_painel()
    if estado == 'ok' and (info.get('versao') != arquivos.versao_codigo() or info.get('esquema') != banco.ESQUEMA_VERSAO):
        _encerrar_painel(info.get('pid'))  # painel de antes de uma atualização: reinicia com o código atual
        estado = 'ausente'
    if estado == 'ausente':
        start_panel()
        estado, info = identidade_do_painel()
    if estado != 'ok':
        print('## Luzia · Painel não abriu')
        print(f'Algo que não é o seu painel da Luzia está respondendo em {PAINEL} (outro programa, ou um painel antigo '
              'da Luzia que não sabe se identificar). Por segurança, não gerei o link de entrada. Feche esse programa '
              '(ou reinicie o computador) e peça o painel de novo.')
        botoes([BT_TRAJETORIA, BT_PAINEL], 'Quer tentar abrir o painel de novo?')
        return
    _registrar_agente_atual()
    url = f'{PAINEL}/#entrar={acesso.emitir_link()}'
    try:
        aberto = bool(webbrowser.open(url)) and not _sem_tela()
    except Exception:
        aberto = False
    if aberto:
        print('## Luzia · Painel aberto')
        print(f'{PAINEL}, já com a sua sessão.')
    else:
        print('## Luzia · Navegador não abriu')
        print(f'Abra este link no navegador desta máquina. Ele vale 2 minutos e funciona uma vez só: {url}')
    botoes([BT_TRAJETORIA, BT_PAINEL])


def cmd_privacidade(valor: str, restantes: list[str]) -> None:
    """Interruptor do envio ao modelo: `privacidade mascarar-modelo on|off` (o mesmo de Ajustes no painel)."""
    print('## Luzia · Privacidade')
    escolha = (restantes[0] if restantes else '').strip().lower()
    if (valor or '').strip().lower() == 'mascarar-modelo' and escolha in ('on', 'off'):
        pipeline.definir_mascarar_modelo(escolha == 'on')
        print('✦ Ajustado.')
    elif valor:
        print('Use `privacidade mascarar-modelo on` ou `privacidade mascarar-modelo off`.')
    ligado = pipeline.mascarar_modelo()
    termos = pipeline.termos_configurados()
    if ligado:
        print('Mascarar antes de enviar ao modelo: **ligado**. E-mails, URLs, números de PR/ticket, hashes e os colegas '
              'do git viram marcadores antes de sair da máquina; empresa, produtos e clientes, só os listados em '
              f'`{arquivos.PRIVATE / "termos.txt"}` ({plural(termos, "termo")}).')
    else:
        print('Mascarar antes de enviar ao modelo: **desligado** (padrão). O modelo recebe os fatos reais, como você '
              'os vê no painel e no chat.')
    if not termos:
        print(f'◐ Sem termos em `{arquivos.PRIVATE / "termos.txt"}`: com o mascaramento ligado, nomes de empresa, produto e cliente '
              'passariam como estão. Liste-os lá, um por linha.')
    print('O interruptor vale só para as chamadas da própria Luzia ao modelo; o agente do chat (Claude Code, Codex...) '
          'recebe os dados reais na saída da CLI. Na tela nada é mascarado: o painel só abre pelo seu agente. Arquivos '
          'versionados nunca recebem dados reais.')
    alterna = ({'rotulo': 'Enviar dados reais', 'descricao': 'desliga o mascaramento no envio ao modelo',
                'rodar': 'privacidade mascarar-modelo off'} if ligado else
               {'rotulo': 'Mascarar no envio', 'descricao': 'liga o mascaramento antes de cada chamada ao modelo',
                'rodar': 'privacidade mascarar-modelo on'})
    botoes([alterna, BT_PAINEL], 'Quer mudar o que vai para o modelo?')


# ------------------------------------------------------------------ main
COMANDOS = [
    'hoje', 'triage', 'trajetoria', 'next-level', 'rota',
    'entregas', 'entrega', 'acender-entrega', 'feedback-progress', 'feedback-skills-opportunities', 'identidade',
    'leituras', 'analises', 'foco', 'agente',
    'avancos', 'centelhas', 'acoes', 'fazer', 'converter', 'prompt', 'registrar', 'confirmar', 'descartar', 'restaurar',
    'subir', 'acender', 'trecho', 'pedido', 'dividir', 'dividir-todos',
    'dossie', 'fila', 'enviar', 'career-map', 'modo', 'modelo', 'acesso', 'privacidade', 'diagnostico', 'configurar',
]
# Nomes de estado de antes das centelhas: ainda entendidos em `--estado`.
ESTADO_LEGADO = {'sugerido': 'apagada', 'sugeridas': 'apagada', 'na_fila': 'convertendo', 'em_andamento': 'convertendo',
                 'conquistado': 'propria', 'descartado': 'descartada', 'abertas': 'converter'}
MAIS_TXT = {'convertendo': 'convertendo', 'refletida': 'com luz refletida', 'propria': 'com luz própria',
            'apagada': 'por acender', 'descartada': 'descartadas'}
ORDEM_LISTA = {'convertendo': 0, 'refletida': 1, 'apagada': 2, 'propria': 3, 'descartada': 4}


CAMPOS_ENTRADA = (('nivel', 'Onde você está'), ('objetivo', 'Aonde quer chegar'), ('horizonte', 'Em quanto tempo'),
                  ('repo', 'Repositório'), ('author', 'E-mail dos seus commits'))


def cmd_configurar(args, entrada_path: Path) -> None:
    """Primeira configuração (ou ajuste): grava entrada.json e autoriza o repositório para o foco. Nada vai ao modelo aqui."""
    cfg = arquivos.ler_json(entrada_path, {}) if entrada_path.exists() else {}
    for chave, valor in (('nivel', args.cargo), ('objetivo', args.objetivo), ('horizonte', args.horizonte),
                         ('uso_ia', args.uso_ia), ('github', args.github), ('author', args.autor)):
        if valor and valor.strip():
            cfg[chave] = valor.strip()
    avisos = []
    if args.repo:
        repo = Path(args.repo).expanduser().resolve()
        if (repo / '.git').exists():
            cfg['repo'] = str(repo)
        else:
            avisos.append(f'{repo} não é a raiz de um repositório git: o repositório não mudou.')
    if args.cv:
        cv = Path(args.cv).expanduser().resolve()
        if cv.is_file():
            cfg['cv_pdf'] = str(cv)
            if cv.suffix.lower() == '.pdf':
                try:
                    import pypdf  # noqa: F401
                except ImportError:
                    avisos.append('para ler o currículo em PDF, instale o pypdf: python -m pip install pypdf '
                                  '(ou use um .txt ou .md).')
        else:
            avisos.append('o arquivo do currículo não foi encontrado: o currículo não mudou.')
    if args.sem_historico:
        cfg['incluir_historico_ia'] = False
    elif args.com_historico:
        cfg['incluir_historico_ia'] = True
    arquivos.gravar_json(entrada_path, cfg)
    if cfg.get('repo'):
        obs = observer.config()
        autorizados = obs.setdefault('autorizados', [])
        if cfg['repo'] not in autorizados:
            autorizados.append(cfg['repo'])
            arquivos.gravar_json(observer.CFG, obs)
    print('## Luzia · Configuração')
    for chave, rotulo_campo in CAMPOS_ENTRADA:
        print(f"- {rotulo_campo}: {cfg.get(chave) or 'faltando'}")
    print(f"- Currículo: {'sim' if cfg.get('cv_pdf') else 'não (opcional)'} · GitHub: {cfg.get('github') or 'não (opcional)'}"
          f" · Histórico das IAs: {'sim' if cfg.get('incluir_historico_ia') is True else 'não'}")
    print(f'- Foco liga só em: {", ".join(observer.config().get("autorizados") or []) or "nenhum repositório"}')
    for a in avisos:
        print(f'Atenção: {a}')
    faltam = [r for c, r in CAMPOS_ENTRADA if not cfg.get(c)]
    if faltam:
        print(f"\nFalta: {', '.join(faltam)}.")
        botoes([BT_PAINEL], 'Completar depois?')
        return
    print('\nTudo pronto para a triagem.')
    botoes([{'rotulo': 'Fazer a triagem', 'descricao': 'ler currículo, GitHub e commits', 'rodar': 'triage'}, BT_PAINEL],
           'Próximo passo?')


def cmd_diagnostico() -> None:
    """Confere o ambiente (Python, dados, modelo, plano, git) sem mostrar chave nenhuma."""
    import shutil
    v = sys.version_info
    st = modelo.status()
    try:
        tem_plano = bool(pipeline.load_state().get('plano'))
    except Exception:
        tem_plano = False
    print('## Luzia · Diagnóstico')
    print(f"Python: {v.major}.{v.minor}.{v.micro} " + ('ok' if v >= (3, 11) else '(precisa ser 3.11 ou mais novo)'))
    print(f'Pasta de dados: {arquivos.PRIVATE}')
    print(f"Modelo: {st['nome_provedor']} · SDK: " + ('instalado' if st['sdk_instalado'] else f"falta (pip install {st['pip']})"))
    print('Chave do modelo: ' + ('configurada' if st['chave_configurada'] else 'FALTANDO (painel > Ajustes, nunca no chat)'))
    print('Triagem/plano: ' + ('existe' if tem_plano else 'ainda não feita'))
    print('git: ' + ('encontrado' if shutil.which('git') else 'NÃO encontrado no PATH'))
    botoes([{'rotulo': 'Abrir o painel', 'descricao': 'mapa completo no navegador', 'rodar': 'career-map'},
            {'rotulo': 'Fazer a triagem', 'descricao': 'ler currículo, GitHub e commits', 'rodar': 'triage'}], 'Como seguimos?')


def main() -> None:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='Luzia CLI')
    ap.add_argument('comando', choices=COMANDOS)
    ap.add_argument('valor', nargs='?', default='')
    ap.add_argument('--entrada', default=str(pipeline.PRIVATE / 'entrada.json'))
    ap.add_argument('--rotulo', default='')
    ap.add_argument('--salvar-json', default='', help='Salva a resposta e o custo num JSON separado (não altera o estado)')
    ap.add_argument('--nota', default=None)  # validada em `registrar` (0 a 4), com mensagem em português
    ap.add_argument('--resumo', default='')
    ap.add_argument('--skill', default='')
    ap.add_argument('--prisma', default='')
    ap.add_argument('--estado', default='')
    ap.add_argument('--tipo', default='')
    ap.add_argument('--motivo', default='nao_faz_sentido')
    ap.add_argument('--onde', default='', help='Onde a centelha foi aberta (ex.: "sessão nova", "aqui")')
    ap.add_argument('--ampliar', type=int, default=0)
    ap.add_argument('--nivel', type=int, default=None)
    ap.add_argument('--meta', type=int, default=None)
    ap.add_argument('--partes', nargs='+', default=None, help='pedido ajustar (dividir): nomes das habilidades')
    ap.add_argument('--mover', action='append', default=None, help='pedido ajustar (dividir): <avanço>=<habilidade>')
    ap.add_argument('--base-url', default='', help='modelo usar: endereço do provedor compatível com OpenAI')
    ap.add_argument('--todas', action='store_true', help='leituras: inclui as entregas antigas, não só as mais recentes')
    ap.add_argument('--prompt-arquivo', default='', help='foco: arquivo temporário com o texto do pedido (nunca é gravado)')
    ap.add_argument('--arquivos', nargs='+', default=[], help='foco: caminhos editados; o código é lido do git diff e nunca gravado')
    ap.add_argument('--cwd', default='', help='foco: pasta do projeto da pessoa (a CLI roda de dentro do plugin)')
    ap.add_argument('--sessao', default='', help='foco: id da sessão do agente (padrão: um id diário por pasta)')
    ap.add_argument('--cargo', default='', help='configurar: onde você está hoje (ex.: "Júnior 3")')
    ap.add_argument('--objetivo', default='', help='configurar: aonde quer chegar (ex.: "Plena")')
    ap.add_argument('--horizonte', default='', help='configurar: em quanto tempo (ex.: "12 meses")')
    ap.add_argument('--repo', default='', help='configurar: raiz do repositório git em que você trabalha')
    ap.add_argument('--autor', default='', help='configurar: nome ou e-mail dos seus commits')
    ap.add_argument('--cv', default='', help='configurar: currículo em PDF, .txt ou .md (opcional)')
    ap.add_argument('--github', default='', help='configurar: usuário do GitHub (opcional)')
    ap.add_argument('--uso-ia', default='', help='configurar: como você usa IA hoje, numa frase (opcional)')
    ap.add_argument('--sem-historico', action='store_true', help='configurar: não ler o histórico do Claude Code e do Codex')
    ap.add_argument('--com-historico', action='store_true', help='configurar: pode ler o histórico do Claude Code e do Codex')
    ap.add_argument('--verbose', action='store_true', help='mostra o rodapé técnico (tempo, memória e tokens das chamadas)')
    args, restantes = ap.parse_known_args()
    global VERBOSE
    VERBOSE = bool(args.verbose)

    entrada_path = Path(args.entrada)
    rotulo = args.rotulo or f'cmd-{args.comando}'

    if args.comando == 'modo':
        bts_foco = [
            {'rotulo': 'Em foco', 'descricao': 'soma lúmens e mostra centelhas da sessão', 'rodar': 'modo ativo'},
            {'rotulo': 'Em silêncio', 'descricao': 'soma lúmens sem interromper', 'rodar': 'modo passivo'},
            {'rotulo': 'Fora de foco', 'descricao': 'só age quando você chama', 'rodar': 'modo sob_demanda'},
        ]
        if args.valor in MODOS:
            set_mode(args.valor)
            nome_foco = observer.NOMES_FOCO.get(args.valor, args.valor)
            print(f'✦ Foco: **{nome_foco}** (`{args.valor}`).')
        else:
            cfg = observer.config()
            nome_foco = observer.NOMES_FOCO.get(cfg['modo'], cfg['modo'])
            print(f"✦ Foco agora: **{nome_foco}** (`{cfg['modo']}`).")
        botoes(bts_foco, 'Qual foco?')
        return

    if args.comando == 'modelo' and args.valor == 'usar':
        extras = [x for x in restantes if not x.startswith('--')]
        if any(x.startswith('--chave') or x.lower() in ('chave', 'key') for x in restantes):
            print('◐ A chave nunca passa pelo chat: coloque-a em Ajustes > Modelo da Luzia, no painel, ou no `.env` desta máquina.')
            botoes([BT_PAINEL, BT_TRAJETORIA], 'Como seguimos?')
            return
        if len(extras) < 2:
            print('Use: `modelo usar <provedor> <modelo>`, com provedor ' + ', '.join(modelo.PROVEDORES) + '.')
            botoes([BT_PAINEL, BT_TRAJETORIA], 'Como seguimos?')
            return
        try:
            modelo.salvar(extras[0].lower(), extras[1], args.base_url)
        except ValueError as e:
            print(f'◐ Não troquei o modelo: {e}. Provedores: ' + ', '.join(modelo.PROVEDORES) + '.')
            botoes([BT_PAINEL, BT_TRAJETORIA], 'Como seguimos?')
            return
        st = modelo.status()
        print(f"✦ Modelo da Luzia agora: **{st['nome_provedor']}** · `{st['modelo']}`. "
              f"Chave: {'configurada' if st['chave_configurada'] else 'FALTANDO (coloque no painel, em Ajustes, ou no `.env`; nunca no chat)'}.")
        botoes([{'rotulo': 'Testar o modelo', 'descricao': 'uma chamada curta para conferir', 'rodar': 'modelo testar'},
                BT_PAINEL], 'Quer testar o modelo?')
        return

    if args.comando == 'agente':
        cfg = observer.config()
        escolhas = observer.AGENTES
        if args.valor in escolhas:
            cfg['agente'] = args.valor
            arquivos.gravar_json(observer.CFG, cfg)
            print(f'✦ Agente da Luzia ajustado para **{args.valor}**.')
        elif args.valor:
            print(f"◐ Agente desconhecido: `{args.valor}`. Use um de: {', '.join(escolhas)}.")
        else:
            print(f"✦ Agente atual da Luzia: **{cfg.get('agente', 'claude-code')}**. Opções: {', '.join(escolhas)}.")
        botoes([{'rotulo': nome, 'descricao': 'usar este agente', 'rodar': f'agente {nome}'}
                for nome in escolhas if nome != cfg.get('agente', 'claude-code')][:3], 'Qual agente você usa?')
        return

    if args.comando == 'modelo':
        s = modelo.status()
        print('## Luzia · Modelo')
        print(f"**{s['nome_provedor']}** · `{s['modelo']}`" + (f" · {s['base_url']}" if s.get('base_url') else ''))
        print(f"chave: {'configurada' if s['chave_configurada'] else 'FALTANDO'} · "
              f"SDK: {'instalado' if s['sdk_instalado'] else 'falta: pip install ' + s['pip']}")
        print('Troque em Ajustes > Modelo da Luzia, no painel, ou pelo chat: `modelo usar <provedor> <modelo>`. '
              'A chave nunca passa pelo chat: coloque-a no painel ou no .env desta máquina.')
        if args.valor == 'testar':
            r = modelo.chamar('Responda só com o JSON {"ok": true}.', 'Responda só com JSON.')
            print(f"teste: {r['texto'].strip()[:60]} · {r['segundos']:.1f} s · {r['tokens_in']}→{r['tokens_out']} tokens · {r['provedor']}/{r['modelo']}")
            if r.get('aviso'):
                print(f"! {r['aviso']}")
        botoes([BT_TRAJETORIA, BT_PAINEL], 'O que você quer ver agora?')
        return

    if args.comando == 'foco':
        cmd_foco(args)
        return

    if args.comando == 'acesso':
        cmd_acesso(args.valor, restantes)
        return

    if args.comando == 'privacidade':
        cmd_privacidade(args.valor, restantes)
        return

    if args.comando == 'career-map':
        abrir_painel()
        return

    if args.comando == 'diagnostico':
        cmd_diagnostico()
        return

    if args.comando == 'configurar':
        cmd_configurar(args, entrada_path)
        return

    if args.comando == 'triage':
        if not entrada_path.exists():
            print('## Luzia · Triagem')
            print('Antes da triagem, conte onde você está, aonde quer chegar e em qual repositório trabalha.')
            print('Siga o roteiro do comando /luzia:triage, que grava isso com `configurar`.')
            botoes([BT_PAINEL], 'Configurar agora?')
            return
        try:
            plan, rec, hits = execute_triage(entrada_path, rotulo=rotulo, save_state=not args.salvar_json)
        except Exception as e:
            arquivos.registrar_erro('cli triage', e)
            print('## Luzia · Triagem não rodou')
            print(modelo.resumo_erro(e) + '.')
            print('Nada foi perdido. Confira o modelo e a chave com /luzia:diagnostico e tente de novo.')
            botoes([{'rotulo': 'Conferir o ambiente', 'descricao': 'Python, SDK, chave e git', 'rodar': 'diagnostico'},
                    BT_PAINEL], 'Como seguimos?')
            return
        if args.salvar_json:
            Path(args.salvar_json).write_text(
                json.dumps({'plano': plan, 'custo': rec, 'hits': hits}, ensure_ascii=False, indent=2), encoding='utf-8',
            )
            return
        state = pipeline.load_state()
        plan = state.get('plano', {})
        print('## Luzia · Triagem')
        try:
            cfg_tri = json.loads(entrada_path.read_text(encoding='utf-8'))
        except Exception:
            cfg_tri = None
        base_tri = base_triagem(rec.get('mascarar_modelo', False), cfg_tri)
        for rotulo_tri, campo in (('Onde você está', 'onde_esta'), ('Aonde quer chegar', 'aonde_quer_chegar')):
            texto = (plan.get(campo) or {}).get('resumo', '')
            leit = {'texto': texto, 'modelo': rec.get('modelo'), 'criado_em': rec.get('quando')}
            print(f"{rotulo_tri}: {leitura_txt(leit, base_tri)}")
        print()
        rota_texto(plan, state)
        primeiros = [a for a in acoes.todas(plan) if a['origem'] == 'rota']
        print('\n**Primeiras centelhas:**')
        for a in primeiros[:3]:
            print(feixe_linha(a))
        footer(rec, hits)
        botoes([bt_feixe(a) for a in primeiros] + [BT_TRAJETORIA, BT_PAINEL], 'Próximo passo?')
        return

    if args.comando == 'feedback-skills-opportunities':
        resp, rec, hits = daily_call(entrada_path, rotulo)
        plan = pipeline.load_state().get('plano', {})
        sessao = [a for a in acoes.todas(plan) if a['origem'] == 'sessão']
        print('## Luzia · Oportunidades')
        if resp.get('resumo_sessao'):
            print(leitura_txt({'texto': resp['resumo_sessao'], 'modelo': rec.get('modelo'), 'criado_em': rec.get('quando')},
                              f"{plural(rec.get('eventos_sessao', 0), 'evento mascarado', 'eventos mascarados')} da sessão e o seu plano") + '\n')
        for a in sessao:
            print(feixe_linha(a))
            print(f"   ↳ {a.get('gatilho', '')}")
        footer(rec, hits)
        oferecer(sessao, 'Próximo passo?')
        return

    state = pipeline.load_state()
    plan = state.get('plano', {})
    if not plan:
        print('A Luzia ainda não fez a triagem. Rode /luzia:triage.')
        botoes([BT_PAINEL])
        return

    if args.comando in ('entregas', 'feedback-progress'):
        cmd_entregas(args, state)
        return

    if args.comando == 'identidade':
        cmd_identidade(args, restantes)
        return

    if args.comando in ('leituras', 'analises'):
        cmd_leituras(args.todas)
        return

    if args.comando == 'acender-entrega':
        if not str(args.valor).isdigit():
            print('Informe o número da entrega: `acender-entrega <id>`')
            botoes([{'rotulo': 'Ver entregas', 'descricao': 'lista de entregas', 'rodar': 'entregas'}, BT_PAINEL])
            return
        res = acender_entrega(int(args.valor), rotulo)
        voltar = {'rotulo': f'Ver #{args.valor}', 'descricao': 'fatos, propriedade e centelhas',
                  'rodar': f'entrega {args.valor}'}
        if res.get('erro'):
            print(f"◐ Não acendi centelhas para a entrega `#{args.valor}`: {res['erro']}.")
            botoes([*[bt_feixe(a) for a in res.get('avancos', [])][:2], voltar, BT_PAINEL], 'Como seguimos?')
            return
        det = res['entrega']
        print(f"## Luzia · 2 centelhas para a entrega #{det['id']}")
        print(f"**{det['titulo']}**")
        for a in res['avancos']:
            print(f"{feixe_linha(a)} → prova {a.get('dimensao')}")
        footer(res['record'])
        botoes([bt_feixe(a) for a in res['avancos']] + [voltar], 'Próximo passo?')
        return

    if args.comando == 'entrega':
        if not args.valor or not str(args.valor).isdigit():
            print('Informe o número da entrega: `entrega <id>`')
            botoes([{'rotulo': 'Ver entregas', 'descricao': 'listar entregas detectadas', 'rodar': 'entregas'}, BT_PAINEL])
            return
        cmd_entrega_detalhe(int(args.valor), plan)
        return

    if args.comando == 'pedido':
        cmd_pedido(args, restantes, plan)
        return

    if args.comando in ('dividir', 'dividir-todos'):
        cmd_dividir(args, plan, todos=args.comando == 'dividir-todos')
        return

    if args.comando == 'hoje':
        hoje(plan, state)
        return

    if args.comando in ('trajetoria', 'next-level', 'rota'):
        with trajetoria.abrir() as con:
            versoes = trajetoria.versoes(con)
            ver_atual = versoes[-1]['numero'] if versoes else 1
            ver_motivo = versoes[-1]['origem'] if versoes else 'triagem'
            arquivados = [p for p in trajetoria.prismas(con, incluir_arquivados=True) if p['estado'] == 'arquivado']
            lista_pedidos = pedidos.listar(con)
        ini, fim = pipeline.rotulos(state)
        print(f"## Luzia · Trajetória · v{ver_atual}" + (f' ({ver_motivo})' if ver_motivo != 'triagem' else ''))
        rota_texto(plan, state)
        cfg = load_cfg(entrada_path) if entrada_path.exists() else {}
        rit = jogo.ritmo(plan, cfg.get('horizonte', ''))
        if rit['feixes_semana']:
            print(f"\n_Ritmo: {plural(rit['feixes_semana'], 'centelha')} por semana leva até {fim} em ~{rit['meses']} meses. "
                  'É só referência._')
        if arquivados:
            print(f'\n**Arquivados ({len(arquivados)})** · luz preservada')
            for p in arquivados:
                print(f"   - {nome_prisma(p['nome'])}")
        if lista_pedidos:
            print('\n**Pedidos**')
            for p in lista_pedidos[:5]:
                print(f"   - `#{p['id']}` · {p['tipo']} · **{nome_prisma(p['prisma'])}** · {p['estado']}")
        botoes(com_leituras(proximos_botoes(plan) + [BT_CONVERTER]), 'Próximo passo?')
        return

    if args.comando in ('avancos', 'centelhas', 'acoes'):
        jogo.sincronizar(plan)
        est_f = (args.estado or 'converter').strip().lower().replace(' ', '_')
        est_f = ESTADO_LEGADO.get(est_f, est_f)
        if est_f not in ('converter', 'todas', *jogo.ESTADOS):
            print(f"◐ Não conheço o estado `{args.estado}`. Use converter, propria, apagada ou todas.")
            botoes([BT_CONVERTER, BT_PAINEL])
            return
        pri_raw = args.prisma or args.skill or (args.valor if args.valor else None)
        pri_f = jogo.skill_de(pri_raw, plan) if pri_raw else None
        tip_f = args.tipo or None
        with trajetoria.abrir() as con:
            lista = jogo.avancos(con, estado=est_f if est_f in jogo.ESTADOS else None, prisma=pri_f, tipo=tip_f)
        if est_f == 'converter':
            lista = [a for a in lista if a.get('estado') in jogo.PARA_CONVERTER]
        elif est_f == 'todas':
            lista = [a for a in lista if a.get('estado') != 'descartada']
        if est_f in ('converter', 'todas'):
            lista.sort(key=lambda a: (ORDEM_LISTA.get(a.get('estado'), 9), -int(a.get('valor_lm') or 0)))
        nome_estado = {'converter': 'para converter', 'todas': 'todas'}.get(est_f) or jogo.ROTULO_ESTADO[est_f].lower()
        filtros_txt = ' · '.join(v for v in (nome_estado, pri_f and nome_prisma(pri_f), tip_f) if v)
        print(f"## Luzia · Centelhas · {filtros_txt} · {len(lista)}")
        if not lista:
            print('Nada com esses filtros.' if (pri_f or tip_f or est_f != 'converter') else 'Nenhuma centelha para converter agora.')
        for a in lista[:3]:
            print(centelha_txt(a))
        resto: dict[str, int] = {}
        for a in lista[3:]:
            resto[a['estado']] = resto.get(a['estado'], 0) + 1
        for est in sorted(resto, key=lambda e: ORDEM_LISTA.get(e, 9)):
            print(f"{ESTADO_IC[est]} mais {resto[est]} {MAIS_TXT[est]}")
        bts = [bt_converter(a) for a in lista if a.get('estado') in jogo.ABERTOS][:2]
        bts.append({'rotulo': 'Ver o que falta acender', 'descricao': 'centelhas ainda sem luz', 'rodar': 'centelhas --estado apagada'}
                   if est_f == 'converter' else BT_CONVERTER)
        botoes(bts, 'Próximo passo?')
        return

    if args.comando == 'fila':
        lista = [a for a in (acoes.find(plan, f['id']) for f in acoes.fila()) if a]
        print('## Luzia · Fila')
        if not lista:
            print('Nada na fila. No painel, toque em "Acender no seu agente" numa centelha.')
        for a in lista:
            print(centelha_txt(a))
        botoes([bt_feixe(a) for a in lista] + ([BT_PAINEL] if not lista else []), 'Próximo passo?')
        return

    if args.comando in ('acender', 'trecho'):
        if not (args.valor or args.prisma or args.skill):  # sem prisma, pergunta: nada é gerado por adivinhação
            abertos = [p['nome'] for p in jogo.luz(plan)['prismas'] if not p['na_meta']]
            print('Para qual prisma? Ex.: `acender Git`.')
            botoes([{'rotulo': f'Acender: {nome_prisma(n)}', 'descricao': '3 centelhas novas', 'rodar': f'acender {n}'}
                    for n in abertos[:4]], 'Qual prisma?')
            return
        try:
            res = gerar_trecho(args.valor or args.prisma or args.skill, rotulo)
        except Exception as e:  # sem modelo, sem chave ou sem internet: mensagem clara e botões, nada gravado
            arquivos.registrar_erro('cli acender', e)
            res = {'erro': f'não deu para acender centelhas sem o modelo ({modelo.resumo_erro(e)})'}
        if res.get('erro'):
            print(f"◐ {res['erro']}.")
            botoes(proximos_botoes(plan))
            return
        print(f"## Luzia · {plural(len(res['feixes']), 'centelha nova', 'centelhas novas')} · {nome_prisma(res['skill'])}")
        for f in res['feixes']:
            print(centelha_txt(f))
        footer(res['record'])
        oferecer(res['feixes'], 'Próximo passo?')
        return

    a = acoes.find(plan, args.valor) if args.valor else None

    if args.comando == 'enviar':
        if not a:
            print(sem_centelha(args))
            botoes(proximos_botoes(plan))
            return
        if not jogo.enfileirar(a['id']):
            print(f"`#{a['id']}` não pode ir para a fila: já é luz própria ou está descartada.")
            botoes(proximos_botoes(plan))
            return
        acoes.enfileirar(a['id'], a.get('titulo', ''))
        print(f"➤ `#{a['id']}` na fila: a Luzia oferece na sua próxima mensagem.")
        botoes([bt_feixe(a), BT_PAINEL], 'Próximo passo?')
        return

    if args.comando in ('prompt', 'fazer', 'converter'):
        if not a:
            print(sem_centelha(args))
            botoes(proximos_botoes(plan))
            return
        if a.get('estado') == 'propria':
            print(f"`#{a['id']}` já é luz própria. Não há o que converter.")
            botoes(proximos_botoes(plan, {a['id']}))
            return
        atual = jogo.iniciar(a['id'], args.onde)
        if not atual:
            print(f"`#{a['id']}` está descartada.")
            botoes([{'rotulo': 'Restaurar', 'descricao': 'volta para onde estava', 'rodar': f"restaurar {a['id']}"}])
            return
        acoes.desenfileirar(a['id'])
        acoes.registrar_evento(a['id'], 'iniciada', skill=a.get('skill'), origem=a.get('origem'))
        if args.comando == 'prompt':
            print(acoes.prompt_completo(atual))
        else:
            roteiro(atual)
            botoes([
                *([bt_confirmar(atual)] if atual.get('confirmada_em') else []),
                {'rotulo': 'Descartar', 'descricao': 'não faz sentido para mim', 'rodar': f"descartar {a['id']} --motivo nao_faz_sentido"},
                {'rotulo': 'Já domino', 'descricao': 'descarta por já dominar', 'rodar': f"descartar {a['id']} --motivo ja_domino"},
                BT_PAINEL,
            ], 'Responda no chat, ou escolha:')
        return

    if args.comando == 'registrar':
        nota_in = nota_valida(args.nota)
        if not a or nota_in is None:
            if args.valor and not a:
                print(sem_centelha(args))
            elif args.nota is not None:
                print(f'A nota vai de 0 a 4 (recebi `{args.nota}`). Nada foi registrado.')
            else:
                print("Use: registrar <id> --nota 0-4 --resumo '...'")
            botoes(proximos_botoes(plan))
            return
        res = jogo.avaliar(a['id'], nota_in, args.resumo[:200], plan)
        if res.get('erro'):
            print(f"◐ {res['erro']}.")
            botoes(proximos_botoes(plan))
            return
        f, nota = res['feixe'], res['nota']
        rubrica = propriedade.RUBRICA[max(0, min(4, nota))]
        if res['confirmada']:
            print(f'◐ Nota {nota} de 4 · a Luzia confirmou seu entendimento')
            print(f"Você {rubrica}." + (f" — {args.resumo[:200]}" if args.resumo else ''))
            print(f"Falta o seu sim para acender {f.get('valor_lm')} lm de luz própria.")
            botoes([bt_confirmar(f), *proximos_botoes(plan, {a['id']})[:2]], 'Acender a luz própria agora?')
            return
        print(f'◐ Nota {nota} de 4 · ainda convertendo')
        if args.resumo:
            print(f"O que você mostrou: {args.resumo[:200]}")
        print(f"Para converter, falta: {propriedade.RUBRICA[3]} (nota 3) ou {propriedade.RUBRICA[4]} (nota 4).")
        print(f"A centelha vale os mesmos {f.get('valor_lm')} lm. Tente de novo quando quiser.")
        botoes([bt_feixe(f, 'Continuar: '), *proximos_botoes(plan, {a['id']})[:2]], 'Próximo passo?')
        return

    if args.comando == 'confirmar':
        if not a:
            print('Use: confirmar <id> (o id da centelha que a Luzia confirmou).' if not args.valor
                  else f'Centelha {args.valor} não encontrada.')
            botoes(proximos_botoes(plan))
            return
        res = jogo.confirmar(a['id'], plan)
        if res.get('erro'):
            print(f"◐ {res['erro']}.")
            botoes([bt_feixe(a)] if a.get('estado') in jogo.PARA_CONVERTER else proximos_botoes(plan))
            return
        f = res['feixe']
        print(f"✦ **+{res['ganho']} lm de luz própria** · {nome_prisma(res['prisma'])} {res['pct_antes']}% → {res['pct_depois']}%")
        print(f"**{f.get('titulo', '')}** agora é luz própria.")
        if f.get('entrega_id'):
            with trajetoria.abrir() as con:
                det = entregas.detalhe(con, f['entrega_id'], incluir_leitura=False)
            if det:
                idx = det['propriedade'].get('indice')
                print(f"▸ Entrega #{det['id']}: propriedade agora "
                      f"**{f'{idx}% seu' if idx is not None else '—'}** (medido em {dims_medidas(det['propriedade']) or '—'})")
        if res.get('marco'):
            print(f"✦ Marco {res['marco']['n']} de 3 · dossiê gerado em `{res['marco']['dossie']}` (local).")
        ini, fim = pipeline.rotulos(state)
        print(f"{ini} → {fim}  {barra_total(res['luz'])}  {res['luz']['pct']}% seu")
        botoes([*proximos_botoes(plan, {a['id']})[:2], BT_CONVERTER], 'Próximo passo?')
        return

    if args.comando == 'descartar':
        if not a:
            print(sem_centelha(args))
            botoes(proximos_botoes(plan))
            return
        motivo_k = args.motivo if args.motivo in jogo.MOTIVOS else 'nao_faz_sentido'
        if not jogo.descartar(a['id'], motivo_k):
            print(f"`#{a['id']}` já é luz própria ou já estava descartada. Nada mudou.")
            botoes(proximos_botoes(plan, {a['id']}))
            return
        acoes.desenfileirar(a['id'])
        print(f"✕ Descartada ({jogo.MOTIVOS[motivo_k].lower()}). `#{a['id']}`")
        botoes([{'rotulo': 'Desfazer', 'descricao': 'a centelha volta para onde estava', 'rodar': f"restaurar {a['id']}"}]
               + proximos_botoes(plan, {a['id']}))
        return

    if args.comando == 'restaurar':
        if not a:
            print(sem_centelha(args))
            botoes(proximos_botoes(plan))
            return
        volta = jogo.restaurar(a['id'])
        if not volta:
            print(f"`#{a['id']}` não está descartada.")
            botoes(proximos_botoes(plan))
            return
        print(f"{ESTADO_IC.get(volta['estado'], '○')} `#{a['id']}` voltou para {jogo.ROTULO_ESTADO[volta['estado']].lower()}.")
        botoes([bt_feixe(volta)])
        return

    if args.comando == 'subir':
        print('O progresso agora vem de converter centelhas, não de subir de nível.')
        print('Cada centelha que vira luz própria enche o seu prisma.')
        botoes([BT_CONVERTER, BT_TRAJETORIA, BT_PAINEL], 'Próximo passo?')
        return

    if args.comando == 'dossie':
        caminho = jogo.dossie(plan)
        print(f'## Luzia · Dossiê\nSalvo em `{caminho}` (local, fora do git).')
        print(caminho.read_text(encoding='utf-8'))
        botoes(proximos_botoes(plan)[:2] + [BT_PAINEL])
        return


if __name__ == '__main__':
    main()
