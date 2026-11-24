"""Centelhas e conversão (docs/specs/2026-11-18-centelhas-conversao.md).

O progresso de um prisma é o lm das centelhas próprias dividido pelo lm de todas as centelhas da meta;
o loop central converte luz refletida em própria, com a avaliação da Luzia e o sim da pessoa.
"""

import json
import shutil

import pytest

from luzia import banco, jogo, observer, pipeline

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'
FRONT = 'Front-end (JS / Razor / React)'


@pytest.fixture
def plan(privado):
    return pipeline.load_state()['plano']


def _consulta(sql, *args):
    con = banco.conectar()
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def _sql(sql, *args):
    con = banco.conectar()
    try:
        with banco.transacao(con):
            con.execute(sql, args)
    finally:
        con.close()


def _da_meta(plan, prisma):
    """A centelha da meta (vinda do plano) de um prisma."""
    return next(f for f in jogo.sincronizar(plan).values() if f['skill_plano'] == prisma and f['origem'] != 'chat')


def _prisma(plan, nome):
    return next(p for p in jogo.luz(plan)['prismas'] if p['nome'] == nome)


def _palavras(fid, *palavras):
    con = banco.conectar()
    try:
        conteudo = json.loads(con.execute('SELECT conteudo_json FROM avanco WHERE id = ?', (fid,)).fetchone()[0])
        conteudo['palavras'] = list(palavras)
        with banco.transacao(con):
            con.execute('UPDATE avanco SET conteudo_json = ? WHERE id = ?', (json.dumps(conteudo), fid))
    finally:
        con.close()


def _converter(fid, plan, nota=4):
    jogo.iniciar(fid)
    jogo.avaliar(fid, nota, 'explicou a decisão', plan)
    return jogo.confirmar(fid, plan)


# ------------------------------------------------------------------ progresso
def test_no_comeco_tudo_esta_por_acender(plan):
    cat = jogo.sincronizar(plan)
    assert cat and {f['estado'] for f in cat.values()} == {'apagada'}
    t = jogo.luz(plan)
    assert t['pct'] == 0 and t['propria'] == 0
    assert t['tot'] == sum(f['valor_lm'] for f in cat.values())
    assert {p['nome'] for p in t['prismas']} >= {DDD, TESTES, FRONT}
    assert t['por_estado']['apagada'] == t['tot']


def test_progresso_e_lm_proprio_sobre_o_total_da_meta(plan):
    f = _da_meta(plan, DDD)
    _converter(f['id'], plan)
    p = _prisma(plan, DDD)
    assert p['propria'] == f['valor_lm'] and p['tot'] == f['valor_lm']
    assert p['pct'] == 100 and p['na_meta'] and p['n_propria'] == 1
    t = jogo.luz(plan)
    assert t['propria'] == f['valor_lm'] and t['pct'] == round(100 * f['valor_lm'] / t['tot'])


# ------------------------------------------------------------------ valor
def test_valor_segue_a_regra_visivel(plan):
    for f in jogo.sincronizar(plan).values():
        nomes = [c[0] for c in f['conta']]
        assert nomes == ['Profundidade do conceito', 'Lacuna no prisma', 'Peso para a meta']
        assert 10 <= f['valor_lm'] <= 100
        assert f['valor_lm'] == max(10, min(100, sum(c[2] for c in f['conta'])))
    f = _da_meta(plan, DDD)  # praticar, 15 min, prisma sem luz própria
    assert f['conta'][0][2] == 20 + 15 and f['conta'][1][2] == round(35 * 0.6)


def test_valor_fica_fixo_depois_de_criado(plan):
    antes = {fid: f['valor_lm'] for fid, f in jogo.sincronizar(plan).items()}
    _converter(_da_meta(plan, DDD)['id'], plan)  # a lacuna de DDD mudou...
    depois = {fid: f['valor_lm'] for fid, f in jogo.sincronizar(plan).items()}
    assert depois == antes  # ...mas o lm de cada centelha não muda sozinho


