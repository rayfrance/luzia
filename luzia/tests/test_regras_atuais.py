"""Regras atuais do jogo, da CLI e do instalador (rede de segurança para a troca de JSON por SQLite).

Antes eram os roteiros avulsos teste_lote1.py e teste_lote23.py, que copiavam a pasta privada real. Agora cada teste
roda na fixture `privado`, com dados sintéticos. O modelo é o das centelhas (docs/specs/2026-11-18-centelhas-conversao.md):
luz própria, refletida e por acender; converter = a Luzia confirma (nota 3 ou 4) e a pessoa dá o sim.
"""

import io
import json
import sys
import time
from contextlib import redirect_stdout
from types import SimpleNamespace

import pytest

from luzia import acoes, arquivos, banco, cli, instalar, jogo, observer, pipeline

DDD = 'Domain-Driven Design (DDD)'
TESTES = 'Testes e Qualidade / SQL'


@pytest.fixture
def plan(privado):
    return pipeline.load_state()['plano']


@pytest.fixture
def apagadas(plan):
    cat = jogo.sincronizar(plan)
    return [k for k, f in cat.items() if f['estado'] == 'apagada']


def _confirmada(plan, fid, nota=3):
    """Centelha em conversão que a Luzia já confirmou (falta só o sim da pessoa)."""
    jogo.iniciar(fid, 'teste')
    return jogo.avaliar(fid, nota, 't', plan)


def _linhas(sql):
    con = banco.conectar()
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _centelhas():
    con = banco.conectar()
    try:
        return {f['id']: f for f in jogo.avancos(con)}
    finally:
        con.close()


# ------------------------------------------------------------------ conversão: a Luzia confirma, a pessoa dá o sim
def test_registrar_sem_iniciar_e_recusado(plan, apagadas):
    assert jogo.avaliar(apagadas[0], 4, 't', plan).get('erro', '').startswith('esta centelha ainda não está em conversão')


def test_nota_3_confirma_o_entendimento_mas_so_o_sim_vira_luz_propria(plan, apagadas):
    f1 = apagadas[0]
    r = _confirmada(plan, f1)
    assert r['confirmada'] and not r['tente_de_novo']
    assert _centelhas()[f1]['estado'] == 'convertendo' and _centelhas()[f1]['confirmada_em']
    assert jogo.livro() == []  # a nota sozinha não rende lúmen


def test_o_sim_paga_o_valor_inteiro_sem_credito_parcial(plan, apagadas):
    f1, f2 = apagadas[0], apagadas[1]
    v1, v2 = _centelhas()[f1]['valor_lm'], _centelhas()[f2]['valor_lm']
    _confirmada(plan, f1, nota=3)
    _confirmada(plan, f2, nota=4)
    assert jogo.confirmar(f1, plan)['ganho'] == v1  # nota 3 vale o mesmo que nota 4
    assert jogo.confirmar(f2, plan)['ganho'] == v2
    assert _centelhas()[f1]['lm_ganho'] == v1 and _centelhas()[f1]['estado'] == 'propria'


def test_enviar_para_a_fila_coloca_em_conversao(plan, apagadas):
    f1 = apagadas[0]
    assert jogo.enfileirar(f1)
    assert _centelhas()[f1]['estado'] == 'convertendo'


def test_confirmar_sem_a_confirmacao_da_luzia_e_recusado(plan, apagadas):
    f1 = apagadas[0]
    assert 'ainda não confirmou' in jogo.confirmar(f1, plan).get('erro', '')
    jogo.iniciar(f1)
    assert 'ainda não confirmou' in jogo.confirmar(f1, plan).get('erro', '')
    assert jogo.livro() == []


def test_segundo_sim_e_recusado_e_o_livro_soma_o_valor_uma_vez(plan, apagadas):
    f1 = apagadas[0]
    v = _centelhas()[f1]['valor_lm']
    _confirmada(plan, f1, nota=4)
    jogo.confirmar(f1, plan)
    assert 'já é luz própria' in jogo.confirmar(f1, plan).get('erro', '')
    assert 'já é luz própria' in jogo.avaliar(f1, 4, 't', plan).get('erro', '')
    assert sum(x['lm'] for x in jogo.livro() if x['ref'] == f1) == v


