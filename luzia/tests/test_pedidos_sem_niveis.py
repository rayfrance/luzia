"""Pedidos de mudança sem níveis: a proposta fala de prisma, palavras-chave, centelhas iniciais e alvo (lm)."""

import re
import sys
import io
from contextlib import redirect_stdout
from types import SimpleNamespace

import pytest

from luzia import cli, pedidos, pipeline, planner, trajetoria


def rodar(monkeypatch, *argv: str) -> str:
    monkeypatch.setattr(sys, 'argv', ['luzia', *[str(a) for a in argv]])
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main()
    return buf.getvalue()


def visivel(saida: str) -> str:
    return '\n'.join(l for l in saida.splitlines() if not l.startswith('LUZIA_'))


def botoes(saida: str) -> list[dict]:
    import json
    linha = next((x for x in saida.splitlines() if x.startswith('LUZIA_BOTOES=')), None)
    return json.loads(linha.split('=', 1)[1]) if linha else []


def _modelo(monkeypatch, recebidos: list):
    def fake(payload, schema=None, intro='', **kw):
        recebidos.append(payload)
        res = {
            'palavras_chave': ['tracing', 'opentelemetry'],
            'analise': 'Telemetria ajuda a ver a latência real.',
            'acoes': [{'titulo': 'Instrumentar um endpoint com tracing', 'tipo': 'praticar', 'skill': 'Observabilidade',
                       'dimensao': None, 'por_que': 'x', 'conceitos': ['span'], 'como': ['a'],
                       'onde_explorar': 'HTTP', 'prompt': 'p', 'duracao_min': 20}],
        }
        return SimpleNamespace(plan=res, model='gemini/teste'), {'quando': '2026-11-24T10:00:00', 'modelo': 'gemini/teste'}

    monkeypatch.setattr(pipeline, 'run_plan', fake)


def test_proposta_sem_nivel_com_alvo(privado, monkeypatch):
    _modelo(monkeypatch, [])
    s = rodar(monkeypatch, 'pedido', 'abrir', 'incluir', 'Observabilidade', '--motivo', 'Monitorar')
    v = visivel(s)
    assert 'nível' not in v.lower() and 'níveis' not in v.lower() and not re.search(r'\d/5', v), v
    assert 'alvo' in v and 'lm' in v and 'nova versão' in v
    assert 'Instrumentar um endpoint com tracing' in v and 'tracing' in v
    assert all('nível' not in (b['rotulo'] + b.get('descricao', '')).lower() for b in botoes(s))


def test_proposta_sem_modelo_usa_alvo_padrao(privado, monkeypatch):
    from luzia import jogo

    def sem(*a, **k):
        raise RuntimeError('sem chave')

    monkeypatch.setattr(pipeline, 'run_plan', sem)
    v = visivel(rodar(monkeypatch, 'pedido', 'abrir', 'incluir', 'Observabilidade'))
    assert f'{jogo.ALVO_PADRAO} lm' in v and 'nível' not in v.lower()
    with trajetoria.abrir() as con:
        assert pedidos.listar(con)[0]['proposta']['alvo_estimado_lm'] == jogo.ALVO_PADRAO


def test_ajustar_com_palavras_troca_as_palavras(privado, monkeypatch):
    recebidos = []
    _modelo(monkeypatch, recebidos)
    rodar(monkeypatch, 'pedido', 'abrir', 'incluir', 'Observabilidade')
    s = rodar(monkeypatch, 'pedido', 'ajustar', '1', '--palavras', 'prometheus, grafana, logs',
              '--motivo', 'quero algo de métricas')
    v = visivel(s)
    assert 'prometheus' in v and 'grafana' in v and 'nível' not in v.lower()
    with trajetoria.abrir() as con:
        prop = pedidos.listar(con)[0]['proposta']
    assert prop['palavras_chave'] == ['prometheus', 'grafana', 'logs']
    assert recebidos[-1]['pedido']['nota_da_pessoa'] == 'quero algo de métricas'
    assert 'nivel_solicitado' not in recebidos[-1]['pedido']


def test_ajustar_sem_flags_nao_pede_numero(privado, monkeypatch):
    _modelo(monkeypatch, [])
    rodar(monkeypatch, 'pedido', 'abrir', 'incluir', 'Observabilidade')
    s = rodar(monkeypatch, 'pedido', 'ajustar', '1')
    v = visivel(s)
    assert '--palavras' in v and '--motivo' in v
    assert 'nível' not in v.lower() and '0 a 5' not in v and '1 a 5' not in v
    assert botoes(s) and any(l.startswith('LUZIA_BOTOES=') for l in s.splitlines())


def test_ajustar_aceita_nivel_e_meta_antigos_sem_erro(privado, monkeypatch):
    _modelo(monkeypatch, [])
    rodar(monkeypatch, 'pedido', 'abrir', 'incluir', 'Observabilidade')
    v = visivel(rodar(monkeypatch, 'pedido', 'ajustar', '1', '--nivel', '2', '--meta', '4', '--palavras', 'a, b'))
    assert 'ajustado' in v and 'nível' not in v.lower()


def test_arquivar_diz_que_a_luz_sai_e_volta(privado, monkeypatch):
    v = visivel(rodar(monkeypatch, 'pedido', 'abrir', 'arquivar', 'Domain-Driven Design (DDD)'))
    assert 'luz' in v and 'reativar' in v and 'nível' not in v.lower()


def test_schema_nao_pede_nivel_nem_meta():
    assert 'nivel_partida' not in planner.PEDIDO_SCHEMA and '"meta"' not in planner.PEDIDO_SCHEMA
    assert 'palavras_chave' in planner.PEDIDO_SCHEMA and 'acoes' in planner.PEDIDO_SCHEMA and 'analise' in planner.PEDIDO_SCHEMA