# ------------------------------------------------------------------ conversão
def test_converter_passa_por_convertendo_e_espera_o_sim(plan):
    f = _da_meta(plan, TESTES)
    assert jogo.iniciar(f['id'])['estado'] == 'convertendo'
    r = jogo.avaliar(f['id'], 2, 'descreveu o que o teste faz', plan)
    assert r['confirmada'] is False and r['feixe']['estado'] == 'convertendo' and r['feixe']['tentativas'] == 1
    r = jogo.avaliar(f['id'], 3, 'comparou com uma alternativa', plan)
    assert r['confirmada'] is True and r['feixe']['estado'] == 'convertendo' and r['feixe']['confirmada_em']
    assert _prisma(plan, TESTES)['propria'] == 0  # sem o sim, a luz ainda não é dela
    r = jogo.confirmar(f['id'], plan)
    assert r['ganho'] == f['valor_lm'] and r['feixe']['estado'] == 'propria' and r['feixe']['nota'] == 3
    lumens = _consulta("SELECT lm, luz, fonte, ref FROM lumen WHERE ref = ?", f['id'])
    assert [tuple(x) for x in lumens] == [(f['valor_lm'], 'propria', 'acesa', f['id'])]


def test_confirmar_pede_avaliacao_antes(plan):
    f = _da_meta(plan, TESTES)
    jogo.iniciar(f['id'])
    assert 'erro' in jogo.confirmar(f['id'], plan)
    jogo.avaliar(f['id'], 1, 'não explicou', plan)
    assert 'erro' in jogo.confirmar(f['id'], plan)


def test_avaliar_pede_centelha_iniciada(plan):
    f = _da_meta(plan, TESTES)
    assert 'erro' in jogo.avaliar(f['id'], 4, 'x', plan)


def test_confirmar_duas_vezes_lanca_um_lumen_so(plan):
    f = _da_meta(plan, FRONT)
    _converter(f['id'], plan)
    assert 'erro' in jogo.confirmar(f['id'], plan)
    assert len(_consulta('SELECT 1 FROM lumen WHERE ref = ?', f['id'])) == 1


def test_converter_luz_refletida_grava_fonte_conversao(plan):
    f = _da_meta(plan, DDD)
    _sql("UPDATE avanco SET estado = 'refletida' WHERE id = ?", f['id'])
    _converter(f['id'], plan)
    assert _consulta('SELECT fonte FROM lumen WHERE ref = ?', f['id'])[0][0] == 'conversao'


def test_descartada_sai_do_total_e_restaurar_volta_ao_estado(plan):
    f = _da_meta(plan, DDD)
    _sql("UPDATE avanco SET estado = 'refletida' WHERE id = ?", f['id'])
    tot = jogo.luz(plan)['tot']
    assert jogo.descartar(f['id'], 'agora_nao')['estado'] == 'descartada'
    assert jogo.luz(plan)['tot'] == tot - f['valor_lm']
    assert jogo.restaurar(f['id'])['estado'] == 'refletida'


def test_luz_propria_nao_se_descarta(plan):
    f = _da_meta(plan, DDD)
    _converter(f['id'], plan)
    assert jogo.descartar(f['id'], 'ja_domino') is None
    assert jogo.sincronizar(plan)[f['id']]['estado'] == 'propria'


# ------------------------------------------------------------------ hooks (reconhecimento por centelha)
def _gaps(plan):
    return observer.lacunas(plan)


def test_agente_aplicou_o_conceito_acende_a_centelha_como_refletida(plan):
    f = _da_meta(plan, DDD)
    _palavras(f['id'], 'Aggregate')
    achados = observer.reconhecer_em('class Pedido : Aggregate { }', 'agente', 's1', 'ativo', '.cs', 'Write', _gaps(plan))
    assert [(a['centelha'], a['estado'], a['novo']) for a in achados] == [(f['id'], 'refletida', False)]
    g = jogo.sincronizar(plan)[f['id']]
    assert g['estado'] == 'refletida' and g['onde']
    assert _prisma(plan, DDD)['refletida'] == f['valor_lm']


