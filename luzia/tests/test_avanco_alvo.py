"""Avanço da trajetória com alvo fixo e composição da luz (decisão de 24/11/2026, depois do teste com testadores).

Duas medidas separadas:
- avanço (`pct`): luz própria do prisma, até o alvo dele, sobre o alvo. O alvo é fixado quando a meta é definida
  e não muda ao acender centelhas novas nem ao capturar luz refletida, então o avanço só sobe;
- composição (`luz_pct`): própria sobre a luz já coletada (própria + refletida + convertendo); as apagadas são
  oportunidades e ficam de fora.
"""

import pytest

from luzia import acoes, banco, jogo, pipeline

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'


@pytest.fixture
def plan(privado):
    p = pipeline.load_state()['plano']
    jogo.sincronizar(p)  # a primeira sincronização fixa os alvos da meta
    return p


def _prisma(plan, nome):
    return jogo.luz(plan)['por_prisma'][nome]


def _da_meta(plan, prisma):
    return next(f for f in jogo.sincronizar(plan).values() if f['skill_plano'] == prisma and f['origem'] != 'chat')


def _converter(fid, plan, nota=4):
    jogo.iniciar(fid)
    jogo.avaliar(fid, nota, 'explicou a decisão', plan)
    return jogo.confirmar(fid, plan)


def _acender(plan, skill, n=3, minutos=30):
    """O que `acender` grava: um trecho novo no plano (centelhas apagadas do prisma)."""
    novas = [{'titulo': f'Centelha extra {i} de {skill}', 'tipo': 'praticar', 'skill': skill, 'dimensao': None,
              'por_que': 'x', 'conceitos': ['x'], 'como': ['a', 'b'], 'onde_explorar': 'x', 'prompt': 'x',
              'duracao_min': minutos} for i in range(n)]
    pipeline.update_state({'trechos': plan.get('trechos', []) + [{'skill': skill, 'quando': '2026-11-24T10:00:00',
                                                                  'acoes': novas}]}, {'quando': '2026-11-24T10:00:00'})
    novo = pipeline.load_state()['plano']
    jogo.sincronizar(novo)
    return novo


def _alvo_gravado(nome):
    con = banco.conectar()
    try:
        return con.execute('SELECT alvo_lm FROM prisma WHERE nome = ?', (nome,)).fetchone()[0]
    finally:
        con.close()


def test_alvo_e_fixado_na_primeira_sincronizacao_com_o_lm_da_meta(plan):
    meta = sum(f['valor_lm'] for f in jogo.sincronizar(plan).values() if f['skill_plano'] == DDD and f['origem'] != 'chat')
    assert _alvo_gravado(DDD) == meta and _prisma(plan, DDD)['alvo_lm'] == meta


def test_acender_centelhas_novas_nunca_baixa_o_avanco(plan):
    _converter(_da_meta(plan, DDD)['id'], plan)
    antes = jogo.luz(plan)
    novo = _acender(plan, DDD)
    depois = jogo.luz(novo)
    assert depois['pct'] == antes['pct'] and depois['por_prisma'][DDD]['pct'] == antes['por_prisma'][DDD]['pct']
    assert depois['alvo_lm'] == antes['alvo_lm'] and depois['tot'] > antes['tot']  # mais oportunidades, mesmo alvo


def test_luz_refletida_nao_mexe_no_avanco_mas_aparece_na_composicao(plan):
    f = _da_meta(plan, DDD)
    _converter(f['id'], plan)
    antes = _prisma(plan, DDD)
    assert antes['luz_pct'] == 100
    novo = _acender(plan, DDD, n=1)
    extra = next(c for c in jogo.sincronizar(novo).values() if c['titulo'].startswith('Centelha extra'))
    con = banco.conectar()
    try:
        with banco.transacao(con):
            con.execute("UPDATE avanco SET estado = 'refletida' WHERE id = ?", (extra['id'],))
    finally:
        con.close()
    depois = jogo.luz(novo)['por_prisma'][DDD]
    assert depois['pct'] == antes['pct']
    assert depois['luz_pct'] == round(100 * f['valor_lm'] / (f['valor_lm'] + extra['valor_lm']))


def test_confirmar_sobe_o_avanco_ate_o_teto_de_100(plan):
    f = _da_meta(plan, DDD)
    r = _converter(f['id'], plan)
    assert r['pct_antes'] == 0 and r['pct_depois'] == 100 and _prisma(plan, DDD)['na_meta']
    novo = _acender(plan, DDD, n=1)
    extra = next(c for c in jogo.sincronizar(novo).values() if c['titulo'].startswith('Centelha extra'))
    _converter(extra['id'], novo)
    p = jogo.luz(novo)['por_prisma'][DDD]
    assert p['pct'] == 100 and p['contado'] == p['alvo_lm'] and p['propria'] > p['alvo_lm']  # o extra é evidência, não passa do teto