def test_luz_propria_nao_volta_a_ser_conversao(plan, apagadas):
    f1 = apagadas[0]
    _confirmada(plan, f1, nota=4)
    jogo.confirmar(f1, plan)
    assert jogo.iniciar(f1) is None and jogo.enfileirar(f1) is None and jogo.descartar(f1, 'agora_nao') is None
    assert _centelhas()[f1]['estado'] == 'propria'


# ------------------------------------------------------------------ tente de novo
def test_nota_1_tente_de_novo_mantem_convertendo(plan, apagadas):
    f2 = apagadas[1]
    jogo.iniciar(f2)
    r = jogo.avaliar(f2, 1, 'Falta o porquê', plan)
    assert r.get('tente_de_novo') and not r['confirmada']
    f = _centelhas()[f2]
    assert f['estado'] == 'convertendo' and f['tentativas'] == 1 and not f['confirmada_em']


def test_segunda_tentativa_na_mesma_sessao_e_aceita(plan, apagadas):
    f2 = apagadas[1]
    jogo.iniciar(f2)
    jogo.avaliar(f2, 1, 't', plan)
    assert jogo.avaliar(f2, 4, 't', plan)['confirmada']
    assert jogo.confirmar(f2, plan)['ganho'] > 0


def test_centelha_propria_com_estado_perdido_nao_paga_de_novo(plan, apagadas):
    f3 = apagadas[2]
    con = banco.conectar()
    with banco.transacao(con):
        con.execute("UPDATE avanco SET estado = 'propria', lm_ganho = 20, nota = 4 WHERE id = ?", (f3,))
    con.close()
    assert 'erro' in jogo.avaliar(f3, 4, 't', plan) and 'erro' in jogo.confirmar(f3, plan)
    assert jogo.livro() == []


# ------------------------------------------------------------------ arquivos
def test_catalogo_sem_mudanca_nao_e_regravado(plan, apagadas):
    espiao = banco.conectar()  # data_version muda quando outra conexão confirma uma gravação
    antes = espiao.execute('PRAGMA data_version').fetchone()[0]
    jogo.catalogo(plan)
    assert espiao.execute('PRAGMA data_version').fetchone()[0] == antes
    espiao.close()


def _corromper(privado):
    """Um JSON de configuração quebrado (o jogo em si já não usa JSON: a leitura segura é a de `arquivos`)."""
    caminho = privado / 'config-teste.json'
    caminho.write_text('{"quebrado":', encoding='utf-8')
    return caminho


def test_json_corrompido_devolve_o_padrao(privado, apagadas):
    assert arquivos.ler_json(_corromper(privado), {}) == {}


def test_uma_unica_copia_do_arquivo_ruim(privado, apagadas):
    caminho = _corromper(privado)
    arquivos.ler_json(caminho, {})
    arquivos.ler_json(caminho, {})
    assert len(list(privado.glob('config-teste.json.corrompido-*'))) == 1


def test_erro_registrado_so_com_o_tipo(privado, apagadas):
    arquivos.ler_json(_corromper(privado), {})
    log = (privado / 'erros.log').read_text(encoding='utf-8')
    assert 'JSONDecodeError' in log
    assert 'quebrado' not in log


def test_gravacoes_nao_deixam_temporario(privado, plan, apagadas):
    _confirmada(plan, apagadas[0])
    jogo.confirmar(apagadas[0], plan)
    acoes.enfileirar(apagadas[1], 't')
    assert not list(privado.glob('.*.tmp'))


# ------------------------------------------------------------------ observador
def test_hook_agente_aplicou_o_conceito_vira_luz_refletida(privado, plan, capsys):
    cfg = json.loads((privado / 'observer.json').read_text(encoding='utf-8'))
    lac = observer.lacunas(plan)
    _, info = next(iter(lac.items()))
    evento = {'session_id': 's-teste', 'tool_name': 'Write', 'cwd': cfg['autorizados'][0],
              'tool_input': {'file_path': 'x.cs', 'content': ' '.join(info['palavras'][:3])}}
    observer.ao_usar_ferramenta(evento, cfg)
    saida = capsys.readouterr().out
    assert 'luz refletida' in saida and 'Converter agora' in saida
    nascidas = _linhas("SELECT estado, origem FROM avanco WHERE origem = 'chat'")
    assert [(r['estado'], r['origem']) for r in nascidas] == [('refletida', 'chat')]


# ------------------------------------------------------------------ CLI termina em botões
def rodar(monkeypatch, *argv):
    monkeypatch.setattr(sys, 'argv', ['luzia', *argv])
    buf = io.StringIO()
    with redirect_stdout(buf):
        cli.main()
    return buf.getvalue()