def test_agente_sem_centelha_que_case_cria_uma_refletida_do_chat(plan):
    achados = observer.reconhecer_em('class Pedido : Aggregate { }', 'agente', 's1', 'ativo', '.cs', 'Write', _gaps(plan))
    assert len(achados) == 1 and achados[0]['novo'] and achados[0]['estado'] == 'refletida'
    nova = jogo.sincronizar(plan)[achados[0]['centelha']]
    assert nova['origem'] == 'chat' and nova['skill_plano'] == DDD and 10 <= nova['valor_lm'] <= 100
    assert '.cs' in nova['onde'] and 'Pedido' not in json.dumps(nova)  # nunca o caminho nem o código
    de_novo = observer.reconhecer_em('Aggregate de novo', 'agente', 's2', 'ativo', '.cs', 'Write', _gaps(plan))
    assert [a['centelha'] for a in de_novo] == [nova['id']] and not de_novo[0]['novo']
    assert len([g for g in jogo.sincronizar(plan).values() if g['origem'] == 'chat']) == 1


def test_prompt_que_cita_o_conceito_faz_a_centelha_do_chat_nascer_propria(plan):
    achados = observer.reconhecer_em('modele o Aggregate de pedido', 'prompt', 's1', 'ativo', 'prompt', 'prompt', _gaps(plan))
    assert [(a['estado'], a['luz'], a['novo']) for a in achados] == [('propria', 'propria', True)]
    cid = achados[0]['centelha']
    assert tuple(_consulta("SELECT lm, fonte FROM lumen WHERE ref = ? AND luz = 'propria'", cid)[0])[1] == 'prompt'


def test_prompt_acende_a_luz_refletida_do_chat(plan):
    observer.reconhecer_em('class Pedido : Aggregate', 'agente', 's1', 'ativo', '.cs', 'Write', _gaps(plan))
    achados = observer.reconhecer_em('modele o Aggregate de pedido', 'prompt', 's1', 'ativo', 'prompt', 'prompt', _gaps(plan))
    assert [(a['estado'], a['novo']) for a in achados] == [('propria', False)]


def test_prompt_nao_fecha_centelha_da_meta_nem_conversao_sem_a_rubrica(plan):
    """Colar o prompt da centelha ou explicar durante a conversa cita o conceito: quem decide é a rubrica e o sim."""
    f = _da_meta(plan, DDD)
    _palavras(f['id'], 'Aggregate')
    assert observer.reconhecer_em('Aggregate', 'prompt', 's1', 'ativo', 'prompt', 'prompt', _gaps(plan)) == []
    jogo.iniciar(f['id'])
    observer.reconhecer_em('o Aggregate protege as invariantes', 'prompt', 's2', 'ativo', 'prompt', 'prompt', _gaps(plan))
    assert jogo.sincronizar(plan)[f['id']]['estado'] == 'convertendo'
    assert _consulta("SELECT 1 FROM lumen WHERE ref = ? AND luz = 'propria'", f['id']) == []


def test_o_nome_do_prisma_sozinho_nao_acende_nada(plan):
    """As ações do plano usam o nome do prisma como conceito: 'o que é DDD?' não pode acender o prisma inteiro."""
    for f in jogo.sincronizar(plan).values():
        _palavras(f['id'], f['skill_plano'], 'DDD')
    antes = jogo.luz(plan)
    observer.reconhecer_em('o que é Domain-Driven Design (DDD)?', 'prompt', 's1', 'ativo', 'prompt', 'prompt', _gaps(plan))
    observer.reconhecer_em('Domain-Driven Design (DDD)', 'agente', 's1', 'ativo', '.cs', 'Write', _gaps(plan))
    assert jogo.luz(plan)['por_estado'] == antes['por_estado']


def test_agente_acende_uma_centelha_por_prisma_por_mudanca(plan):
    cat = list(jogo.sincronizar(plan).values())
    ddd = [f for f in cat if f['skill_plano'] == DDD]
    for f in ddd:
        _palavras(f['id'], 'Aggregate')
    extra = {'id': 'extra1', 'titulo': 'Outra de DDD', 'tipo': 'estudar', 'skill_plano': DDD, 'duracao_min': 30,
             'palavras': ['Aggregate'], 'valor_lm': 90, 'conta': []}
    con = banco.conectar()
    try:
        with banco.transacao(con):
            jogo._inserir_avanco(con, extra)
    finally:
        con.close()
    achados = observer.reconhecer_em('Aggregate', 'agente', 's1', 'ativo', '.cs', 'Write', _gaps(plan))
    assert [a['centelha'] for a in achados] == ['extra1']  # a que mais vale
    assert len(_consulta("SELECT 1 FROM avanco WHERE prisma = ? AND estado = 'refletida'", DDD)) == 1


