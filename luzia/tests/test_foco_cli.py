"""Comando `foco`: o mesmo reconhecimento dos hooks para agentes sem hooks (Antigravity, Codex, Cursor)."""

import io
import json
import os
import re
import shlex
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from luzia import banco, cli

CODE = Path(__file__).resolve().parents[2]
DDD = 'Domain-Driven Design (DDD)'


def _consulta(sql, *args):
    con = banco.conectar()
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def rodar(monkeypatch, *argv):
    monkeypatch.setattr(sys, 'argv', ['luzia', *[str(a) for a in argv]])
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main()
    return buf.getvalue()


def botoes_de(saida):
    linha = next((x for x in saida.splitlines() if x.startswith('LUZIA_BOTOES=')), None)
    return json.loads(linha.split('=', 1)[1]) if linha else []


def _git(repo, *args):
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Pessoa Teste', '-c', 'user.email=p@teste.local', *args],
                   check=True, capture_output=True)


@pytest.fixture
def repo(privado):
    pasta = Path(json.loads((privado / 'observer.json').read_text(encoding='utf-8'))['autorizados'][0])
    _git(pasta, 'init', '-q')
    (pasta / 'Pedido.cs').write_text('class Pedido { }\n', encoding='utf-8')
    _git(pasta, 'add', '.')
    _git(pasta, 'commit', '-q', '-m', 'init')
    return pasta


def _modo(privado, modo):
    cfg = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))
    cfg['modo'] = modo
    (privado / 'observer.json').write_text(json.dumps(cfg), encoding='utf-8')


def _editar(repo, conteudo='class Pedido : Aggregate { }\n'):
    (repo / 'Pedido.cs').write_text(conteudo, encoding='utf-8')


def test_foco_arquivos_reconhece_luz_refletida_e_oferece_converter(privado, repo, monkeypatch):
    _editar(repo)
    saida = rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', 's1')
    assert re.search(r'✦ Centelha da sessão · DDD · Aggregate · \d+ lm para converter', saida), saida
    bts = botoes_de(saida)
    assert [b['rotulo'] for b in bts] == ['Converter agora', 'Ver centelhas para converter', 'Ver trajetória']
    assert re.fullmatch(r'fazer \w+ --onde aqui', bts[0]['rodar']) and bts[1]['rodar'] == 'centelhas --estado converter'
    assert [(r['prisma'], r['luz'], r['fonte']) for r in _consulta('SELECT * FROM lumen')] == [(DDD, 'refletida', 'agente')]
    nascida = _consulta("SELECT estado, titulo, origem FROM avanco WHERE origem = 'chat'")
    assert [(r['estado'], r['titulo']) for r in nascida] == [('refletida', 'Por que o agente usou Aggregate')]  # nasce da conversa, sem o código


def test_foco_nunca_guarda_codigo_nem_prompt(privado, repo, monkeypatch, tmp_path):
    _editar(repo, 'class Pedido : ZzAggregateSecreto { }\n')
    prompt = tmp_path / 'prompt.txt'
    prompt.write_text('quero um Aggregate chamado ZzPromptSecreto', encoding='utf-8')
    rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', 's1')
    rodar(monkeypatch, 'foco', '--prompt-arquivo', prompt, '--cwd', repo, '--sessao', 's1')
    assert _consulta('SELECT 1 FROM lumen')  # os dois reconhecimentos aconteceram
    for arquivo in privado.rglob('*'):
        if arquivo.is_file():
            dados = arquivo.read_bytes()
            assert b'ZzAggregateSecreto' not in dados and b'ZzPromptSecreto' not in dados, arquivo.name


def test_foco_prompt_reconhece_luz_propria(privado, repo, monkeypatch, tmp_path):
    prompt = tmp_path / 'prompt.txt'
    prompt.write_text('modele o Aggregate de pedido separando o subdomínio', encoding='utf-8')
    saida = rodar(monkeypatch, 'foco', '--prompt-arquivo', prompt, '--cwd', repo, '--sessao', 's2')
    assert f'DIRIGIU "Aggregate" ({DDD})' in saida and 'virou luz própria' in saida
    assert re.search(r'Luzia · DDD: você dirigiu Aggregate · \+\d+ lm de luz própria', saida), saida
    linhas = _consulta('SELECT * FROM lumen')
    assert [(r['luz'], r['fonte']) for r in linhas] == [('propria', 'prompt')]
    assert [r['estado'] for r in _consulta("SELECT estado FROM avanco WHERE origem = 'chat'")] == ['propria']
    assert 'LUZIA_BOTOES=' in saida


def test_foco_cada_centelha_muda_de_luz_uma_vez_so(privado, repo, monkeypatch):
    _editar(repo)
    rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', 's3')
    repetido = rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', 's3')
    assert 'Centelha da sessão' not in repetido and 'LUZIA_BOTOES=' in repetido
    assert len(_consulta('SELECT 1 FROM lumen')) == 1
    for sessao in ('s4', 's5', 's6'):  # sem teto diário: o que importa é que a luz não se repete
        rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', sessao)
    ultimo = rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', 's7')
    assert len(_consulta('SELECT 1 FROM lumen')) == 1  # a centelha já é refletida: repetir não infla o progresso
    assert 'Centelha da sessão' not in ultimo and 'nenhuma centelha mudou de luz' in ultimo


