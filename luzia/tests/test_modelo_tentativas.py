"""Chamada ao Gemini sem modelo reserva (24/11/2026): o gemini-2.5-flash foi aposentado para contas novas e mascarava o
erro do modelo principal como "modelo não encontrado". Agora: erro passageiro tenta de novo o mesmo modelo; erro
definitivo para na hora, com a causa verdadeira."""

from __future__ import annotations

import sys
import types

import pytest

from luzia import modelo


class _Resp:
    text = '{"ok": true}'
    usage_metadata = types.SimpleNamespace(prompt_token_count=3, candidates_token_count=2)


def _sdk_falso(monkeypatch, respostas: list):
    """Instala um `google.genai` falso: cada chamada consome um item (exceção a levantar ou resposta)."""
    chamados: list[str] = []

    class _Modelos:
        def generate_content(self, model, contents, config):
            chamados.append(model)
            item = respostas.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

    class _Cliente:
        def __init__(self, **kw):
            self.models = _Modelos()

    genai = types.ModuleType('google.genai')
    genai.Client = _Cliente
    tipos = types.ModuleType('google.genai.types')
    for nome in ('HttpOptions', 'GenerateContentConfig', 'AutomaticFunctionCallingConfig'):
        setattr(tipos, nome, lambda **kw: kw)
    genai.types = tipos
    google = types.ModuleType('google')
    google.genai = genai
    monkeypatch.setitem(sys.modules, 'google', google)
    monkeypatch.setitem(sys.modules, 'google.genai', genai)
    monkeypatch.setitem(sys.modules, 'google.genai.types', tipos)
    monkeypatch.setattr(modelo.time, 'sleep', lambda s: None)
    return chamados


def test_erro_passageiro_tenta_de_novo_o_mesmo_modelo(monkeypatch):
    chamados = _sdk_falso(monkeypatch, [RuntimeError('503 UNAVAILABLE: model overloaded'), _Resp()])
    texto, *_ , usado = modelo._gemini('gemini-3.5-flash-lite', 'p', 's', 'k')
    assert texto == '{"ok": true}' and usado == 'gemini-3.5-flash-lite'
    assert chamados == ['gemini-3.5-flash-lite', 'gemini-3.5-flash-lite']  # nunca um modelo reserva


def test_erro_definitivo_para_na_hora_com_a_causa_do_modelo_principal(monkeypatch):
    chamados = _sdk_falso(monkeypatch, [RuntimeError("403 PERMISSION_DENIED: API key not valid")])
    with pytest.raises(RuntimeError, match='chave sem permissão ou inválida'):
        modelo._gemini('gemini-3.5-flash-lite', 'p', 's', 'k')
    assert chamados == ['gemini-3.5-flash-lite']


def test_sobrecarga_que_insiste_vai_para_as_reservas_atuais_e_avisa(monkeypatch):
    sobrecarga = RuntimeError('503 UNAVAILABLE: This model is currently experiencing high demand')
    chamados = _sdk_falso(monkeypatch, [sobrecarga] * 2 + [_Resp()])
    *_, usado = modelo._gemini('gemini-3.5-flash-lite', 'p', 's', 'k')
    # sobrecarga: 2 tentativas no escolhido e logo a reserva (insistir no pico só atrasa a triagem)
    assert chamados == ['gemini-3.5-flash-lite'] * 2 + [modelo.RESERVAS_GEMINI[0]] and usado == modelo.RESERVAS_GEMINI[0]


def test_tudo_falhando_mostra_o_erro_do_principal_e_pula_reserva_que_nao_existe(monkeypatch):
    sobrecarga = RuntimeError('503 UNAVAILABLE: high demand')
    sumiu = RuntimeError('404 NOT_FOUND: no longer available')
    chamados = _sdk_falso(monkeypatch, [sobrecarga] * 2 + [sumiu, sobrecarga])
    with pytest.raises(RuntimeError, match='sobrecarregado'):
        modelo._gemini('gemini-3.5-flash-lite', 'p', 's', 'k')
    assert chamados == ['gemini-3.5-flash-lite'] * 2 + list(modelo.RESERVAS_GEMINI)


def test_mensagem_clara_para_sobrecarga():
    assert 'sobrecarregado' in modelo.resumo_erro(RuntimeError("503 UNAVAILABLE. {'error': {'message': 'high demand'}}"))


def test_nao_ha_mais_modelo_reserva_aposentado():
    import inspect
    assert not any(m.startswith('gemini-2.5') for m in modelo.RESERVAS_GEMINI)  # aposentados para contas novas
