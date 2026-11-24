"""Tutorial de primeiro uso do painel (24/11/2026): abre sozinho uma vez depois da triagem e de novo por Ajustes."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from luzia import entregas, jogo, pipeline, server

PAINEL = Path(server.PAINEL)


@pytest.fixture
def api(servidor, monkeypatch):
    jogo.sincronizar(pipeline.load_state()['plano'])
    monkeypatch.setattr(entregas, 'atualizar', lambda con, dias=90: {'novas': 0, 'atualizadas': 0})
    servidor.entrar()
    return lambda metodo, caminho, corpo=None: servidor.pedir(metodo, caminho, corpo)[:2]


def test_estado_diz_se_o_tutorial_ja_foi_visto_e_a_rota_grava(api):
    code, st = api('GET', '/api/estado')
    assert code == 200 and st['tutorial_visto'] is False  # primeira vez: o painel abre o tutorial
    assert api('POST', '/api/tutorial', {'visto': True}) == (200, {'ok': True, 'visto': True})
    assert api('GET', '/api/estado')[1]['tutorial_visto'] is True
    api('POST', '/api/tutorial', {'visto': False})  # rever pelo Ajustes não depende disso, mas a rota desfaz
    assert api('GET', '/api/estado')[1]['tutorial_visto'] is False


def test_rota_do_tutorial_exige_sessao(servidor):
    servidor.cookie = None
    assert servidor.pedir('POST', '/api/tutorial', {'visto': True})[0] == 401


def test_painel_tem_o_tutorial_acessivel_e_o_botao_de_rever():
    js = (PAINEL / 'luzia.js').read_text(encoding='utf-8')
    html = (PAINEL / 'index.html').read_text(encoding='utf-8')
    assert 'id="tutorial" role="dialog" aria-modal="true" aria-labelledby="tt-titulo"' in html
    lista = js.split('const PASSOS_TUTORIAL', 1)[1].split('let tutorial = null', 1)[0]
    passos = re.findall(r"\{ titulo: '([^']+)'", lista)
    assert 6 <= len(passos) <= 9, passos
    assert 'data-tutorial="1"' in js and 'Rever o tutorial' in js  # Ajustes
    assert "ev.key === 'Escape'" in js and "'ArrowRight'" in js and "'ArrowLeft'" in js
    assert "api('/api/tutorial', { visto: true })" in js and '!E.tutorial_visto' in js
    corpo = js.split('const PASSOS_TUTORIAL', 1)[1].split('let tutorial = null', 1)[0]
    assert 'nível' not in corpo.lower() and 'senha' not in corpo.lower()