def botoes_de(saida):
    linha = next((x for x in saida.splitlines() if x.startswith('LUZIA_BOTOES=')), None)
    return json.loads(linha.split('=', 1)[1]) if linha else []


def test_rotulos_da_rota_vem_da_declaracao(privado):
    assert pipeline.rotulos(pipeline.load_state()) == ('Júnior 3', 'Plena')


def test_hoje_oferece_botoes_com_cli_e_pergunta(privado, monkeypatch):
    s = rodar(monkeypatch, 'hoje')
    assert 'LUZIA_CLI=' in s and 'LUZIA_PERGUNTA=' in s
    assert 1 <= len(botoes_de(s)) <= 3


def test_hoje_primeiro_botao_continua_a_centelha_convertendo(apagadas, monkeypatch):
    jogo.iniciar(apagadas[1], 'aqui')
    b = botoes_de(rodar(monkeypatch, 'hoje'))
    assert b[0]['rodar'] == f'fazer {apagadas[1]}'
    assert 'Continuar' in b[0]['rotulo']


def test_hoje_sem_comando_cru_na_parte_visivel(apagadas, monkeypatch):
    jogo.iniciar(apagadas[0], 'aqui')
    s = rodar(monkeypatch, 'hoje')
    visivel = chr(10).join(l for l in s.splitlines() if not l.startswith('LUZIA_'))
    assert '/lz.py' not in visivel
    assert 'cd /c/' not in visivel


def test_entendimento_confirmado_vira_o_primeiro_botao_de_hoje(plan, apagadas, monkeypatch):
    _confirmada(plan, apagadas[0], nota=4)
    b = botoes_de(rodar(monkeypatch, 'hoje'))
    assert b[0]['rodar'] == f'confirmar {apagadas[0]}' and b[0]['rotulo'] == 'Acender luz própria'


def test_depois_do_sim_o_primeiro_botao_converte_a_proxima_luz_refletida(plan, apagadas, monkeypatch):
    con = banco.conectar()
    with banco.transacao(con):
        con.execute("UPDATE avanco SET estado = 'refletida' WHERE id = ?", (apagadas[1],))
    con.close()
    _confirmada(plan, apagadas[0], nota=4)
    s = rodar(monkeypatch, 'confirmar', apagadas[0])
    assert s.startswith('✦ **+')
    assert botoes_de(s)[0]['rodar'] == f'fazer {apagadas[1]}'


# ------------------------------------------------------------------ trecho (modelo simulado)
@pytest.fixture
def modelo_falso(privado, monkeypatch):
    fake = {'acoes': [{'titulo': f'Centelha nova {i}', 'tipo': 'praticar', 'skill': 'qualquer', 'por_que': 'p',
                       'conceitos': ['c'], 'como': ['a', 'b'], 'onde_explorar': 'o', 'prompt': 'x', 'duracao_min': 15}
                      for i in range(3)]}
    registro = {'quando': jogo.agora(), 'tempo_total_s': 1, 'pico_memoria_mib': 1, 'tokens_entrada': 1,
                'tokens_saida': 1, 'versao': 't', 'modelo': 'fake'}
    monkeypatch.setattr(pipeline, 'run_plan', lambda payload, **kw: (SimpleNamespace(plan=fake), registro))


def test_trecho_cria_3_centelhas_da_skill_certa_apagadas_e_com_valor(modelo_falso):
    res = cli.gerar_trecho(DDD)
    assert len(res['feixes']) == 3
    assert all(f['skill_plano'] == DDD and f['origem'] == 'trecho' for f in res['feixes'])
    assert all(f['estado'] == 'apagada' and 10 <= f['valor_lm'] <= 100 for f in res['feixes'])


def test_trecho_nao_recalcula_o_valor_das_centelhas_que_ja_existem(modelo_falso):
    plan = pipeline.load_state()['plano']
    antes = {k: f['valor_lm'] for k, f in jogo.sincronizar(plan).items()}
    cli.gerar_trecho(DDD)
    depois = {k: f['valor_lm'] for k, f in jogo.sincronizar(pipeline.load_state()['plano']).items()}
    assert all(depois[k] == v for k, v in antes.items())