def test_trajetoria_soma_o_contado_de_cada_prisma_sobre_a_soma_dos_alvos(plan):
    _converter(_da_meta(plan, DDD)['id'], plan)
    t = jogo.luz(plan)
    assert t['alvo_lm'] == sum(p['alvo_lm'] for p in t['prismas'])
    assert t['contado'] == sum(min(p['propria'], p['alvo_lm']) for p in t['prismas'])
    assert t['pct'] == round(100 * t['contado'] / t['alvo_lm'])


def test_prisma_sem_centelhas_da_meta_ganha_o_alvo_padrao(plan):
    con = banco.conectar()
    try:
        with banco.transacao(con):
            con.execute('UPDATE prisma SET alvo_lm = NULL')
            con.execute("UPDATE avanco SET estado = 'descartada' WHERE prisma = ?", (TESTES,))
        jogo.fixar_alvos(con, plan)
    finally:
        con.close()
    assert _alvo_gravado(TESTES) == jogo.ALVO_PADRAO


def test_refazer_os_alvos_redefine_a_meta(plan):
    novo = _acender(plan, DDD)
    alvo_antes = _alvo_gravado(DDD)
    con = banco.conectar()
    try:
        jogo.fixar_alvos(con, novo, refazer=True)
    finally:
        con.close()
    assert _alvo_gravado(DDD) > alvo_antes  # a triagem (ou mudar a meta) é que redefine o alvo, de propósito


def test_marco_do_dossie_segue_o_avanco(plan):
    t = jogo.luz(plan)
    for p in t['prismas']:
        for f in [c for c in jogo.sincronizar(plan).values() if c['skill_plano'] == p['nome'] and c['origem'] != 'chat']:
            r = _converter(f['id'], plan)
    assert jogo.luz(plan)['pct'] == 100 and r['marco'] and r['marco']['n'] == 3


def test_ritmo_conta_o_que_falta_ate_o_alvo(plan):
    t = jogo.luz(plan)
    assert jogo.ritmo(plan, '12 meses')['lm_faltam'] == t['alvo_lm'] - t['contado']


def test_triagem_completa_cada_prisma_com_pelo_menos_3_centelhas_e_fixa_os_alvos(plan, monkeypatch):
    from luzia import cli
    chamadas = []

    def falso(plan_, skill, pct, rotulo):
        chamadas.append(skill)
        return ([{'titulo': f'Meta {i} de {skill}', 'tipo': 'explicar', 'skill': skill, 'dimensao': None, 'por_que': 'x',
                  'conceitos': ['x'], 'como': ['a', 'b'], 'onde_explorar': 'x', 'prompt': 'x', 'duracao_min': 15}
                 for i in range(3)], {'quando': '2026-11-24T11:00:00'})

    monkeypatch.setattr(cli, '_pedir_centelhas', falso)
    feitos = cli.completar_meta()
    novo = pipeline.load_state()['plano']
    cat = jogo.sincronizar(novo)
    t = jogo.luz(novo)
    for p in t['prismas']:
        meta = [f for f in cat.values() if f['skill_plano'] == p['nome'] and f['origem'] != 'chat' and f['estado'] != 'descartada']
        assert len(meta) >= cli.META_MINIMA, p['nome']
        assert _alvo_gravado(p['nome']) == sum(f['valor_lm'] for f in meta)
    assert sorted(feitos) == sorted(set(chamadas)) and feitos
    assert t['pct'] == 0


def test_completar_meta_segue_quando_o_modelo_falha(plan, monkeypatch):
    from luzia import cli

    def quebra(*a, **k):
        raise RuntimeError('sem rede')

    monkeypatch.setattr(cli, '_pedir_centelhas', quebra)
    assert cli.completar_meta() == []
    assert all(p['alvo_lm'] > 0 for p in jogo.luz(pipeline.load_state()['plano'])['prismas'])


def test_triagem_avisa_quando_algum_prisma_fica_com_meta_curta(plan, monkeypatch):
    """Teste com testadores (24/11): o limite por minuto da chave gratuita derrubava chamadas de completar a meta em silêncio."""
    from luzia import cli

    def quebra(*a, **k):
        raise RuntimeError('429 RESOURCE_EXHAUSTED')

    monkeypatch.setattr(cli, '_pedir_centelhas', quebra)
    cli.completar_meta()
    curtos = cli.prismas_com_meta_curta()
    assert curtos and all(isinstance(n, str) for n in curtos)
