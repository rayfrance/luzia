"""Foco da Luzia: hooks (observer), linha de status e o comando `foco` para agentes sem hooks."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from luzia import banco, observer, pipeline

CODE = Path(__file__).resolve().parents[2]
DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'


def _consulta(sql, *args):
    con = banco.conectar()
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def _script(privado, nome, entrada, extra_env=None):
    """Roda o arquivo como o harness roda; stdin e stdout em bytes UTF-8 (o pipe real não passa pela página de código)."""
    r = subprocess.run([sys.executable, str(CODE / 'luzia' / nome)], input=entrada.encode('utf-8'), capture_output=True,
                       env={**os.environ, 'LUZIA_PRIVATE': str(privado), **(extra_env or {})}, cwd=CODE.parent)
    return subprocess.CompletedProcess(r.args, r.returncode, r.stdout.decode('utf-8'), r.stderr.decode('utf-8', 'replace'))


# ------------------------------------------------------------------ B1
def test_statusline_roda_como_script(privado):
    """O Claude Code executa `python statusline.py`: sem pacote, só com o caminho do arquivo."""
    repo = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))['autorizados'][0]
    r = _script(privado, 'statusline.py', json.dumps({'workspace': {'current_dir': repo}}))
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith('✦ Luzia · em foco'), r.stdout + r.stderr


def test_statusline_fora_do_repositorio_autorizado_nao_imprime(privado, tmp_path):
    r = _script(privado, 'statusline.py', json.dumps({'workspace': {'current_dir': str(tmp_path / 'outro')}}))
    assert r.returncode == 0, r.stderr
    assert r.stdout == ''


def test_statusline_como_modulo(privado):
    from luzia import statusline
    repo = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))['autorizados'][0]
    assert statusline.linha({'workspace': {'current_dir': repo}}).startswith('✦ Luzia')


def test_observer_script_le_prompt_com_acentos_em_utf8(privado):
    """O pipe do Windows não pode estragar acentos do prompt: 'subdomínio' é palavra do prisma DDD."""
    repo = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))['autorizados'][0]
    evento = {'hook_event_name': 'UserPromptSubmit', 'session_id': 's-acento', 'cwd': repo,
              'prompt': 'separe o Subdomínio de cobrança'}  # conceito escrito como nome (prompt pede termo de conceito, 24/11)
    r = _script(privado, 'observer.py', json.dumps(evento, ensure_ascii=False))
    assert r.returncode == 0, r.stderr
    assert 'luz própria' in json.loads(r.stdout)['hookSpecificOutput']['additionalContext']


# ------------------------------------------------------------------ B2 · o cartão mostra a centelha de verdade
def _evento(privado, conteudo='class Pedido : Aggregate { }', sessao='s-b2'):
    cfg = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))
    return {'session_id': sessao, 'tool_name': 'Write', 'cwd': cfg['autorizados'][0],
            'tool_input': {'file_path': 'Pedido.cs', 'content': conteudo}}, cfg


def test_cartao_mostra_a_centelha_e_o_lm_para_converter(privado, capsys):
    evento, cfg = _evento(privado)
    observer.ao_usar_ferramenta(evento, cfg)
    saida = json.loads(capsys.readouterr().out)['hookSpecificOutput']['additionalContext']
    cid, lm = _consulta("SELECT id, valor_lm FROM avanco WHERE origem = 'chat'")[0]
    assert f'#{cid}' in saida and f'{lm} lm para converter' in saida and 'Converter agora' in saida
    assert 'Pedido.cs' not in saida.split('[Luzia')[0]


def test_conceito_ja_refletido_nao_repete_o_cartao(privado, capsys):
    evento, cfg = _evento(privado)
    observer.ao_usar_ferramenta(evento, cfg)
    capsys.readouterr()
    observer.ao_usar_ferramenta({**evento, 'session_id': 'outra'}, cfg)  # já é refletida: nada novo para converter
    assert capsys.readouterr().out == ''
    assert len(_consulta("SELECT 1 FROM avanco WHERE origem = 'chat'")) == 1


def test_card_de_reconhecimento_pendurado_nao_promete_conversao(privado, monkeypatch, capsys):
    """Com o banco ocupado o resultado é provisório: o card não convida a converter."""
    monkeypatch.setattr(banco, 'gravar_ou_pendurar', lambda *a, **k: False)
    evento, cfg = _evento(privado)
    observer.ao_usar_ferramenta(evento, cfg)
    saida = json.loads(capsys.readouterr().out)['hookSpecificOutput']['additionalContext']
    assert 'a confirmar' in saida
    assert 'AskUserQuestion' not in saida and 'Converter agora' not in saida


def test_um_cartao_por_mudanca_com_a_centelha_que_mais_vale(privado, capsys):
    evento, cfg = _evento(privado, conteudo='Aggregate e xunit Assert')
    observer.ao_usar_ferramenta(evento, cfg)
    saida = json.loads(capsys.readouterr().out)['hookSpecificOutput']['additionalContext']
    chat = _consulta("SELECT prisma, valor_lm FROM avanco WHERE origem = 'chat' ORDER BY valor_lm DESC")
    assert {r['prisma'] for r in chat} == {DDD, TESTES}  # as duas acenderam
    assert saida.count('✦ Centelha da sessão') == 1 and f'{chat[0]["valor_lm"]} lm para converter' in saida


# ------------------------------------------------------------------ B3 · palavras do banco
def test_prisma_incluido_por_pedido_ganha_lumens_pelas_palavras_do_banco(privado, capsys):
    con = banco.conectar()
    try:
        with banco.transacao(con):
            con.execute("INSERT INTO prisma (nome, palavras_json, nivel, meta, estado, origem) "
                        "VALUES ('Observabilidade', '[\"OpenTelemetry\", \"tracing\"]', 0, 3, 'ativo', 'pedido')")
    finally:
        con.close()
    evento, cfg = _evento(privado, conteudo='using OpenTelemetry; // sem nenhuma palavra dos outros prismas')
    observer.ao_usar_ferramenta(evento, cfg)
    saida = json.loads(capsys.readouterr().out)['hookSpecificOutput']['additionalContext']
    assert '(Observabilidade)' in saida
    assert [(r['prisma'], r['luz']) for r in _consulta('SELECT prisma, luz FROM lumen')] == [('Observabilidade', 'refletida')]
    assert [r['titulo'] for r in _consulta("SELECT titulo FROM avanco WHERE origem = 'chat'")] == ['Por que o agente usou OpenTelemetry']


def test_prisma_arquivado_nao_ganha_lumens(privado, capsys):
    con = banco.conectar()
    try:
        with banco.transacao(con):
            con.execute("INSERT INTO prisma (nome, palavras_json, nivel, meta, estado, origem) "
                        "VALUES ('Observabilidade', '[\"OpenTelemetry\"]', 0, 3, 'arquivado', 'pedido')")
    finally:
        con.close()
    evento, cfg = _evento(privado, conteudo='using OpenTelemetry;')
    observer.ao_usar_ferramenta(evento, cfg)
    assert _consulta('SELECT 1 FROM lumen') == []
