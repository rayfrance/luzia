"""Testes da CLI: comandos, conversão de centelhas (registrar e confirmar), barra de luz e vocabulário."""

from __future__ import annotations

import io
import json
import re
import sys
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import pytest

from luzia import acoes, banco, cli, entregas, jogo, observer, pedidos, pipeline, statusline, trajetoria

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'

RE_TERMOS_ANTIGOS = re.compile(
    r'\b(feixes?|degraus?|trechos?(?!\s+d[eo]\s+c[óo]digo)|rota|cart[aã]o|cart[oõ]es)\b',
    re.IGNORECASE,
)


def rodar(monkeypatch, *argv: str) -> str:
    monkeypatch.setattr(sys, 'argv', ['luzia', *[str(a) for a in argv]])
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main()
    return buf.getvalue()


@contextmanager
def contextlib_suprimir_stderr():
    with redirect_stderr(io.StringIO()):
        yield


def visivel(saida: str) -> str:
    return '\n'.join(l for l in saida.splitlines() if not l.startswith('LUZIA_'))


def botoes_de(saida: str) -> list[dict]:
    linha = next((x for x in saida.splitlines() if x.startswith('LUZIA_BOTOES=')), None)
    return json.loads(linha.split('=', 1)[1]) if linha else []


def tem_rodape_botoes(saida: str) -> bool:
    linhas = [l for l in saida.splitlines() if l.strip()]
    return (
        any(l.startswith('LUZIA_CLI=') for l in linhas)
        and any(l.startswith('LUZIA_PERGUNTA=') for l in linhas)
        and any(l.startswith('LUZIA_BOTOES=') for l in linhas)
        and len(botoes_de(saida)) >= 1
    )


def _semear_entrega(con) -> int:
    with banco.transacao(con):
        cur = con.execute(
            "INSERT INTO entrega (chave, titulo, inicio, fim, fonte, commits, arquivos, linhas, areas_json) "
            "VALUES ('pr:1', 'Separa agregado de agendamento', '2026-11-10T10:00:00', '2026-11-11T15:00:00', "
            "'merge-pr', 2, 4, 90, '[\"Back-end C# / .NET\"]')"
        )
        eid = int(cur.lastrowid)
        con.execute(
            'INSERT INTO entrega_prisma (entrega_id, prisma, termos_json) VALUES (?, ?, ?)',
            (eid, DDD, json.dumps(['aggregate', 'domain'])),
        )
    return eid


def _apagadas(plan) -> list[str]:
    return [k for k, f in jogo.sincronizar(plan).items() if f['estado'] == 'apagada']


def _forcar_estado(fid: str, estado: str) -> None:
    """Põe a centelha num estado de luz sem passar pelo fluxo (cenário de teste)."""
    with trajetoria.abrir() as con, banco.transacao(con):
        con.execute('UPDATE avanco SET estado = ? WHERE id = ?', (estado, fid))


def _converter_ate_confirmar(monkeypatch, fid: str, nota: int = 4, resumo: str = 'Explicou as invariantes do agregado') -> str:
    rodar(monkeypatch, 'fazer', fid)
    return rodar(monkeypatch, 'registrar', fid, '--nota', str(nota), '--resumo', resumo)


