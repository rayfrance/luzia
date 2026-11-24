"""SessionStart logo depois da triagem e o porteiro dos hooks (sai cedo sem importar o resto)."""

import json
import re

import pytest

from luzia import jogo, observer, pipeline, porteiro

DDD = 'Domain-Driven Design (DDD)'
LINHA = re.compile(r'✦ Luzia \(em foco\): (\d+) centelhas? na sua meta para acender · /luzia:hoje para começar\.')


@pytest.fixture
def plan(privado):
    plano = pipeline.load_state()['plano']
    jogo.sincronizar(plano)  # a triagem acabou de acender a meta: só centelhas apagadas
    return plano


def _inicio(privado, modo='ativo', cwd=None):
    cfg = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))
    cfg['modo'] = modo
    return {'session_id': 's-inicio', 'hook_event_name': 'SessionStart', 'cwd': cwd or cfg['autorizados'][0]}, cfg


def _contexto(capsys) -> str:
    saida = capsys.readouterr().out
    return json.loads(saida)['hookSpecificOutput']['additionalContext'] if saida.strip() else ''


@pytest.mark.parametrize('modo', ['ativo', 'passivo'])
def test_so_apagadas_pede_a_linha_para_acender(privado, plan, capsys, modo):
    observer.ao_iniciar_sessao(*_inicio(privado, modo))
    ctx = _contexto(capsys)
    m = LINHA.search(ctx)
    assert m and int(m.group(1)) == 3  # a trajetória sintética tem 3 centelhas apagadas
    assert ctx.startswith('[Luzia · em foco · início]')


def test_com_luz_propria_e_nada_a_converter_fica_em_silencio(privado, plan, capsys):
    f = next(f for f in jogo.sincronizar(plan).values() if f['skill_plano'] == DDD and f['origem'] != 'chat')
    jogo.iniciar(f['id'])
    jogo.avaliar(f['id'], 4, 'explicou a decisão', plan)
    jogo.confirmar(f['id'], plan)
    observer.ao_iniciar_sessao(*_inicio(privado))
    assert _contexto(capsys) == ''


def test_fora_de_foco_nao_diz_nada(privado, plan, capsys):
    observer.ao_iniciar_sessao(*_inicio(privado, 'sob_demanda'))
    assert _contexto(capsys) == ''


def test_porteiro_barra_o_que_o_observador_ignora(privado):
    cfg = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))
    repo = cfg['autorizados'][0]
    evento = lambda **k: json.dumps({'cwd': repo, **k}).encode()  # noqa: E731
    assert porteiro.barrar_hook(evento(hook_event_name='SessionStart', cwd='C:/outro')) is True
    assert porteiro.barrar_hook(b'nao e json') is True
    assert porteiro.barrar_hook(evento(hook_event_name='SessionStart')) is False
    assert porteiro.barrar_hook(evento(hook_event_name='PostToolUse', tool_name='Bash', tool_input={'command': 'ls'})) is True
    assert porteiro.barrar_hook(evento(hook_event_name='PostToolUse', tool_name='Bash',
                                       tool_input={'command': 'git commit -m x'})) is False
    assert porteiro.barrar_hook(evento(hook_event_name='PostToolUse', tool_name='Write', tool_input={'content': 'x'})) is False
    cfg['modo'] = 'sob_demanda'
    (privado / 'observer.json').write_text(json.dumps(cfg), encoding='utf-8')
    assert porteiro.barrar_hook(evento(hook_event_name='PostToolUse', tool_name='Write')) is True
    assert porteiro.barrar_hook(evento(hook_event_name='UserPromptSubmit', prompt='oi')) is False  # a fila do painel ainda vale


def test_porteiro_da_statusline(privado):
    cfg = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))
    assert porteiro.barrar_statusline(json.dumps({'cwd': 'C:/outro'}).encode()) == ''
    assert porteiro.barrar_statusline(json.dumps({'cwd': cfg['autorizados'][0]}).encode()) is None
    cfg['modo'] = 'sob_demanda'
    (privado / 'observer.json').write_text(json.dumps(cfg), encoding='utf-8')
    assert 'fora de foco' in porteiro.barrar_statusline(b'{}')