def test_palavra_inteira_e_sem_termos_genericos_nem_nome_de_arquivo(plan):
    assert not observer._casa('class TestHelper', 'Test') and observer._casa('um Test aqui', 'Test')
    assert observer._casa('vamos desacoplar', 'desacopl')
    achados = observer.reconhecer_em('[Fact] public void Test() { Assert.True(x); }', 'agente', 's1', 'ativo', '.cs', 'Write',
                                     _gaps(plan))
    assert achados == []  # só termos genéricos: nenhuma centelha nasce


def test_nota_baixa_depois_de_confirmada_apaga_a_confirmacao(plan):
    f = _da_meta(plan, TESTES)
    jogo.iniciar(f['id'])
    jogo.avaliar(f['id'], 4, 'explicou', plan)
    r = jogo.avaliar(f['id'], 0, 'não explicou desta vez', plan)
    assert r['feixe']['confirmada_em'] is None and r['feixe']['nota'] == 0
    assert 'erro' in jogo.confirmar(f['id'], plan)


def test_prisma_so_com_centelhas_do_chat_nao_esta_na_meta(plan):
    for f in jogo.sincronizar(plan).values():
        if f['skill_plano'] == DDD:
            jogo.descartar(f['id'], 'agora_nao')
    observer.reconhecer_em('modele o Aggregate', 'prompt', 's1', 'ativo', 'prompt', 'prompt', _gaps(plan))
    p = _prisma(plan, DDD)
    # o alvo continua o da meta (descartar não o encolhe): a centelha do chat conta, mas não completa o prisma
    assert 0 < p['propria'] < p['alvo_lm'] and p['pct'] == round(100 * p['propria'] / p['alvo_lm']) and not p['na_meta']


def test_marcos_da_luz_nao_herdam_os_do_modelo_de_niveis(plan):
    from luzia import trajetoria
    con = banco.conectar()
    try:
        with banco.transacao(con):
            trajetoria.perfil_gravar(con, 'marcos_dossie', [1, 2])  # gravados pelo modelo de níveis
    finally:
        con.close()
    cat = sorted(jogo.sincronizar(plan).values(), key=lambda f: -f['valor_lm'])
    assert _converter(cat[0]['id'], plan)['marco']['n'] == 1


def test_repetir_o_conceito_nao_infla_o_progresso(plan):
    for s in ('s1', 's2', 's3'):
        observer.reconhecer_em('Aggregate', 'prompt', s, 'ativo', 'prompt', 'prompt', _gaps(plan))
        observer.reconhecer_em('Aggregate', 'prompt', s, 'ativo', 'prompt', 'prompt', _gaps(plan))
    chat = [g for g in jogo.sincronizar(plan).values() if g['origem'] == 'chat']
    assert len(chat) == 1 and chat[0]['estado'] == 'propria'
    assert len(_consulta("SELECT 1 FROM lumen WHERE ref = ? AND luz = 'propria'", chat[0]['id'])) == 1


def test_sem_teto_diario(plan):
    """Muitos conceitos no mesmo dia e no mesmo prisma: todos contam (cada um uma vez)."""
    for i, termo in enumerate(('Aggregate', 'ValueObject')):
        observer.reconhecer_em(termo, 'prompt', f's{i}', 'ativo', 'prompt', 'prompt', _gaps(plan))
    chat = [g for g in jogo.sincronizar(plan).values() if g['origem'] == 'chat']
    assert len(chat) == 2
    assert _prisma(plan, DDD)['propria'] == sum(g['valor_lm'] for g in chat)


