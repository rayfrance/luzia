"""Provedores de modelo (27/11/2026): a pessoa escolhe a chave (Anthropic, OpenAI, Gemini ou compatível);
NVIDIA, Groq e OpenRouter vêm com o endereço pronto e são sugestões gratuitas, nunca exigência."""

from __future__ import annotations

import sys
import types

import pytest

from luzia import modelo


class _Uso:
    prompt_tokens = 3
    completion_tokens = 2


def _openai_falso(monkeypatch, erros: list | None = None):
    """Instala um `openai` falso que registra o cliente e cada chamada; `erros` são levantados em ordem."""
    reg = {'clientes': [], 'chamadas': []}
    erros = list(erros or [])

    class _Completions:
        def create(self, **kw):
            reg['chamadas'].append(kw)
            if erros:
                raise erros.pop(0)
            msg = types.SimpleNamespace(content='{"ok": true}')
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)], usage=_Uso(), model=kw['model'])

    class OpenAI:
        def __init__(self, **kw):
            reg['clientes'].append(kw)
            self.chat = types.SimpleNamespace(completions=_Completions())

    import importlib.machinery

    mod = types.ModuleType('openai')
    mod.__spec__ = importlib.machinery.ModuleSpec('openai', None)  # o "SDK instalado" do status
    mod.OpenAI = OpenAI
    monkeypatch.setitem(sys.modules, 'openai', mod)
    return reg


def test_nvidia_usa_o_endereco_fixo_e_a_chave_propria(privado, monkeypatch):
    reg = _openai_falso(monkeypatch)
    monkeypatch.setenv('NVIDIA_API_KEY', 'nvapi-teste')
    modelo.salvar('nvidia', 'z-ai/glm-5.3-flash')
    r = modelo.chamar('p', 's')
    assert reg['clientes'][0]['base_url'] == 'https://integrate.api.nvidia.com/v1'
    assert reg['clientes'][0]['api_key'] == 'nvapi-teste'
    assert r['provedor'] == 'nvidia' and r['texto'] == '{"ok": true}'


def test_cada_provedor_gratuito_tem_endereco_e_site_e_a_escolha_e_livre():
    gratis = {k for k, v in modelo.PROVEDORES.items() if v.get('gratuito')}
    assert gratis == {'gemini', 'nvidia', 'groq', 'openrouter'}
    assert {'anthropic', 'openai'} <= set(modelo.PROVEDORES)  # pagos continuam à escolha
    for k in gratis - {'gemini'}:
        assert modelo.PROVEDORES[k]['url'].startswith('https://') and modelo.PROVEDORES[k]['site'].startswith('https://')
    assert len({v['chave'] for v in modelo.PROVEDORES.values()}) == len(modelo.PROVEDORES)  # trocar não apaga a outra


def test_modelo_sem_modo_json_e_pedido_de_novo_sem_ele(monkeypatch):
    reg = _openai_falso(monkeypatch, [RuntimeError("400 'response_format' is not supported by this model")])
    texto, *_ = modelo._openai('m', 'p', 's', 'k', 'https://exemplo/v1')
    assert texto == '{"ok": true}'
    assert 'response_format' in reg['chamadas'][0] and 'response_format' not in reg['chamadas'][1]


def test_testar_tem_limite_curto_tambem_fora_do_gemini(monkeypatch):
    reg = _openai_falso(monkeypatch)
    modelo._openai('m', 'p', 's', 'k', '', rapido=True)
    assert reg['clientes'][0]['timeout'] == modelo.TEMPO_RAPIDO and reg['clientes'][0]['max_retries'] == 0


def test_erro_de_chave_e_de_limite_viram_mensagem_clara(privado, monkeypatch):
    _openai_falso(monkeypatch, [RuntimeError('Error code: 401 - invalid_api_key')])
    modelo.salvar('groq', 'openai/gpt-oss-120b')
    monkeypatch.setenv('GROQ_API_KEY', 'gsk_teste')
    with pytest.raises(RuntimeError, match='chave sem permissão ou inválida'):
        modelo.chamar('p', 's')
    assert 'limite de uso' in modelo.resumo_erro(RuntimeError('Error code: 429 rate_limit_exceeded'))
    assert 'Groq' in modelo.resumo_erro(RuntimeError('503 Service Unavailable'))  # nunca "o Gemini" para outro provedor
