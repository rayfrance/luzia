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


def test_so_apagadas_pede_a_linha_para_acender(privado, plan, capsys):
    observer.ao_iniciar_sessao(*_inicio(privado, 'ativo'))
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
    assert 'fora de foco' in porteiro.barrar_statusline(json.dumps({'cwd': cfg['autorizados'][0]}).encode())
    assert porteiro.barrar_statusline(b'{}') == ''  # sem cwd: fechada


def test_statusline_fora_de_foco_tambem_some_fora_do_repositorio_autorizado(privado):
    """Rodada 1 do loop (24/11): em "fora de foco" a linha aparecia em qualquer pasta."""
    import json as _json
    from luzia import porteiro, statusline
    cfg = _json.loads((privado / 'observer.json').read_text(encoding='utf-8'))
    cfg['modo'] = 'sob_demanda'
    (privado / 'observer.json').write_text(_json.dumps(cfg), encoding='utf-8')
    fora = _json.dumps({'cwd': 'C:/outra/pasta'}).encode()
    assert porteiro.barrar_statusline(fora) == '' and statusline.linha({'cwd': 'C:/outra/pasta'}) == ''
    dentro = {'cwd': cfg['autorizados'][0]}
    assert 'fora de foco' in statusline.linha(dentro)


def test_em_silencio_o_inicio_de_sessao_fica_calado(privado, plan, capsys):
    """Rodada 11: "em silêncio" (passivo) só muda a luz no banco, sem o aviso de início."""
    observer.ao_iniciar_sessao(*_inicio(privado, 'passivo'))
    assert _contexto(capsys) == ''