def test_trecho_recusa_prisma_que_ja_e_todo_luz_propria(modelo_falso, plan):
    for k, f in jogo.sincronizar(plan).items():
        con = banco.conectar()
        with banco.transacao(con):
            con.execute("UPDATE avanco SET estado = 'propria' WHERE id = ?", (k,))
        con.close()
    assert 'todo luz própria' in cli.gerar_trecho(DDD)['erro']


def test_trecho_fica_salvo_no_estado_privado(modelo_falso):
    cli.gerar_trecho(DDD)
    assert len(pipeline.load_state()['plano'].get('trechos', [])) == 1


def test_comando_trecho_oferece_as_centelhas_novas_em_botoes(modelo_falso, monkeypatch):
    b = botoes_de(rodar(monkeypatch, 'trecho', DDD))
    assert len(b) == 3
    assert all(x['rodar'].startswith('fazer ') for x in b)


# ------------------------------------------------------------------ registrar, confirmar e descartar
def test_registrar_nota_3_oferece_acender_a_luz_propria(plan, apagadas, monkeypatch):
    rodar(monkeypatch, 'fazer', apagadas[0])
    s = rodar(monkeypatch, 'registrar', apagadas[0], '--nota', '3', '--resumo', 'teste')
    assert 'a Luzia confirmou seu entendimento' in s
    assert botoes_de(s)[0]['rotulo'] == 'Acender luz própria'


def test_descartar_oferece_desfazer(plan, apagadas, monkeypatch):
    b = botoes_de(rodar(monkeypatch, 'descartar', apagadas[0], '--motivo', 'agora_nao'))
    assert b and b[0]['rodar'] == f"restaurar {apagadas[0]}"


def test_descartar_luz_propria_nao_muda_nada(plan, apagadas, monkeypatch):
    _confirmada(plan, apagadas[0], nota=4)
    jogo.confirmar(apagadas[0], plan)
    s = rodar(monkeypatch, 'descartar', apagadas[0])
    assert 'já é luz própria' in s and _centelhas()[apagadas[0]]['estado'] == 'propria'


def test_restaurar_volta_ao_estado_de_antes(plan, apagadas, monkeypatch):
    con = banco.conectar()
    with banco.transacao(con):
        con.execute("UPDATE avanco SET estado = 'refletida' WHERE id = ?", (apagadas[0],))
    con.close()
    rodar(monkeypatch, 'descartar', apagadas[0])
    s = rodar(monkeypatch, 'restaurar', apagadas[0])
    assert 'voltou para luz refletida' in s and _centelhas()[apagadas[0]]['estado'] == 'refletida'


# ------------------------------------------------------------------ lote 3 · instalador num HOME falso
@pytest.fixture
def casa(privado, tmp_path, monkeypatch):
    claude = tmp_path / 'casa' / '.claude'
    monkeypatch.setattr(instalar, 'CLAUDE', claude)
    monkeypatch.setattr(instalar, 'SETTINGS', claude / 'settings.json')
    claude.mkdir(parents=True)
    instalar.SETTINGS.write_text(json.dumps({'statusLine': {'type': 'command', 'command': 'outra.sh'}, 'model': 'x'}),
                                 encoding='utf-8')
    return claude


def test_comandos_instalados_com_o_caminho_resolvido(casa):
    instalar.comandos()
    hoje_md = (casa / 'commands' / 'luzia' / 'hoje.md').read_text(encoding='utf-8')
    assert '${CLAUDE_PLUGIN_ROOT}' not in hoje_md
    assert '/lz.py" cli' in hoje_md


def test_hooks_registrados_uma_vez_so(casa):
    assert instalar.hooks() == ['SessionStart', 'UserPromptSubmit', 'PostToolUse']
    assert instalar.hooks() == []


def test_nao_troca_uma_linha_de_status_que_ja_existe(casa):
    assert 'outra' in instalar.statusline()


def test_demais_configuracoes_preservadas(casa):
    instalar.hooks()
    instalar.statusline()
    d = json.loads(instalar.SETTINGS.read_text(encoding='utf-8'))
    assert d['model'] == 'x'
    assert d['statusLine']['command'] == 'outra.sh'


def test_backup_do_settings_feito(casa):
    instalar.hooks()
    assert len(list(casa.glob('settings.json.antes-luzia-*'))) >= 1


def test_regras_para_outros_agentes_com_o_caminho_certo(privado):
    regras = instalar.regras()
    assert '<LUZIA_CLI>' not in regras
    assert '/lz.py" cli' in regras