def test_toda_saida_termina_em_botoes(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    cat = jogo.sincronizar(plan)
    apagadas = [k for k, f in cat.items() if f['estado'] == 'apagada']
    f1, f2, f3 = apagadas[0], apagadas[1], apagadas[2]

    with trajetoria.abrir() as con:
        eid = _semear_entrega(con)
    monkeypatch.setattr(entregas, 'atualizar', lambda con, dias=90: {'novas': 0, 'atualizadas': 0})

    comandos = [
        ('hoje',),
        ('trajetoria',),
        ('rota',),
        ('next-level',),
        ('avancos',),
        ('acoes',),
        ('centelhas',),
        ('centelhas', '--estado', 'todas'),
        ('centelhas', '--estado', 'propria'),
        ('fila',),
        ('fazer', f1),
        ('confirmar', f1),                      # a Luzia ainda não confirmou: explica e termina em botões
        ('registrar', f1, '--nota', '2', '--resumo', 'Faltou explicar o porquê'),
        ('registrar', f1, '--nota', '3', '--resumo', 'Explicou invariantes do agregado'),
        ('confirmar', f1),
        ('confirmar', f1),                      # já é luz própria
        ('converter', f3),
        ('descartar', f2, '--motivo', 'agora_nao'),
        ('restaurar', f2),
        ('enviar', f2),
        ('subir', DDD),
        ('subir',),
        ('entregas',),
        ('entrega', str(eid)),
        ('dossie',),
        ('modo',),
        ('modo', 'passivo'),
        ('modelo',),
    ]
    for argv in comandos:
        s = rodar(monkeypatch, *argv)
        assert tem_rodape_botoes(s), f'Comando {argv} não terminou com botões válidos:\n{s}'


def test_centelhas_filtros_e_padrao_para_converter(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    ids = _apagadas(plan)
    refletida = next(i for i in ids if jogo._um(i)['skill_plano'] == DDD)
    _forcar_estado(refletida, 'refletida')

    padrao = rodar(monkeypatch, 'centelhas')  # padrão: converter (refletida + convertendo); apagadas ficam de fora
    v = visivel(padrao)
    assert 'Centelhas · para converter · 1' in v
    assert 'Modelar um agregado de exemplo' in v and 'Luz refletida' in v
    assert 'Escrever um teste de unidade guiado' not in v and 'Por acender' not in v
    assert tem_rodape_botoes(padrao)

    s_apagada = visivel(rodar(monkeypatch, 'avancos', '--estado', 'apagada', '--prisma', DDD))
    assert 'Modelar um agregado de exemplo' not in s_apagada and 'Nada com esses filtros' in s_apagada
    s_apagada = visivel(rodar(monkeypatch, 'acoes', '--estado', 'apagada'))
    assert 'Por acender' in s_apagada and 'Escrever um teste de unidade guiado' in s_apagada

    s_testes = visivel(rodar(monkeypatch, 'avancos', '--estado', 'todas', '--prisma', TESTES, '--tipo', 'praticar'))
    assert 'Escrever um teste de unidade guiado' in s_testes and 'Modelar um agregado de exemplo' not in s_testes

    erro = rodar(monkeypatch, 'centelhas', '--estado', 'inventado')
    assert 'Não conheço o estado' in visivel(erro) and tem_rodape_botoes(erro)


def test_centelhas_duas_linhas_e_resumo_do_resto(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    ids = _apagadas(plan)
    for i in ids:
        _forcar_estado(i, 'refletida')
    with trajetoria.abrir() as con, banco.transacao(con):  # 5 centelhas para converter: 3 aparecem, 2 viram resumo
        for n in range(2):
            jogo._inserir_avanco(con, {'id': f'extra{n}', 'skill_plano': DDD, 'tipo': 'explicar', 'titulo': f'Extra {n}',
                                       'duracao_min': 5, 'valor_lm': 20, 'estado': 'refletida', 'origem': 'chat'})
    v = visivel(rodar(monkeypatch, 'centelhas')).splitlines()
    assert v[0] == '## Luzia · Centelhas · para converter · 5'
    titulos = [l for l in v if l.startswith('◑ Luz refletida · **')]
    detalhes = [l for l in v if l.startswith('  ') and ' lm · #' in l]
    assert len(titulos) == 3 and len(detalhes) == 3
    assert re.fullmatch(r'  \w+ · .+ · \d+ lm · #\w+', detalhes[0]), detalhes[0]
    assert '◑ mais 2 com luz refletida' in v


# ------------------------------------------------------------------ barra de luz, hoje, trajetória
def test_barra_luz_txt_um_glifo_por_estado():
    barra = cli.barra_luz_txt(50, 10, 30, 10, largura=10)
    assert barra == '█████▓▒▒▒░' and len(barra) == 10
    assert cli.barra_luz_txt(0, 0, 0, 0) == '░' * cli.LARGURA_BARRA  # sem centelhas: tudo por acender
    assert cli.barra_luz_txt(100, 0, 0, 0) == '█' * cli.LARGURA_BARRA
    assert set(cli.barra_luz_txt(1, 1, 1, 500)) == {'█', '▓', '▒', '░'}  # quem tem lm aparece com ao menos 1 glifo
    assert all(len(cli.barra_luz_txt(a, b, c, d)) == cli.LARGURA_BARRA
               for a, b, c, d in ((7, 13, 29, 51), (1, 2, 3, 4), (33, 33, 33, 1)))
    p = {'propria': 40, 'convertendo': 20, 'refletida': 50, 'apagada': 30}  # prisma de jogo.luz: refletida inclui convertendo
    assert cli.barra_de(p, 14) == cli.barra_luz_txt(40, 20, 30, 30, 14)


def test_trajetoria_duas_linhas_por_prisma_sem_niveis(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    ids = _apagadas(plan)
    ddd = next(i for i in ids if jogo._um(i)['skill_plano'] == DDD)
    _forcar_estado(ddd, 'refletida')
    v = visivel(rodar(monkeypatch, 'trajetoria'))
    linhas = v.splitlines()
    assert linhas[0].startswith('## Luzia · Trajetória · v1')
    assert re.fullmatch(r'Júnior 3 → Plena  [█▓▒░]{12}  \d+% seu', linhas[1]), linhas[1]
    i = next(n for n, l in enumerate(linhas) if re.fullmatch(r'DDD  [█▓▒░]{12}  0%', l))
    assert re.fullmatch(r'   0 de \d+ lm · 1 para converter · 0 por acender', linhas[i + 1]), linhas[i + 1]
    assert not any('nível' in l.lower() or '▰' in l or '▱' in l for l in linhas)
    assert 'Domain-Driven Design' not in v  # nome curto; o completo fica no painel
    assert sum(1 for l in linhas if re.fullmatch(r'\S.*  [█▓▒░]{12}  \d+%', l)) == 3  # um por prisma


def test_trajetoria_prisma_todo_proprio_esta_na_meta(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    for i in _apagadas(plan):
        _forcar_estado(i, 'propria')
    v = visivel(rodar(monkeypatch, 'trajetoria'))
    assert v.count('Na meta · tudo é luz própria') == 3 and '100%' in v and '█' * 12 in v


def test_hoje_mostra_a_centelha_que_mais_vale_converter(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    ids = _apagadas(plan)
    a, b, c = ids
    _forcar_estado(a, 'refletida')
    _forcar_estado(b, 'refletida')
    rodar(monkeypatch, 'fazer', c)  # c está convertendo: vem antes das refletidas, mesmo valendo menos
    s = rodar(monkeypatch, 'hoje')
    v = visivel(s)
    linhas = v.splitlines()
    assert linhas[0] == '## Luzia · Hoje'
    assert re.fullmatch(r'Júnior 3 → Plena  [█▓▒░]{12}  \d+% seu', linhas[1]), linhas[1]
    assert re.fullmatch(r'3 centelhas para converter · \d+ lm', linhas[2]), linhas[2]
    assert linhas[3] == '' and linhas[4].startswith('◐ **') and jogo._um(c)['titulo'] in linhas[4]
    assert re.fullmatch(r'  Apareceu em .+ · \w+ · \d+ min · \+\d+ lm|  Da .+ · \w+ · \d+ min · \+\d+ lm', linhas[5]), linhas[5]
    assert sum(1 for l in linhas if l.startswith('◑ Luz refletida · **')) == 2  # até 2 outras
    assert 'Perto de subir' not in v and 'pronto para subir' not in v and 'nível' not in v.lower()
    bts = botoes_de(s)
    assert bts[0]['rodar'] == f'fazer {c}' and bts[0]['rotulo'].startswith('Continuar: ')
    assert any(x['rodar'] == 'centelhas --estado converter' and x['rotulo'] == 'Ver centelhas para converter' for x in bts)


def test_hoje_sem_nada_para_converter_oferece_acender(privado, monkeypatch):
    s = rodar(monkeypatch, 'hoje')
    assert '0 centelhas para converter · 0 lm' in visivel(s) and 'Nada para converter agora' in visivel(s)
    assert tem_rodape_botoes(s)


def test_hoje_oferece_decidir_a_meta_quando_a_propor(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    _forcar_estado(_apagadas(plan)[0], 'refletida')
    with trajetoria.abrir() as con, banco.transacao(con):
        con.execute("UPDATE prisma SET meta_estado = 'a_propor' WHERE nome = ?", (DDD,))
    bts = botoes_de(rodar(monkeypatch, 'hoje'))
    assert any(b['rotulo'] == 'Decidir a meta de DDD' and b['rodar'] == 'trajetoria' for b in bts), bts


# ------------------------------------------------------------------ conversão: registrar e confirmar
def test_registrar_nota_2_continua_convertendo_com_a_dica(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    f1 = _apagadas(plan)[0]
    s = _converter_ate_confirmar(monkeypatch, f1, nota=2, resumo='Falta comparar com uma alternativa')
    v = visivel(s).splitlines()
    assert v[0] == '◐ Nota 2 de 4 · ainda convertendo'
    assert 'O que você mostrou: Falta comparar com uma alternativa' in v
    assert any(l.startswith('Para converter, falta: ') for l in v)
    bts = botoes_de(s)
    assert bts[0]['rodar'] == f'fazer {f1}' and bts[0]['rotulo'].startswith('Continuar: ')
    assert all(b['rodar'] != f'confirmar {f1}' for b in bts)
    f = jogo._um(f1)
    assert f['estado'] == 'convertendo' and f['tentativas'] == 1 and not f['confirmada_em']
    assert jogo.livro() == []  # nenhum lm antes do sim


def test_registrar_nota_4_confirma_e_oferece_acender_luz_propria(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    f1 = _apagadas(plan)[0]
    s = _converter_ate_confirmar(monkeypatch, f1, nota=4)
    linhas = visivel(s).splitlines()
    assert linhas[0] == '◐ Nota 4 de 4 · a Luzia confirmou seu entendimento'
    assert 'Falta o seu sim' in visivel(s)
    primeiro = botoes_de(s)[0]
    assert primeiro['rotulo'] == 'Acender luz própria' and primeiro['rodar'] == f'confirmar {f1}'
    f = jogo._um(f1)
    assert f['estado'] == 'convertendo' and f['confirmada_em']  # ainda não é luz própria: falta o sim
    assert jogo.livro() == []
    s3 = _converter_ate_confirmar(monkeypatch, _apagadas(plan)[0], nota=3)  # nota 3 também confirma
    assert visivel(s3).splitlines()[0] == '◐ Nota 3 de 4 · a Luzia confirmou seu entendimento'


def test_confirmar_vira_luz_propria_e_mostra_o_ganho(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    f1 = _apagadas(plan)[0]
    antes = jogo._um(f1)
    _converter_ate_confirmar(monkeypatch, f1, nota=4)
    s = rodar(monkeypatch, 'confirmar', f1)
    v = visivel(s)
    abertura = v.splitlines()[0]
    pct = jogo.luz(plan)['por_prisma'][antes['skill_plano']]['pct']
    assert abertura == f"✦ **+{antes['valor_lm']} lm de luz própria** · DDD 0% → {pct}%", abertura
    assert pct > 0 and antes['titulo'] in v and 'Parabéns' not in v
    assert re.search(r'Júnior 3 → Plena  [█▓▒░]{12}  \d+% seu', v)
    f = jogo._um(f1)
    assert f['estado'] == 'propria' and f['lm_ganho'] == antes['valor_lm']
    assert [(x['lm'], x['luz'], x['ref']) for x in jogo.livro()] == [(antes['valor_lm'], 'propria', f1)]
    assert tem_rodape_botoes(s)
    s2 = rodar(monkeypatch, 'confirmar', f1)  # o segundo sim não lança lúmen de novo
    assert 'já é luz própria' in visivel(s2) and len(jogo.livro()) == 1


def test_confirmar_sem_a_luzia_ter_confirmado_explica(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    f1 = _apagadas(plan)[0]
    rodar(monkeypatch, 'fazer', f1)
    s = rodar(monkeypatch, 'confirmar', f1)
    assert 'ainda não confirmou' in visivel(s) and tem_rodape_botoes(s)
    assert jogo._um(f1)['estado'] == 'convertendo' and jogo.livro() == []
    assert 'não encontrada' in visivel(rodar(monkeypatch, 'confirmar', 'zzzz'))
    assert 'Use: confirmar' in visivel(rodar(monkeypatch, 'confirmar'))


def test_confirmar_no_marco_menciona_o_dossie(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    ids = _apagadas(plan)
    for i in ids[:-1]:
        _forcar_estado(i, 'propria')  # 2 de 3 próprias já passam de 1/3; o marco 1/3 dispara ao confirmar a próxima
    _converter_ate_confirmar(monkeypatch, ids[-1], nota=4)
    v = visivel(rodar(monkeypatch, 'confirmar', ids[-1]))
    assert re.search(r'✦ Marco \d de 3 · dossiê gerado em `.+dossie-.+\.md`', v), v


def test_converter_e_apelido_de_fazer(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    ids = _apagadas(plan)
    s = rodar(monkeypatch, 'converter', ids[0])
    v = visivel(s)
    assert v.startswith('## Luzia · Convertendo `#') and 'ROTEIRO PARA O AGENTE' in v and 'registrar' in v and 'confirmar' in v
    assert jogo._um(ids[0])['estado'] == 'convertendo' and tem_rodape_botoes(s)
    _forcar_estado(ids[1], 'refletida')
    rodar(monkeypatch, 'fazer', ids[1])
    assert jogo._um(ids[1])['estado'] == 'convertendo'
    p = visivel(rodar(monkeypatch, 'prompt', ids[2]))
    assert ids[2] in p and jogo._um(ids[2])['estado'] == 'convertendo'


def test_subir_explica_que_o_progresso_vem_de_converter(privado, monkeypatch):
    for argv in (('subir', DDD), ('subir',)):
        s = rodar(monkeypatch, *argv)
        v = visivel(s)
        assert 'O progresso agora vem de converter centelhas' in v and 'nível' in v
        assert 'Parabéns' not in v and len(v.splitlines()) <= 3
        assert botoes_de(s)[0]['rodar'] == 'centelhas --estado converter' and tem_rodape_botoes(s)


def test_comandos_de_nivel_e_lampejo_sairam(privado, monkeypatch):
    for comando in ('nivel', 'revisitar', 'lampejo', 'cartao', 'guardar'):
        monkeypatch.setattr(sys, 'argv', ['luzia', comando, DDD])
        with pytest.raises(SystemExit), redirect_stdout(io.StringIO()), contextlib_suprimir_stderr():
            cli.main()


def test_next_level_continua_apelido_da_trajetoria(privado, monkeypatch):
    assert visivel(rodar(monkeypatch, 'next-level')) == visivel(rodar(monkeypatch, 'trajetoria'))
    assert visivel(rodar(monkeypatch, 'rota')) == visivel(rodar(monkeypatch, 'trajetoria'))


def test_pedido_fluxo_completo_pelo_chat(privado, monkeypatch):
    recebidos = []

    def fake_run_plan(payload, schema=None, intro='', **kw):
        recebidos.append(payload)  # o payload é o que o código de verdade monta: pedido.nivel_solicitado / meta_solicitada
        ped = payload.get('pedido') or {}
        nivel = ped.get('nivel_solicitado') if ped.get('nivel_solicitado') is not None else 1
        meta = ped.get('meta_solicitada') if ped.get('meta_solicitada') is not None else 3
        res = {
            'nivel_partida': nivel,
            'meta': meta,
            'palavras_chave': ['opentelemetry', 'tracing', 'metrics'],
            'analise': f'Partida no nível {nivel} rumo à meta {meta} com foco em telemetria.',
            'acoes': [
                {
                    'titulo': 'Instrumentar endpoint crítico com tracing',
                    'tipo': 'praticar',
                    'skill': 'Observabilidade',
                    'dimensao': None,
                    'por_que': 'Dar visibilidade à latência real.',
                    'conceitos': ['tracing', 'span'],
                    'como': ['Escolher endpoint.', 'Adicionar span e medir.'],
                    'onde_explorar': 'Camada de entrada HTTP.',
                    'prompt': 'Me guie na instrumentação de um endpoint com tracing.',
                    'duracao_min': 20,
                }
            ],
        }
        reg = {
            'quando': '2026-11-12T15:00:00',
            'tempo_total_s': 0.5,
            'pico_memoria_mib': 10.0,
            'tokens_entrada': 50,
            'tokens_saida': 40,
            'versao': 'test',
            'modelo': 'gemini-2.5-flash',
        }
        return SimpleNamespace(plan=res), reg

    monkeypatch.setattr(pipeline, 'run_plan', fake_run_plan)

    s_abrir = rodar(monkeypatch, 'pedido', 'abrir', 'incluir', 'Observabilidade', '--motivo', 'Monitorar serviços')
    assert tem_rodape_botoes(s_abrir)
    botoes = botoes_de(s_abrir)
    rotulos = [b['rotulo'].lower() for b in botoes]
    assert any('aceitar' in r for r in rotulos)
    assert any('ajustar' in r for r in rotulos)
    assert any('recusar' in r for r in rotulos)

    with trajetoria.abrir() as con:
        lista = pedidos.listar(con)
        assert len(lista) == 1
        pid = lista[0]['id']

    s_ajustar = rodar(monkeypatch, 'pedido', 'ajustar', str(pid), '--nivel', '2', '--meta', '4')
    assert tem_rodape_botoes(s_ajustar)
    # o modelo recebeu o pedido de verdade (nível 2, meta 4) e a proposta impressa traz exatamente esses números
    assert recebidos[-1]['pedido']['nivel_solicitado'] == 2 and recebidos[-1]['pedido']['meta_solicitada'] == 4
    assert 'nível **2 → meta 4/5**' in visivel(s_ajustar)
    assert 'Partida no nível 2 rumo à meta 4' in visivel(s_ajustar)

    s_aceitar = rodar(monkeypatch, 'pedido', 'aceitar', str(pid))
    assert tem_rodape_botoes(s_aceitar)
    assert 'Observabilidade' in visivel(s_aceitar)

    s_traj = rodar(monkeypatch, 'trajetoria')
    v_traj = visivel(s_traj)
    assert re.search(r'Observabilidade  [█▓▒░]{12}  0%', v_traj)
    assert '1 por acender' in v_traj  # a centelha da proposta nasce apagada


def test_vocabulario_sem_termos_antigos(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    cat = jogo.sincronizar(plan)
    f1 = next(k for k, f in cat.items() if f['estado'] == 'apagada')

    with trajetoria.abrir() as con:
        eid = _semear_entrega(con)
    monkeypatch.setattr(entregas, 'atualizar', lambda con, dias=90: {'novas': 0, 'atualizadas': 0})

    saidas = [
        rodar(monkeypatch, 'hoje'),
        rodar(monkeypatch, 'trajetoria'),
        rodar(monkeypatch, 'centelhas'),
        rodar(monkeypatch, 'avancos', '--estado', 'todas'),
        rodar(monkeypatch, 'fila'),
        rodar(monkeypatch, 'fazer', f1),
        rodar(monkeypatch, 'registrar', f1, '--nota', '2', '--resumo', 'Falta o porquê'),
        rodar(monkeypatch, 'registrar', f1, '--nota', '3', '--resumo', 'Explicou bem'),
        rodar(monkeypatch, 'confirmar', f1),
        rodar(monkeypatch, 'subir', DDD),
        rodar(monkeypatch, 'entregas'),
        rodar(monkeypatch, 'entrega', str(eid)),
        rodar(monkeypatch, 'dossie'),
        rodar(monkeypatch, 'modo'),
    ]
    for s in saidas:
        texto = visivel(s)
        achado = RE_TERMOS_ANTIGOS.search(texto)
        assert achado is None, f'Termo antigo "{achado.group(0)}" encontrado na saída visível:\n{texto}'
        assert 'Parabéns' not in texto

    v_traj = visivel(rodar(monkeypatch, 'trajetoria'))
    assert '(prisma · skill)' not in v_traj and not re.search(r'\bPrisma [^(s]', v_traj)
    assert 'DDD  ' in v_traj and 'Domain-Driven Design' not in v_traj  # nome curto; o completo fica no painel

    v_modo = visivel(rodar(monkeypatch, 'modo'))
    assert 'em foco' in v_modo.lower() and 'lampejo' not in v_modo.lower()

    # o aviso do observador e a linha de status falam a mesma língua
    cartao = observer.cartao_refletida(DDD, 'Como isolar o domínio?', 'ab12', 30)
    assert '✦ Centelha da sessão · DDD · Como isolar o domínio? · 30 lm para converter' in cartao
    assert 'Prisma Domain' not in cartao and RE_TERMOS_ANTIGOS.search(cartao) is None

    linha_st = statusline.linha({'workspace': {'current_dir': str(privado)}})
    assert RE_TERMOS_ANTIGOS.search(linha_st) is None


def test_dossie_formal(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    cat = jogo.sincronizar(plan)
    f1 = next(k for k, f in cat.items() if f['estado'] == 'apagada' and f.get('skill_plano') == DDD)

    _converter_ate_confirmar(monkeypatch, f1, nota=4, resumo='Modelou agregado com invariantes claras')
    rodar(monkeypatch, 'confirmar', f1)

    # Pedido de mudança aceito (arquivar e reativar sem modelo)
    with trajetoria.abrir() as con:
        p = pedidos.abrir(con, 'arquivar', TESTES, 'Pausa temporária')
        pedidos.aceitar(con, p['id'])

    s = rodar(monkeypatch, 'dossie')
    assert tem_rodape_botoes(s)
    m = re.search(r'(C:[^\n]+dossie-[^\n]+\.md|/[^\n]+dossie-[^\n]+\.md)', visivel(s))
    assert m, f'Caminho do dossiê não encontrado em:\n{s}'
    conteudo = Path(m.group(1).strip()).read_text(encoding='utf-8')

    assert '## Ações com autoria própria' in conteudo
    assert '## Pedidos de mudança aceitos' in conteudo and '## Por skill' in conteudo
    assert 'pontos de evidência' in conteudo and 'autoria própria' in conteudo
    secao_proprias = conteudo.split('## Ações com autoria própria')[1].split('## Pedidos')[0]
    assert jogo._um(f1)['titulo'] in secao_proprias and 'nota 4/4' in secao_proprias
    assert 'Modelou agregado com invariantes claras' in secao_proprias
    assert 'Pausa temporária' in conteudo
    assert 'Histórico (modelo anterior' not in conteudo  # sem registro de níveis antigos, a seção não aparece


# ------------------------------------------------------------------ entrega: propriedade P1–P4 com base (A4)
def test_entrega_detalhe_mostra_p1_a_p4_com_base(privado, monkeypatch):
    with trajetoria.abrir() as con:
        eid = _semear_entrega(con)
        with banco.transacao(con):
            con.execute("INSERT INTO commit_ (hash, entrega_id, data, mensagem, arquivos, linhas, areas_json) "
                        "VALUES ('h1', ?, '2026-11-10T10:00:00', 'feat: agregado', 4, 90, '[\"C#/.NET\"]')", (eid,))
    s = rodar(monkeypatch, 'entrega', str(eid))
    v = visivel(s)
    assert 'None' not in v and 'n/d%' not in v
    assert re.search(r'P1 Direção no prompt: \*\*65\*\* \(inferido · geral\)', v), v
    assert re.search(r'P2 Coesão: \*\*100\*\* \(calculado\) — 100 − 0 \(4 arquivos\)', v), v
    assert 'P3 Aplicação de conceito: — falta você explicar' in v and 'P4 Decisão de arquitetura: — falta você defender' in v
    assert '**82% seu** (medido em P1 e P2)' in v, v
    assert '(s)' not in v and '2 commits' in v and '4 arquivos' in v  # plural de verdade
    assert tem_rodape_botoes(s)


# ------------------------------------------------------------------ pedidos: erros, sem modelo e leitura com base (A6–A8)
def _modelo_pedido(monkeypatch, modelo_nome='gemini/gemini-2.5-flash'):
    def fake(payload, **kw):
        ped = payload.get('pedido') or {}
        nv = ped.get('nivel_solicitado') if ped.get('nivel_solicitado') is not None else 1
        mt = ped.get('meta_solicitada') if ped.get('meta_solicitada') is not None else 3
        res = {'nivel_partida': nv, 'meta': mt, 'palavras_chave': ['tracing'], 'acoes': [],
               'analise': f'Partida no nível {nv} rumo à meta {mt}.'}
        return SimpleNamespace(plan=res, model=modelo_nome), {'quando': '2026-11-12T15:00:00', 'modelo': modelo_nome}

    monkeypatch.setattr(pipeline, 'run_plan', fake)


def test_pedido_mostra_analise_com_base_modelo_e_data(privado, monkeypatch):
    _modelo_pedido(monkeypatch)
    for argv in (('pedido', 'abrir', 'incluir', 'Observabilidade', '--motivo', 'Monitorar'),
                 ('pedido', 'ajustar', '1', '--nivel', '2', '--meta', '4')):
        v = visivel(rodar(monkeypatch, *argv))
        linha = next(l for l in v.splitlines() if 'Partida no nível' in l)
        assert '— Análise da Luzia, 12 nov' in linha and 'base: ' in linha and 'gemini/gemini-2.5-flash' in linha, linha


def test_pedido_erros_no_chat_terminam_em_botoes(privado, monkeypatch):
    _modelo_pedido(monkeypatch)
    s = rodar(monkeypatch, 'pedido', 'abrir', 'incluir', 'Observabilidade')
    assert tem_rodape_botoes(s)
    casos = [
        (('pedido', 'abrir', 'incluir', 'Observabilidade'), 'já existe um pedido em aberto'),
        (('pedido', 'abrir', 'inventado', 'Outro'), 'tipo de pedido inválido'),
        (('pedido', 'aceitar', 'abc'), 'número do pedido'),
        (('pedido', 'ajustar', '999'), 'pedido desconhecido'),
        (('pedido', 'aceitar', '1'), 'aceito'),
        (('pedido', 'aceitar', '1'), 'já foi aceito'),
        (('pedido', 'recusar', '1'), 'já foi aceito'),
        (('pedido', 'ajustar', '1', '--meta', '5'), 'já foi aceito'),
    ]
    for argv, esperado in casos:
        s = rodar(monkeypatch, *argv)
        assert esperado in visivel(s), (argv, s)
        assert tem_rodape_botoes(s), (argv, s)


def test_pedido_sem_modelo_nao_trava_a_pessoa(privado, monkeypatch):
    def sem_modelo(*a, **k):
        raise RuntimeError('Falta a chave GEMINI_API_KEY: configure em Ajustes > Modelo da Luzia.')

    monkeypatch.setattr(pipeline, 'run_plan', sem_modelo)
    s = rodar(monkeypatch, 'pedido', 'abrir', 'incluir', 'Observabilidade', '--nivel', '2', '--meta', '4')
    v = visivel(s)
    assert 'proposto' in v and 'nível **2 → meta 4/5**' in v and 'Sem análise: análise indisponível' not in v and 'Sem análise' in v
    assert any(b['rodar'] == 'pedido aceitar 1' for b in botoes_de(s))
    s = rodar(monkeypatch, 'pedido', 'abrir', 'incluir', 'Observabilidade')  # tentar de novo explica, não trava
    assert 'já existe um pedido em aberto' in visivel(s) and tem_rodape_botoes(s)
    s = rodar(monkeypatch, 'pedido', 'aceitar', '1')
    assert 'aceito' in visivel(s) and tem_rodape_botoes(s)
    with trajetoria.abrir() as con:
        assert {p['nome']: (p['nivel'], p['meta']) for p in trajetoria.prismas(con)}['Observabilidade'] == (2, 4)


def test_toda_leitura_impressa_tem_base_modelo_e_data(privado, monkeypatch):
    from luzia import leituras, modelo
    monkeypatch.setattr(entregas, 'atualizar', lambda con, dias=90: {'novas': 0, 'atualizadas': 0})
    monkeypatch.setattr(modelo, 'pronto', lambda: False)
    with trajetoria.abrir() as con:
        eid = _semear_entrega(con)
        b = leituras.base(con, 'entrega', str(eid))
        with banco.transacao(con):
            con.execute("INSERT INTO leitura (alvo_tipo, alvo_id, texto, base_json, base_hash, modelo, criado_em) "
                        "VALUES ('entrega', ?, 'Entrega focada no domínio.', ?, ?, 'gemini/teste', '2026-11-11T09:00:00')",
                        (str(eid), json.dumps(b), leituras.hash_base(b)))
    v = visivel(rodar(monkeypatch, 'entrega', str(eid)))
    linha = next(l for l in v.splitlines() if 'Entrega focada no domínio.' in l)
    assert 'base: 2 commits, 4 arquivos, 90 linhas, 1 prisma' in linha, linha
    assert '— Análise da Luzia, 11 nov' in linha and 'gemini/teste' in linha, linha
    v = visivel(rodar(monkeypatch, 'entregas'))  # a lista: uma linha por entrega, a análise só no detalhe
    assert f'**#{eid} Separa agregado de agendamento** · ' in v and 'Entrega focada no domínio.' not in v
    v = visivel(rodar(monkeypatch, 'trajetoria'))  # prisma sem análise: diz por quê, nunca fica vazio
    assert 'Sem análise: falta configurar o modelo' in v


# ------------------------------------------------------------------ entregas: sem atalho para as tarefas da IA (A2)
def test_sem_entrega_git_mostra_diagnostico_e_nunca_tarefas_da_ia(privado, monkeypatch):
    monkeypatch.setattr(pipeline, 'run_plan', lambda *a, **k: (_ for _ in ()).throw(AssertionError('sem modelo aqui')))
    for argv in (('entregas',), ('feedback-progress',), ('feedback-progress', '--rotulo', 'feedback-progress')):
        s = rodar(monkeypatch, *argv)
        v = visivel(s)
        assert 'Nenhuma entrega encontrada' in v, v
        assert 'cadastro de exemplo' not in v and 'cobertura do relatório' not in v  # tarefas_recentes (IA) fora
        assert 'Repositório:**' in v and 'não consegui ler o histórico git' in v
        assert 'E-mails do git:** Pessoa Teste' in v and 'Janela:** ainda não lida' in v
        rodar_bts = [b['rodar'] for b in botoes_de(s)]
        assert 'entregas --ampliar 180' in rodar_bts and 'identidade' in rodar_bts, rodar_bts


def test_identidade_confere_e_acrescenta_mostrando_o_email_para_a_dona(privado, monkeypatch):
    s = rodar(monkeypatch, 'identidade')
    assert 'Pessoa Teste' in visivel(s) and tem_rodape_botoes(s)
    s = rodar(monkeypatch, 'identidade', 'adicionar', 'pessoa.segunda@exemplo.test')
    v = visivel(s)
    assert 'pessoa.segunda@exemplo.test' in v and '***' not in v
    assert tem_rodape_botoes(s) and any(b['rodar'] == 'entregas' for b in botoes_de(s))
    with trajetoria.abrir() as con:
        assert 'pessoa.segunda@exemplo.test' in entregas.identidades(con)


# ------------------------------------------------------------------ avanços ligados a uma entrega: P3/P4 (A3)
def _acao_entrega(titulo, skill, dimensao):
    return {'titulo': titulo, 'tipo': 'explicar', 'skill': skill, 'dimensao': dimensao, 'por_que': 'Dono da decisão.',
            'conceitos': ['agregado'], 'como': ['Abra a entrega.', 'Explique com suas palavras.'],
            'onde_explorar': 'Os arquivos de domínio da entrega.', 'prompt': 'Me pergunte uma coisa por vez.',
            'duracao_min': 15}


def _modelo_entrega(monkeypatch, chamadas):
    def fake(payload, schema=None, **kw):
        chamadas.append({'payload': payload, 'schema': schema})
        acoes_ = [_acao_entrega('Explicar o agregado desta entrega', 'Prisma inventado', None),
                  _acao_entrega('Defender a separação do agregado', DDD, 'P3')]
        reg = {'quando': '2026-11-12T15:00:00', 'modelo': 'gemini/teste', 'tempo_total_s': 0.1, 'pico_memoria_mib': 1,
               'tokens_entrada': 1, 'tokens_saida': 1, 'versao': 't'}
        return SimpleNamespace(plan={'acoes': acoes_}, model='gemini/teste'), reg

    monkeypatch.setattr(pipeline, 'run_plan', fake)


def test_acender_entrega_liga_avancos_e_acende_p3(privado, monkeypatch):
    from luzia import planner
    chamadas = []
    _modelo_entrega(monkeypatch, chamadas)
    with trajetoria.abrir() as con:
        eid = _semear_entrega(con)
    s = rodar(monkeypatch, 'entrega', str(eid))
    assert f'acender-entrega {eid}' in [b['rodar'] for b in botoes_de(s)]

    s = rodar(monkeypatch, 'acender-entrega', str(eid))
    assert tem_rodape_botoes(s) and len(chamadas) == 1 and chamadas[0]['schema'] == planner.ENTREGA_SCHEMA
    enviado = chamadas[0]['payload']
    assert set(enviado) == {'entrega'} and set(enviado['entrega']) == {'titulo', 'periodo', 'fatos', 'prismas'}
    assert enviado['entrega']['prismas'] == [{'prisma': DDD, 'termos': ['aggregate', 'domain']}]
    with trajetoria.abrir() as con:
        ligados = [a for a in jogo.avancos(con) if a.get('entrega_id') == eid]
    assert sorted(a['dimensao'] for a in ligados) == ['P3', 'P4']
    assert {a['skill_plano'] for a in ligados} == {DDD} and {a['origem'] for a in ligados} == {'entrega'}
    assert all(a['estado'] == 'refletida' and 10 <= a['valor_lm'] <= 100 for a in ligados)  # o agente aplicou o conceito
    assert all(a['entrega_id'] == eid and a['onde'] == f'entrega #{eid}' for a in ligados)
    p3 = next(a for a in ligados if a['dimensao'] == 'P3')
    assert p3['titulo'] == 'Explicar o agregado desta entrega'  # a primeira é sempre a P3

    s = rodar(monkeypatch, 'acender-entrega', str(eid))  # já há P3 e P4 abertos: não chama o modelo de novo
    assert 'já tem centelhas P3 e P4 abertas' in visivel(s) and len(chamadas) == 1 and tem_rodape_botoes(s)

    rodar(monkeypatch, 'fazer', p3['id'])
    assert 'propriedade agora' not in visivel(rodar(monkeypatch, 'registrar', p3['id'], '--nota', '4',
                                                    '--resumo', 'Explicou as invariantes do agregado'))
    s = rodar(monkeypatch, 'confirmar', p3['id'])  # a propriedade só muda com o sim: a centelha vira luz própria
    assert 'propriedade agora' in visivel(s)
    v = visivel(rodar(monkeypatch, 'entrega', str(eid)))
    assert 'P3 Aplicação de conceito: **100** (evidência)' in v and 'Explicou as invariantes do agregado' in v
    assert 'P4 Decisão de arquitetura: — falta você defender' in v


def test_acender_entrega_sem_modelo_nao_grava_nada(privado, monkeypatch):
    monkeypatch.setattr(pipeline, 'run_plan', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('Falta a chave X')))
    with trajetoria.abrir() as con:
        eid = _semear_entrega(con)
    s = rodar(monkeypatch, 'acender-entrega', str(eid))
    assert 'Falta a chave X' in visivel(s) and tem_rodape_botoes(s)
    with trajetoria.abrir() as con:
        assert not [a for a in jogo.avancos(con) if a.get('entrega_id') == eid]
    s = rodar(monkeypatch, 'acender-entrega', '999')
    assert 'entrega não encontrada' in visivel(s) and tem_rodape_botoes(s)


# ------------------------------------------------------------------ leituras pelo chat (A5)
def _leituras_falsas(monkeypatch, chamadas):
    def fake(payload, schema=None, **kw):
        chamadas.append(payload)
        lt = [{'alvo': a['alvo'], 'texto': f"Leitura de {a['alvo']}."} for a in payload['alvos']]
        return SimpleNamespace(plan={'leituras': lt}, model='gemini/teste'), {'quando': '2026-11-12T10:00:00',
                                                                               'modelo': 'gemini/teste'}
    monkeypatch.setattr(pipeline, 'run_plan', fake)


def test_leituras_pelo_chat(privado, monkeypatch):
    from luzia import leituras, modelo
    monkeypatch.setattr(modelo, 'pronto', lambda: False)
    s = rodar(monkeypatch, 'leituras')
    assert 'sem análise: falta configurar o modelo' in visivel(s) and tem_rodape_botoes(s)
    assert all(b['rodar'] != 'leituras' for b in botoes_de(rodar(monkeypatch, 'hoje')))
    assert '## Luzia · Análises' in visivel(rodar(monkeypatch, 'analises'))  # apelido de `leituras`

    monkeypatch.setattr(modelo, 'pronto', lambda: True)
    with trajetoria.abrir() as con:
        n = len(leituras.vencidas(con))
    assert n == 3  # os 3 prismas do plano, ainda sem leitura
    for cmd in ('hoje', 'trajetoria'):
        bts = botoes_de(rodar(monkeypatch, cmd))
        assert {'rotulo': 'Atualizar 3 análises', 'rodar': 'leituras'}.items() <= next(
            b for b in bts if b['rodar'] == 'leituras').items(), (cmd, bts)

    monkeypatch.setattr(pipeline, 'run_plan', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('sem internet')))
    s = rodar(monkeypatch, 'leituras')
    assert 'nada foi gravado' in visivel(s) and tem_rodape_botoes(s)

    chamadas = []
    _leituras_falsas(monkeypatch, chamadas)
    s = rodar(monkeypatch, 'leituras')
    assert '3 análises atualizadas' in visivel(s) and len(chamadas) == 1  # um lote, uma chamada
    assert 'Todas as análises estão em dia' in visivel(rodar(monkeypatch, 'leituras'))
    v = visivel(rodar(monkeypatch, 'trajetoria'))
    assert f'Leitura de prisma:{DDD}. _— Análise da Luzia, 12 nov · base: ' in v and 'gemini/teste' in v
    assert all(b['rodar'] != 'leituras' for b in botoes_de(rodar(monkeypatch, 'hoje')))


def test_erros_do_motor_ja_nascem_no_vocabulario_novo(privado, monkeypatch):
    """Sem tradução na hora de exibir: o painel (que recebe o texto cru) e o chat mostram as mesmas palavras."""
    plan = pipeline.load_state()['plano']
    fid = _apagadas(plan)[0]
    mensagens = [
        jogo.avaliar('zzzz', 3, 'x', plan)['erro'],               # centelha inexistente
        jogo.avaliar(fid, 3, 'x', plan)['erro'],                  # ainda não está em conversão
        jogo.confirmar('zzzz', plan)['erro'],
        jogo.confirmar(fid, plan)['erro'],                        # a Luzia ainda não confirmou
    ]
    for m in mensagens:
        assert RE_TERMOS_ANTIGOS.search(m) is None, m
    saida = visivel(rodar(monkeypatch, 'registrar', fid, '--nota', '3', '--resumo', 'x'))
    assert RE_TERMOS_ANTIGOS.search(saida) is None and 'centelha' in saida
    assert not hasattr(cli, '_vocab_novo')


def test_acender_sem_modelo_no_chat_nao_quebra_nem_grava(privado, monkeypatch):
    monkeypatch.setattr(pipeline, 'run_plan', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('sem modelo')))
    jogo.sincronizar(pipeline.load_state()['plano'])
    antes = len(jogo.catalogo(pipeline.load_state()['plano']))
    s = rodar(monkeypatch, 'acender', DDD)
    assert 'não deu para acender' in visivel(s) and tem_rodape_botoes(s)
    assert len(jogo.catalogo(pipeline.load_state()['plano'])) == antes


def test_entrega_no_chat_mostra_titulo_real_e_numero_do_ticket(privado, monkeypatch):
    jogo.sincronizar(pipeline.load_state()['plano'])
    with trajetoria.abrir() as con, banco.transacao(con):
        eid = con.execute(
            "INSERT INTO entrega (chave, titulo, inicio, fim, fonte, commits, arquivos, linhas, areas_json, ids_privados_json) "
            "VALUES ('tk-x', 'Bug 14988: ProdutoZeta corrige mapa', '2026-11-10T10:00:00', '2026-11-11T10:00:00', "
            "'ticket', 1, 1, 5, '[]', '[\"14988\"]')").lastrowid
    monkeypatch.setattr(entregas, 'atualizar', lambda con, dias=90: {'novas': 0, 'atualizadas': 0})
    v = visivel(rodar(monkeypatch, 'entrega', eid))
    assert 'Bug 14988: ProdutoZeta corrige mapa' in v and '#14988' in v
    v = visivel(rodar(monkeypatch, 'entregas'))
    assert 'Bug 14988: ProdutoZeta corrige mapa' in v


# --- teste com testadores (24/11): validação da CLI ---

@pytest.mark.parametrize('nota', ['7', '5', '-1', 'abc', '2.5'])
def test_nota_fora_de_0_a_4_nao_registra_nada(privado, monkeypatch, nota):
    plan = pipeline.load_state()['plano']
    fid = _apagadas(plan)[0]
    rodar(monkeypatch, 'fazer', fid)
    s = rodar(monkeypatch, 'registrar', fid, f'--nota={nota}', '--resumo', 'x')
    assert 'A nota vai de 0 a 4' in s and 'confirmou' not in s and tem_rodape_botoes(s)
    assert jogo.sincronizar(plan)[fid].get('confirmada_em') in (None, '')
    assert jogo.avaliar(fid, 7, 'x', plan) == {'erro': 'a nota vai de 0 a 4'}


def test_registrar_id_inexistente_e_comandos_sem_id(privado, monkeypatch):
    assert 'Centelha zzzz não encontrada.' in rodar(monkeypatch, 'registrar', 'zzzz', '--nota', '3', '--resumo', 'x')
    for cmd in ('converter', 'descartar', 'restaurar', 'enviar'):
        s = rodar(monkeypatch, cmd)
        assert f'Use: {cmd} <id>' in s and 'Centelha  não' not in s, cmd


def test_nota_baixa_diz_o_que_falta_pela_rubrica(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    fid = _apagadas(plan)[0]
    s = _converter_ate_confirmar(monkeypatch, fid, nota=2, resumo='explicou parte')
    assert 'O que você mostrou: explicou parte' in s and 'Para converter, falta: comparou com uma alternativa' in s


def test_acender_sem_prisma_pergunta_e_nao_gera_nada(privado, monkeypatch):
    chamado = []
    monkeypatch.setattr(cli, 'gerar_trecho', lambda *a, **k: chamado.append(a) or {'erro': 'x'})
    s = rodar(monkeypatch, 'acender', '')
    assert chamado == [] and 'Para qual prisma?' in s and all(b['rodar'].startswith('acender ') for b in botoes_de(s))
