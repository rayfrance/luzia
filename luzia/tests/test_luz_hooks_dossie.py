"""Luz no banco: dossiê, transações da conversão, hook com espera curta e pendentes que nunca se perdem."""

import json
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from luzia import banco, jogo, observer, pipeline, trajetoria

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'
FRONT = 'Front-end (JS / Razor / React)'
CODE = Path(__file__).resolve().parents[2]


@pytest.fixture
def plan(privado):
    return pipeline.load_state()['plano']


def _sql(sql, *args):
    con = banco.conectar()
    try:
        with banco.transacao(con):
            con.execute(sql, args)
    finally:
        con.close()


def _consulta(sql, *args):
    con = banco.conectar()
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def _agora(dias=0, horas=0):
    return (datetime.now() - timedelta(days=dias, hours=horas)).isoformat(timespec='seconds')


def _evento(privado, tool='Write', conteudo='class Pedido : Aggregate { }', sessao='s-teste'):
    cfg = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))
    return {'session_id': sessao, 'tool_name': tool, 'cwd': cfg['autorizados'][0],
            'tool_input': {'file_path': 'Pedido.cs', 'content': conteudo}}, cfg


def _da_meta(plan, prisma):
    return next(f for f in jogo.sincronizar(plan).values() if f['skill_plano'] == prisma and f['origem'] != 'chat')


def _converter(fid, plan, nota=4):
    jogo.iniciar(fid)
    jogo.avaliar(fid, nota, 'explicou a decisão', plan)
    return jogo.confirmar(fid, plan)


# ------------------------------------------------------------------ dossiê
def _secao(texto, titulo):
    m = re.search(rf'## {re.escape(titulo)}\n(.*?)(?=\n## |\n_Gerado|\Z)', texto, re.S)
    assert m, f'seção {titulo!r} ausente'
    return m.group(1)


def test_dossie_lista_so_acoes_proprias(plan):
    texto = jogo.dossie(plan, 'teste').read_text(encoding='utf-8')
    assert '- nenhuma ainda' in _secao(texto, 'Ações com autoria própria (avaliadas pela rubrica 0–4 ou dirigidas pela pessoa)')
    f = _da_meta(plan, DDD)
    _converter(f['id'], plan, nota=3)
    texto = jogo.dossie(plan, 'teste').read_text(encoding='utf-8')
    proprias = _secao(texto, 'Ações com autoria própria (avaliadas pela rubrica 0–4 ou dirigidas pela pessoa)')
    assert f['titulo'] in proprias and 'nota 3/4' in proprias


def test_dossie_mostra_os_niveis_antigos_como_historico(plan):
    _sql("INSERT INTO nivel_registro (prisma, de, para, quando, origem, lm, luz_propria) "
         "VALUES (?, 1, 2, '2026-11-01T10:00:00', 'conquistado', 160, 45)", DDD)
    texto = jogo.dossie(plan, 'teste').read_text(encoding='utf-8')
    assert DDD in _secao(texto, 'Histórico (modelo anterior, por níveis)')


def test_dossie_em_linguagem_formal(plan):
    texto = jogo.dossie(plan, 'teste').read_text(encoding='utf-8').lower()
    for proibida in ('feixe', 'degrau', 'prisma', 'lúmen', 'lampejo', 'centelha'):
        assert proibida not in texto
    assert 'skill' in texto and 'ações' in texto and 'autoria própria' in texto
    assert not re.search(r'\blm\b', texto)


def test_dossie_lista_pedidos_aceitos(plan):
    _sql("INSERT INTO pedido (tipo, prisma, motivo, estado, criado_em, decidido_em) "
         "VALUES ('mudar_meta', ?, 'quero focar em domínio', 'aceito', '2026-11-05T09:00:00', '2026-11-06T09:00:00')", DDD)
    _sql("INSERT INTO pedido (tipo, prisma, motivo, estado, criado_em) "
         "VALUES ('arquivar', ?, 'motivo recusado', 'recusado', '2026-11-05T09:00:00')", TESTES)
    texto = jogo.dossie(plan, 'teste').read_text(encoding='utf-8')
    pedidos = _secao(texto, 'Pedidos de mudança aceitos')
    assert 'quero focar em domínio' in pedidos and '2026-11-06' in pedidos
    assert 'motivo recusado' not in texto


