"""Prismas, perfil e versões da trajetória no banco (Tarefa 5)."""

import json

import pytest

from luzia import banco, jogo, pipeline, trajetoria

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'
FRONT = 'Front-end (JS / Razor / React)'


@pytest.fixture
def con(privado):
    c = banco.conectar()
    yield c
    c.close()


def _lumen(con, prisma, lm, luz='propria'):
    with banco.transacao(con):
        con.execute("INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES ('2026-11-10T10:00:00', ?, ?, ?, 'feixe', 'x')",
                    (prisma, lm, luz))


def _centelha(con, fid, prisma, estado, lm):
    with banco.transacao(con):
        jogo._inserir_avanco(con, {'id': fid, 'skill_plano': prisma, 'skill': prisma, 'tipo': 'explicar',
                                   'titulo': f'Centelha {fid}', 'duracao_min': 10, 'valor_lm': lm,
                                   'estado': estado, 'origem': 'rota'})


def test_arquivado_fora_da_trajetoria_mas_lumens_contam(con):
    plan = pipeline.load_state()['plano']
    _lumen(con, DDD, 60)
    _lumen(con, TESTES, 40, 'refletida')
    _centelha(con, 'c1', DDD, 'propria', 60)
    _centelha(con, 'c2', DDD, 'apagada', 60)
    _centelha(con, 'c3', TESTES, 'refletida', 40)
    antes = jogo.luz(plan, con)
    assert (antes['tot'], antes['propria'], antes['pct']) == (160, 60, 38)
    assert trajetoria.lumens_totais(con) == (100, 60)
    with banco.transacao(con):
        con.execute("UPDATE prisma SET estado = 'arquivado' WHERE nome = ?", (DDD,))
    depois = jogo.luz(plan, con)
    assert (depois['tot'], depois['propria']) == (40, 0)  # a luz do arquivado sai da trajetória
    assert trajetoria.lumens_totais(con) == (100, 60)  # lúmens do arquivado continuam
    assert DDD not in [p['nome'] for p in trajetoria.prismas(con)]
    assert DDD in [p['nome'] for p in trajetoria.prismas(con, incluir_arquivados=True)]
    assert DDD not in jogo.ativos(plan, con)
    with banco.transacao(con):  # reativar devolve tudo
        con.execute("UPDATE prisma SET estado = 'ativo' WHERE nome = ?", (DDD,))
    assert jogo.luz(plan, con) == antes


def test_historico_de_niveis_e_so_leitura(con):
    with banco.transacao(con):
        con.execute("INSERT INTO nivel_registro (prisma, de, para, quando, origem, lm, luz_propria) "
                    "VALUES (?, 1, 2, '2026-11-01T10:00:00', 'conquistado', 160, 70)", (DDD,))
        con.execute("INSERT INTO nivel_registro (prisma, de, para, quando, origem) "
                    "VALUES (?, 1, 3, '2026-11-02T10:00:00', 'declarado')", (DDD,))
    assert trajetoria.historico_subidas(con) == [
        {'quando': '2026-11-01T10:00:00', 'skill': DDD, 'para': 2, 'lm': 160, 'luz_propria': 70}]  # só os conquistados
    for antigo in ('declarar_nivel', 'registrar_subida', 'acrescentar_subida', 'resumo', 'declarados', 'base_de', 'desde'):
        assert not hasattr(trajetoria, antigo)  # nada mais escreve nem lê níveis como medida de progresso


def test_nova_versao_guarda_foto(con):
    n1 = trajetoria.versoes(con)[-1]['numero']  # a migração já gravou a nº 1 (triagem)
    with banco.transacao(con):
        con.execute("UPDATE prisma SET estado = 'arquivado' WHERE nome = ?", (TESTES,))
    n2 = trajetoria.nova_versao(con, 'pedido', None)
    assert n2 == n1 + 1
    foto = trajetoria.versoes(con)[-1]
    assert foto['origem'] == 'pedido' and foto['numero'] == n2
    nomes = {p['nome']: p for p in foto['prismas']}
    assert set(nomes) == {DDD, FRONT} and nomes[DDD]['meta'] == 4
    assert trajetoria.versoes(con)[0]['numero'] == n1  # as antigas ficam como estavam
    assert len(trajetoria.versoes(con)[0]['prismas']) == 3


def test_rotulos_vem_do_plano(privado):
    assert pipeline.rotulos(pipeline.load_state()) == ('Júnior 3', 'Plena')


def test_autoavaliacao_da_triagem_e_so_leitura_do_perfil(con):
    assert pipeline.trajetoria_autoavaliacao() == {}  # a pessoa ainda não declarou nada
    with banco.transacao(con):
        trajetoria.perfil_gravar(con, 'autoavaliacao', {DDD: 3, 'Inexistente': 2})
    assert pipeline.trajetoria_autoavaliacao() == {DDD: 3}  # só prismas ativos; nada é escrito


def test_estado_vive_no_perfil(privado):
    estado = pipeline.load_state()
    assert estado['plano']['skills'][0]['nome'] == DDD
    pipeline.update_state({'trechos': ['a']}, {'quando': '2026-11-12T09:00:00'})
    assert pipeline.load_state()['plano']['trechos'] == ['a']
    with trajetoria.abrir() as con:
        assert trajetoria.perfil_ler(con, 'plano')['trechos'] == ['a']


def test_log_run_grava_chamada_modelo(privado):
    pipeline.log_run({'quando': '2026-11-12T09:00:00', 'rotulo': 'demo', 'modelo': 'm', 'tempo_modelo_s': 1.5,
                      'tokens_entrada': 10, 'tokens_saida': 5})
    with trajetoria.abrir() as con:
        r = con.execute('SELECT * FROM chamada_modelo').fetchone()
    assert (r['rotulo'], r['modelo'], r['segundos'], r['tokens_in'], r['tokens_out']) == ('demo', 'm', 1.5, 10, 5)
    assert json.loads(r['registro_json'])['rotulo'] == 'demo'
    assert pipeline.RUNS.exists()


def test_observer_e_statusline_veem_o_plano_atualizado(privado):
    from luzia import observer, statusline
    pipeline.update_state({'trechos': ['novo']}, {'quando': '2026-11-12T09:00:00'})
    assert observer.plano()['trechos'] == ['novo']
    assert statusline.trajetoria.plano()['trechos'] == ['novo']
    assert not (privado / 'career_state.json').read_text(encoding='utf-8').count('novo')  # o arquivo já não é a fonte


def test_triagem_nova_cria_prisma_e_versao_na_mesma_transacao(privado):
    plan = dict(pipeline.load_state()['plano'])
    plan['skills'] = plan['skills'] + [{'nome': 'Mensageria', 'luzia_sugere': 1, 'alvo': 3}]
    pipeline.save_state({}, plan, {'quando': '2026-11-12T10:00:00'}, {})
    with trajetoria.abrir() as con:
        assert 'Mensageria' in [p['nome'] for p in trajetoria.prismas(con)]
        assert [p['nome'] for p in trajetoria.versoes(con)[-1]['prismas']].count('Mensageria') == 1
