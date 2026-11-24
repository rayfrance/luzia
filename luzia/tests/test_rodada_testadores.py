"""Achados da rodada de testes orquestrada de 24/11/2026 (CLI, pedidos, dossiê e painel)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from luzia import jogo, pipeline, server
from luzia.tests.test_cli import botoes_de, rodar, visivel

DDD = 'Domain-Driven Design (DDD)'


def _modelo(monkeypatch):
    def fake(payload, **kw):
        res = {'palavras_chave': ['logs', 'métricas', 'tracing'], 'analise': 'Faz sentido para a meta.',
               'acoes': [{'titulo': f'Observar {i}', 'tipo': 'praticar', 'skill': 'Observabilidade', 'dimensao': None,
                          'por_que': 'x', 'conceitos': ['logs'], 'como': ['a', 'b'], 'onde_explorar': 'x', 'prompt': 'x',
                          'duracao_min': 15} for i in range(3)]}
        return SimpleNamespace(plan=res, model='m/x'), {'quando': '2026-11-24T15:00:00', 'modelo': 'm/x'}

    monkeypatch.setattr(pipeline, 'run_plan', fake)


def test_comando_desconhecido_responde_em_portugues_com_botoes(privado, monkeypatch, capsys):
    import sys
    from luzia import cli
    for argv, esperado in ((['foo'], '`foo` não é um comando da Luzia'), (['arquivar', 'X'], 'pedido abrir arquivar')):
        monkeypatch.setattr(sys, 'argv', ['luzia', *argv])
        with pytest.raises(SystemExit):
            cli.main()
        saida = capsys.readouterr()
        assert esperado in saida.out and 'LUZIA_BOTOES=' in saida.out and 'usage:' not in saida.out + saida.err


def test_pedido_de_arquivar_ou_reativar_prisma_que_nao_existe_e_recusado(privado, monkeypatch):
    for tipo in ('arquivar', 'reativar'):
        s = visivel(rodar(monkeypatch, 'pedido', 'abrir', tipo, 'Fantasma', '--motivo', 'x'))
        assert 'prisma desconhecido: Fantasma' in s, s
    s = visivel(rodar(monkeypatch, 'pedido', 'abrir', 'reativar', DDD, '--motivo', 'x'))
    assert 'já está ativo' in s


def test_aceitar_mostra_o_alvo_real_e_o_avanco_antes_e_depois(privado, monkeypatch):
    _modelo(monkeypatch)
    plan = pipeline.load_state()['plano']
    f = next(c for c in jogo.sincronizar(plan).values() if c['skill_plano'] == DDD)
    jogo.iniciar(f['id'])
    jogo.avaliar(f['id'], 4, 'x', plan)
    jogo.confirmar(f['id'], plan)
    abrir = rodar(monkeypatch, 'pedido', 'abrir', 'incluir', 'Observabilidade', '--motivo', 'monitorar a API')
    assert 'logs, métricas, tracing' in abrir and 'nível' not in visivel(abrir).lower()
    s = visivel(rodar(monkeypatch, 'pedido', 'aceitar', '1'))
    alvo = jogo.luz(pipeline.load_state()['plano'])['por_prisma']['Observabilidade']['alvo_lm']
    assert f'entrou com alvo de **{alvo} lm**' in s
    assert 'Avanço da trajetória:' in s and '→' in s and 'continua toda sua' in s


def test_dossie_usa_o_alvo_por_prisma(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    jogo.sincronizar(plan)
    texto = jogo.dossie(plan, 'teste').read_text(encoding='utf-8')
    # linguagem formal ("pontos de evidência", "ações"), mas contando contra o alvo de cada skill, como o avanço
    assert 'do alvo em autoria própria' in texto and 'pontos de evidência do alvo da meta' in texto


def test_planner_nao_pede_niveis_ao_modelo():
    from luzia import planner
    for schema in (planner.TRECHO_SCHEMA, planner.OPPORTUNITIES_SCHEMA):
        assert 'nível' not in schema
    assert 'nunca escreva "nível"' in planner.SYSTEM if hasattr(planner, 'SYSTEM') else True


def test_painel_orienta_quando_nao_ha_nada_para_converter_e_tutorial_explica_p1_a_p4():
    js = (Path(server.PAINEL) / 'luzia.js').read_text(encoding='utf-8')
    assert 'Nada para converter ainda' in js and 'data-filtro-estado="apagada"' in js
    tutorial = js.split('const PASSOS_TUTORIAL', 1)[1].split('let tutorial = null', 1)[0]
    for termo in ('lúmens (lm)', '<b>P1</b>', '<b>P4</b>', 'falta a nota e o seu sim'):
        assert termo in tutorial, termo
    assert 'btn neutro mini' not in tutorial and "setAttribute('aria-labelledby', 'gaveta-titulo')" in js