def test_dossie_pedido_sem_modelo_mostra_leitura_indisponivel(plan):
    _sql("INSERT INTO leitura (id, alvo_tipo, alvo_id, texto, base_json, base_hash, modelo, criado_em) "
         "VALUES (1, 'pedido', '1', 'texto sem modelo', '{}', 'h', '', '2026-11-05T09:00:00')")
    _sql("INSERT INTO pedido (tipo, prisma, motivo, leitura_id, estado, criado_em, decidido_em) "
         "VALUES ('arquivar', ?, 'motivo', 1, 'aceito', '2026-11-05T09:00:00', '2026-11-06T09:00:00')", DDD)
    pedidos = _secao(jogo.dossie(plan, 'teste').read_text(encoding='utf-8'), 'Pedidos de mudança aceitos')
    assert 'leitura indisponível' in pedidos and 'texto sem modelo' not in pedidos and 'None' not in pedidos


def test_marco_do_dossie_a_um_terco_da_luz_propria(plan, privado):
    cat = sorted(jogo.sincronizar(plan).values(), key=lambda f: -f['valor_lm'])
    tot = sum(f['valor_lm'] for f in cat)
    r = _converter(cat[0]['id'], plan)  # a maior centelha passa de 1/3 do total
    assert cat[0]['valor_lm'] * 3 >= tot and r['marco']['n'] == 1 and Path(r['marco']['dossie']).exists()
    assert trajetoria.perfil_ler(banco.conectar(), jogo.MARCOS) == [1]


# ------------------------------------------------------------------ conversão numa transação só
def test_confirmar_lumen_e_estado_na_mesma_transacao(plan, monkeypatch):
    f = _da_meta(plan, DDD)
    jogo.iniciar(f['id'])
    jogo.avaliar(f['id'], 4, 'ok', plan)

    def quebrar(*a, **k):
        raise RuntimeError('falhou no meio')
    monkeypatch.setattr(jogo, '_evento', quebrar)
    with pytest.raises(RuntimeError):
        jogo.confirmar(f['id'], plan)
    assert _consulta('SELECT 1 FROM lumen WHERE ref = ?', f['id']) == []
    assert _consulta('SELECT estado FROM avanco WHERE id = ?', f['id'])[0]['estado'] == 'convertendo'