# ------------------------------------------------------------------ esquema 4
def test_banco_do_esquema_3_sobe_mapeando_os_estados_com_backup(privado, plan):
    cat = jogo.sincronizar(plan)
    ids = list(cat)
    con = banco.conectar()
    with banco.transacao(con):
        con.execute("UPDATE avanco SET estado = 'conquistado', nota = 3 WHERE id = ?", (ids[0],))
        con.execute("UPDATE avanco SET estado = 'conquistado', nota = 2 WHERE id = ?", (ids[1],))
        con.execute("UPDATE avanco SET estado = 'na_fila' WHERE id = ?", (ids[2],))
        con.execute("UPDATE meta SET valor = '3' WHERE chave = 'esquema'")
    con.execute('ALTER TABLE avanco DROP COLUMN onde')
    con.execute('ALTER TABLE avanco DROP COLUMN confirmada_em')
    con.execute('ALTER TABLE prisma DROP COLUMN meta_estado')
    con.close()
    shutil.rmtree(privado / 'dossies', ignore_errors=True)

    con = banco.conectar()  # código novo abre o banco do esquema 3
    try:
        assert con.execute("SELECT valor FROM meta WHERE chave = 'esquema'").fetchone()[0] == str(banco.ESQUEMA_VERSAO)
        estado = dict(con.execute('SELECT id, estado FROM avanco').fetchall())
        assert (estado[ids[0]], estado[ids[1]], estado[ids[2]]) == ('propria', 'convertendo', 'convertendo')
        assert {r[0] for r in con.execute("SELECT meta_estado FROM prisma WHERE estado = 'ativo'")} == {'a_propor'}
    finally:
        con.close()
    backups = list(privado.glob('backup-antes-centelhas-*/luzia.db'))
    assert len(backups) == 1
    velho = banco.sqlite3.connect(backups[0])
    try:
        assert velho.execute("SELECT valor FROM meta WHERE chave = 'esquema'").fetchone()[0] == '3'
    finally:
        velho.close()
    banco.conectar().close()  # abrir de novo não refaz nada
    assert len(list(privado.glob('backup-antes-centelhas-*'))) == 1


# --- teste com testadores (24/11): ruído, nomes de prisma, grafias naturais e repositório autorizado ---

def test_palavra_solta_do_nome_do_prisma_nao_acende(plan):
    gaps = _gaps(plan)
    gaps[TESTES]['palavras'] = ['qualidade']
    gaps[TESTES]['centelhas'] = []
    assert observer.reconhecer_em('Testes e Qualidade', 'prompt', 's1', 'ativo', 'prompt', 'prompt', gaps) == []


def test_sintaxe_da_linguagem_nao_cria_centelha_do_chat(plan):
    gaps = _gaps(plan)
    for info in gaps.values():
        info['palavras'] = ['def', 'class', 'import', 'commit']
        info['centelhas'] = []
    texto = 'import os\nclass Periodo:\n    def contem(self): pass\n# git commit -m "feat: x"'
    assert observer.reconhecer_em(texto, 'agente', 's1', 'ativo', '.py', 'Write', gaps) == []


def test_grafia_natural_casa_com_camel_case_e_vice_versa(plan):
    f = _da_meta(plan, DDD)
    _palavras(f['id'], 'ValueObject')
    achados = observer.reconhecer_em('# periodo: value object imutável', 'agente', 's1', 'ativo', '.py', 'Edit', _gaps(plan))
    assert [a['centelha'] for a in achados] == [f['id']]
    assert observer._casa('class PeriodoValueObject', 'value object') is False  # dentro de outra palavra, não
    assert observer._casa('um Value-Object aqui', 'ValueObject') and observer._casa('ValueObject', 'value object')


def test_so_o_repositorio_autorizado_e_as_subpastas_dele():
    cfg = {'autorizados': [r'C:\r\repo']}
    assert observer.authorized('C:/r/repo', cfg) and observer.authorized(r'c:\R\Repo\src', cfg)
    assert not observer.authorized('C:/r/repo-outro', cfg) and not observer.authorized('C:/r', cfg)
    assert not observer.authorized(5, cfg) and not observer.authorized(None, cfg)


@pytest.mark.parametrize('bruto', [b'[1, 2]', b'null', b'"texto"', b'{"cwd": 5, "hook_event_name": "Stop"}'])
def test_evento_de_tipo_inesperado_nao_derruba_o_hook(privado, monkeypatch, bruto):
    import io, sys
    monkeypatch.setattr(sys, 'stdin', io.TextIOWrapper(io.BytesIO(bruto)))
    observer.main()  # não levanta