def test_foco_sem_sessao_usa_um_id_diario_por_pasta(privado, repo, monkeypatch):
    _editar(repo)
    rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo)
    rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo)
    assert len(_consulta('SELECT 1 FROM lumen')) == 1


def test_foco_arquivo_novo_sem_commit_tambem_e_lido_pelo_git_diff(privado, repo, monkeypatch):
    (repo / 'Novo.cs').write_text('class Novo : Aggregate { }\n', encoding='utf-8')
    saida = rodar(monkeypatch, 'foco', '--arquivos', 'Novo.cs', '--cwd', repo, '--sessao', 's8')
    assert 'Centelha da sessão' in saida


def test_foco_em_silencio_registra_sem_mostrar_cartao(privado, repo, monkeypatch):
    _modo(privado, 'passivo')
    _editar(repo)
    saida = rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', 's9')
    assert 'Centelha da sessão' not in saida and 'em silêncio' in saida and 'Aggregate' in saida
    assert len(_consulta('SELECT 1 FROM lumen')) == 1


def test_foco_fora_de_foco_e_repositorio_nao_autorizado_nao_observam(privado, repo, monkeypatch, tmp_path):
    _editar(repo)
    outro = tmp_path / 'outro'
    outro.mkdir()
    saida = rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', outro, '--sessao', 'sa')
    assert 'não está autorizada' in saida and 'LUZIA_BOTOES=' in saida
    _modo(privado, 'sob_demanda')
    saida = rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', 'sb')
    assert 'fora de foco' in saida and 'LUZIA_BOTOES=' in saida
    assert _consulta('SELECT 1 FROM lumen') == []


def test_foco_sem_argumentos_explica_o_uso(privado, repo, monkeypatch):
    saida = rodar(monkeypatch, 'foco', '--cwd', repo)
    assert '--prompt-arquivo' in saida and '--arquivos' in saida and 'LUZIA_BOTOES=' in saida


def test_foco_fora_de_repositorio_git_avisa_sem_gravar(privado, repo, monkeypatch, tmp_path):
    cfg = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))
    pasta = tmp_path / 'semgit'
    pasta.mkdir()
    cfg['autorizados'].append(str(pasta))
    (privado / 'observer.json').write_text(json.dumps(cfg), encoding='utf-8')
    (pasta / 'a.cs').write_text('Aggregate', encoding='utf-8')
    saida = rodar(monkeypatch, 'foco', '--arquivos', 'a.cs', '--cwd', pasta, '--sessao', 'sc')
    assert 'git' in saida.lower() and 'LUZIA_BOTOES=' in saida
    assert _consulta('SELECT 1 FROM lumen') == []


def test_botao_do_foco_leva_a_conversao_ate_a_luz_propria(privado, repo, monkeypatch):
    _editar(repo)
    bts = botoes_de(rodar(monkeypatch, 'foco', '--arquivos', 'Pedido.cs', '--cwd', repo, '--sessao', 'sd'))
    converter = rodar(monkeypatch, *shlex.split(bts[0]['rodar']))  # "Converter agora": fazer <id> --onde aqui
    assert 'Convertendo' in converter and 'ROTEIRO PARA O AGENTE' in converter
    cid = bts[0]['rodar'].split()[1]
    avaliada = rodar(monkeypatch, 'registrar', cid, '--nota', '4', '--resumo', 'separei o agregado')
    assert 'a Luzia confirmou seu entendimento' in avaliada and botoes_de(avaliada)[0]['rodar'] == f'confirmar {cid}'
    confirmada = rodar(monkeypatch, 'confirmar', cid)
    assert re.match(r'✦ \*\*\+\d+ lm de luz própria\*\* · DDD 0% → \d+%', confirmada), confirmada
    rodadas = [(r['luz'], r['fonte']) for r in _consulta('SELECT * FROM lumen ORDER BY id')]
    assert rodadas == [('refletida', 'agente'), ('propria', 'conversao')]  # a luz refletida virou própria, sem duplicar
    assert _consulta('SELECT estado FROM avanco WHERE id = ?', cid)[0]['estado'] == 'propria'


def test_foco_roda_como_a_cli_real(privado, repo):
    """A CLI é chamada de outra pasta (`cd code && python -m luzia.cli`): o projeto vem de --cwd."""
    _editar(repo)
    r = subprocess.run([sys.executable, '-m', 'luzia.cli', 'foco', '--arquivos', 'Pedido.cs', '--cwd', str(repo), '--sessao', 'sf'],
                       cwd=CODE, capture_output=True, env={**os.environ, 'LUZIA_PRIVATE': str(privado)})
    saida = r.stdout.decode('utf-8')
    assert r.returncode == 0, r.stderr.decode('utf-8', 'replace')
    assert 'Centelha da sessão' in saida and 'LUZIA_BOTOES=' in saida