def test_dois_sim_ao_mesmo_tempo_lancam_um_lumen_so(plan):
    f = _da_meta(plan, DDD)
    jogo.iniciar(f['id'])
    jogo.avaliar(f['id'], 4, 'ok', plan)
    barreira, resultados = threading.Barrier(2), []

    def clicar():
        barreira.wait(10)
        resultados.append(jogo.confirmar(f['id'], plan))
    ts = [threading.Thread(target=clicar) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(60)
    assert len(_consulta('SELECT 1 FROM lumen WHERE ref = ?', f['id'])) == 1
    assert sorted('erro' in r for r in resultados) == [False, True]


def test_marco_na_mesma_transacao_da_conversao(plan, monkeypatch):
    cat = sorted(jogo.sincronizar(plan).values(), key=lambda f: -f['valor_lm'])
    jogo.iniciar(cat[0]['id'])
    jogo.avaliar(cat[0]['id'], 4, 'ok', plan)

    def quebrar(*a, **k):
        raise RuntimeError('falhou')
    monkeypatch.setattr(trajetoria, 'perfil_gravar', quebrar)
    with pytest.raises(RuntimeError):
        jogo.confirmar(cat[0]['id'], plan)
    assert _consulta('SELECT estado FROM avanco WHERE id = ?', cat[0]['id'])[0]['estado'] == 'convertendo'


# ------------------------------------------------------------------ hook
def test_observer_grava_no_banco(privado, plan, capsys):
    evento, cfg = _evento(privado)
    observer.ao_usar_ferramenta(evento, cfg)
    assert 'luz refletida' in capsys.readouterr().out.lower()
    lumens = _consulta('SELECT * FROM lumen')
    assert [(r['prisma'], r['luz'], r['fonte']) for r in lumens] == [(DDD, 'refletida', 'agente')]
    ev = _consulta('SELECT * FROM sessao_evento')
    assert len(ev) == 1 and ev[0]['prisma'] == DDD and ev[0]['ferramenta'] == 'Write'
    assert ev[0]['extensao'] == '.cs' and ev[0]['interveio'] == 1
    assert not (privado / 'sessao.jsonl').exists() and not (privado / 'lumens.jsonl').exists()


def test_observer_prompt_grava_luz_propria(privado, plan, capsys):
    evento, cfg = _evento(privado)
    evento['prompt'] = 'modele um Aggregate para o pedido'
    observer.ao_enviar_prompt(evento, cfg)
    assert [(r['luz'], r['fonte']) for r in _consulta('SELECT * FROM lumen')] == [('propria', 'prompt')]
    assert _consulta('SELECT ferramenta FROM sessao_evento')[0]['ferramenta'] == 'prompt'
    saida = json.loads(capsys.readouterr().out)['hookSpecificOutput']['additionalContext']
    assert 'você dirigiu Aggregate' in saida


def test_observer_repetido_na_sessao_nao_repete_o_aviso(privado, plan, capsys):
    evento, cfg = _evento(privado)
    observer.ao_usar_ferramenta(evento, cfg)
    capsys.readouterr()
    observer.ao_usar_ferramenta(evento, cfg)
    assert capsys.readouterr().out == ''
    assert len(_consulta('SELECT 1 FROM lumen')) == 1


def _travar_banco(privado, segurar_s):
    """Outra conexão segura a trava de escrita; devolve o evento que a libera."""
    pronto, soltar = threading.Event(), threading.Event()

    def segurar():
        con = banco.conectar()
        con.execute('BEGIN IMMEDIATE')
        pronto.set()
        soltar.wait(segurar_s)
        con.rollback()
        con.close()
    t = threading.Thread(target=segurar)
    t.start()
    assert pronto.wait(10)
    return soltar, t


def test_hook_com_banco_travado_pendura_sem_esperar_demais(privado, plan, capsys):
    evento, cfg = _evento(privado)
    soltar, t = _travar_banco(privado, 30)
    try:
        inicio = time.monotonic()
        observer.ao_usar_ferramenta({**evento, 'session_id': 'nova'}, cfg)  # nunca levanta
        assert time.monotonic() - inicio < 3 * (banco.ESPERA_CURTA_MS / 1000 + 1.5)
    finally:
        soltar.set()
        t.join()
    assert (privado / 'pendentes.jsonl').exists() or list(privado.glob('pendentes-*'))
    assert 'a confirmar' in capsys.readouterr().out
    _sql('SELECT 1')  # a próxima transação absorve o que ficou pendente
    assert len(_consulta("SELECT 1 FROM avanco WHERE origem = 'chat' AND estado = 'refletida'")) == 1


def test_hook_nunca_levanta_com_banco_quebrado(privado, plan, monkeypatch, capsys):
    evento, cfg = _evento(privado)

    def quebrar(*a, **k):
        raise OSError('disco')
    monkeypatch.setattr(banco, 'conectar', quebrar)
    observer.ao_usar_ferramenta(evento, cfg)
    observer.ao_enviar_prompt({**evento, 'prompt': 'Aggregate'}, cfg)
    observer.ao_iniciar_sessao(evento, cfg)


def test_reconhecimento_com_banco_travado_nao_se_perde(privado, plan, capsys):
    evento, cfg = _evento(privado, sessao='trava')
    soltar, t = _travar_banco(privado, 30)
    try:
        inicio = time.monotonic()
        observer.ao_usar_ferramenta(evento, cfg)
        observer.ao_usar_ferramenta(evento, cfg)  # repetido na mesma sessão, ainda travado
        observer.ao_enviar_prompt({**evento, 'prompt': 'modele um Aggregate'}, cfg)
        assert time.monotonic() - inicio < banco.ESPERA_CURTA_MS / 1000 + 3
    finally:
        soltar.set()
        t.join()
    assert _consulta('SELECT 1 FROM lumen') == []  # ainda pendente
    _sql('SELECT 1')  # a próxima transação absorve, na ordem: refletida pelo agente, depois própria pelo prompt
    lumens = [(r['luz'], r['fonte']) for r in _consulta('SELECT * FROM lumen WHERE prisma = ? ORDER BY id', DDD)]
    assert lumens == [('refletida', 'agente'), ('propria', 'prompt')]
    assert [r['estado'] for r in _consulta("SELECT estado FROM avanco WHERE origem = 'chat'")] == ['propria']


def test_reconhecimento_pendurado_duas_vezes_vale_uma(privado, plan):
    nova = {'titulo': 'Aggregate', 'tipo': 'explicar', 'duracao_min': 5, 'valor_lm': 40,
            'conteudo': {'skill': DDD, 'palavras': ['Aggregate']}}
    dados = {'sessao': 's2', 'chave': 'agente', 'prisma': DDD, 'centelha': 'c0de', 'nova_json': json.dumps(nova),
             'ferramenta': 'Write'}
    linha = json.dumps({'operacao': 'reconhecimento', 'dados': dados, 'quando': _agora()}) + '\n'
    (privado / 'pendentes.jsonl').write_text(linha * 2, encoding='utf-8')
    _sql('SELECT 1')
    assert len(_consulta('SELECT 1 FROM lumen')) == 1
    assert len(_consulta("SELECT 1 FROM avanco WHERE id = 'c0de'")) == 1
    assert len(_consulta('SELECT 1 FROM sessao_evento')) == 1


def test_pendente_do_modelo_de_niveis_e_absorvido_sem_lumen(privado, plan):
    """Linha gravada pelo hook antigo (lm/luz/teto, sem centelha): vira só o fato da sessão, sem quebrar a absorção."""
    dados = {'sessao': 's3', 'chave': 'agente', 'prisma': DDD, 'lm': 10, 'luz': 'refletida', 'fonte': 'passivo-refletida',
             'teto': 40}
    (privado / 'pendentes.jsonl').write_text(
        json.dumps({'operacao': 'reconhecimento', 'dados': dados, 'quando': _agora()}) + '\n', encoding='utf-8')
    _sql('SELECT 1')
    assert _consulta('SELECT 1 FROM lumen') == []
    assert len(_consulta('SELECT 1 FROM sessao_evento WHERE sessao = ?', 's3')) == 1


def test_reconhecimento_poda_sessoes_velhas(privado, plan):
    _sql("INSERT INTO sessao_visto (sessao, chave, prisma, quando) VALUES ('velha', 'agente', ?, ?)", DDD, _agora(dias=8))
    observer.reconhecer_em('Aggregate', 'agente', 'abc', 'ativo', '.cs', 'Write', observer.lacunas(plan))
    assert _consulta("SELECT 1 FROM sessao_visto WHERE sessao = 'velha'") == []
    assert not (privado / 'sessao_vistos.json').exists()


def test_banco_antigo_sem_sessao_visto_ganha_a_tabela(privado, plan):
    _sql('DROP TABLE sessao_visto')
    achados = observer.reconhecer_em('Aggregate', 'agente', 'x', 'ativo', '.cs', 'Write', observer.lacunas(plan))
    assert achados and achados[0]['estado'] == 'refletida'


def test_banco_que_acabou_de_falhar_nao_faz_o_hook_esperar_de_novo(privado, plan):
    soltar, t = _travar_banco(privado, 30)
    try:
        assert banco.gravar_ou_pendurar('lumen', {'prisma': DDD, 'lm': 10, 'luz': 'refletida', 'fonte': 'x'}) is False
        assert banco.ocupado()
        inicio = time.monotonic()
        assert banco.gravar_ou_pendurar('sessao_evento', {'sessao': 's', 'prisma': DDD}) is False
        assert time.monotonic() - inicio < 0.5  # foi direto para os pendentes
    finally:
        soltar.set()
        t.join()
    _sql('SELECT 1')
    assert len(_consulta('SELECT 1 FROM lumen')) == 1 and len(_consulta('SELECT 1 FROM sessao_evento')) == 1


# ------------------------------------------------------------------ desempenho e JSON antigo
def test_luz_usa_uma_conexao_e_poucas_consultas(plan, monkeypatch):
    jogo.catalogo(plan)
    abertas, consultas = [], []
    original = banco.conectar

    def espiar(*a, **k):
        con = original(*a, **k)
        abertas.append(con)
        con.set_trace_callback(consultas.append)
        return con
    monkeypatch.setattr(banco, 'conectar', espiar)
    t = jogo.luz(plan)
    assert len(t['prismas']) == 3
    assert len(abertas) == 1, 'luz deve abrir uma conexão só'
    assert len([c for c in consultas if 'FROM avanco' in c]) <= 3  # luz, próximas e centelhas da meta
    assert len(consultas) <= 15, consultas


def test_sem_json_antigo():
    antigos = ('feixes.json', 'lumens.jsonl', 'degraus.json', 'cartoes.json', 'fila.json')
    for arquivo in (CODE / 'luzia').glob('*.py'):
        if arquivo.name == 'migrar.py':
            continue
        texto = arquivo.read_text(encoding='utf-8')
        for nome in antigos:
            assert nome not in texto, f'{arquivo.name} ainda cita {nome}'
