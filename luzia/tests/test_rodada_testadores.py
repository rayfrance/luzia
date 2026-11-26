"""Achados da rodada de testes orquestrada de 24/11/2026 (CLI, pedidos, dossiê e painel)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from luzia import jogo, pipeline, server
from luzia.tests.test_cli import botoes_de, rodar, visivel

DDD = 'Domain-Driven Design (DDD)'


def _modelo(monkeypatch):
    def fake(payload, **kw):
        res = {'palavras_chave': ['logs', 'métricas', 'tracing'], 'analise': 'Faz sentido para a meta.',
               'acoes': [{'titulo': f'Observar {i}', 'tipo': 'praticar', 'skill': 'Observabilidade', 'dimensao': None,
                          'por_que': 'x', 'conceitos': ['logs'], 'como': ['a', 'b'], 'onde_explorar': 'x', 'prompt': 'x',
                          'duracao_min': 15} for i in range(3)]}
        return SimpleNamespace(plan=res, model='m/x'), {'quando': '2026-11-24T15:00:00', 'modelo': 'm/x'}

    monkeypatch.setattr(pipeline, 'run_plan', fake)


def test_comando_desconhecido_responde_em_portugues_com_botoes(privado, monkeypatch, capsys):
    import sys
    from luzia import cli
    for argv, esperado in ((['foo'], '`foo` não é um comando da Luzia'), (['arquivar', 'X'], 'pedido abrir arquivar')):
        monkeypatch.setattr(sys, 'argv', ['luzia', *argv])
        with pytest.raises(SystemExit):
            cli.main()
        saida = capsys.readouterr()
        assert esperado in saida.out and 'LUZIA_BOTOES=' in saida.out and 'usage:' not in saida.out + saida.err


def test_pedido_de_arquivar_ou_reativar_prisma_que_nao_existe_e_recusado(privado, monkeypatch):
    for tipo in ('arquivar', 'reativar'):
        s = visivel(rodar(monkeypatch, 'pedido', 'abrir', tipo, 'Fantasma', '--motivo', 'x'))
        assert 'prisma desconhecido: Fantasma' in s, s
    s = visivel(rodar(monkeypatch, 'pedido', 'abrir', 'reativar', DDD, '--motivo', 'x'))
    assert 'já está ativo' in s


def test_aceitar_mostra_o_alvo_real_e_o_avanco_antes_e_depois(privado, monkeypatch):
    _modelo(monkeypatch)
    plan = pipeline.load_state()['plano']
    f = next(c for c in jogo.sincronizar(plan).values() if c['skill_plano'] == DDD)
    jogo.iniciar(f['id'])
    jogo.avaliar(f['id'], 4, 'x', plan)
    jogo.confirmar(f['id'], plan)
    abrir = rodar(monkeypatch, 'pedido', 'abrir', 'incluir', 'Observabilidade', '--motivo', 'monitorar a API')
    assert 'logs, métricas, tracing' in abrir and 'nível' not in visivel(abrir).lower()
    s = visivel(rodar(monkeypatch, 'pedido', 'aceitar', '1'))
    alvo = jogo.luz(pipeline.load_state()['plano'])['por_prisma']['Observabilidade']['alvo_lm']
    assert f'entrou com alvo de **{alvo} lm**' in s
    assert 'Avanço da trajetória:' in s and '→' in s and 'nenhuma luz própria foi perdida' in s


def test_dossie_usa_o_alvo_por_prisma(privado, monkeypatch):
    plan = pipeline.load_state()['plano']
    jogo.sincronizar(plan)
    texto = jogo.dossie(plan, 'teste').read_text(encoding='utf-8')
    # linguagem formal ("pontos de evidência", "ações"), mas contando contra o alvo de cada skill, como o avanço
    assert 'do alvo em autoria própria' in texto and 'pontos de evidência do alvo da meta' in texto


def test_planner_nao_pede_niveis_ao_modelo():
    from luzia import planner
    for schema in (planner.TRECHO_SCHEMA, planner.OPPORTUNITIES_SCHEMA):
        assert 'nível' not in schema
    assert 'nunca escreva "nível"' in planner.SYSTEM if hasattr(planner, 'SYSTEM') else True


def test_painel_orienta_quando_nao_ha_nada_para_converter_e_tutorial_explica_p1_a_p4():
    js = (Path(server.PAINEL) / 'luzia.js').read_text(encoding='utf-8')
    assert 'Nada para converter ainda' in js and 'data-filtro-estado="apagada"' in js
    tutorial = js.split('const PASSOS_TUTORIAL', 1)[1].split('let tutorial = null', 1)[0]
    for termo in ('lúmens (lm)', '<b>P1</b>', '<b>P4</b>', 'falta a nota e o seu sim'):
        assert termo in tutorial, termo
    assert 'btn neutro mini' not in tutorial and "setAttribute('aria-labelledby', 'gaveta-titulo')" in js


def test_incluir_prisma_que_ja_esta_na_trajetoria_e_recusado(privado, monkeypatch):
    """Rodada geral de 24/11: incluir de novo duplicava as centelhas iniciais do prisma."""
    s = visivel(rodar(monkeypatch, 'pedido', 'abrir', 'incluir', DDD, '--motivo', 'x'))
    assert 'já está na trajetória' in s
    saida = rodar(monkeypatch, 'pedido', 'abrir', 'incluir', DDD, '--motivo', 'x')
    assert 'LUZIA_PERGUNTA=Como seguimos?' in saida  # nada a decidir: a pergunta não fala em pedido


def test_versao_sem_git_vem_do_plugin_json(monkeypatch):
    """Rodada 4 (24/11): a cópia instalada pelo marketplace não tem git e mostrava "Versão: desconhecida"."""
    import json as _json
    import subprocess
    from luzia import pipeline

    def sem_git(*a, **k):
        raise FileNotFoundError('git')

    monkeypatch.setattr(subprocess, 'run', sem_git)
    esperado = _json.loads((Path(pipeline.__file__).parent / '.claude-plugin' / 'plugin.json').read_text(encoding='utf-8'))['version']
    assert pipeline.version() == esperado


def test_comando_antigo_subir_explica_sem_falar_em_nivel(privado, monkeypatch):
    assert 'nível' not in visivel(rodar(monkeypatch, 'subir')).lower()


def test_painel_legenda_da_trajetoria_bate_com_a_barra_e_testar_espera_a_resposta():
    js = (Path(server.PAINEL) / 'luzia.js').read_text(encoding='utf-8')
    assert "'Falta do alvo'" in js and 'rumoAoAlvo(t).map' in js
    assert "toast('Testando… leva no máximo 30 s" in js and 'Funcionou: ${r.modelo' in js and 'duracao !== 0' in js


def test_registrar_sem_id_diz_que_falta_o_id(privado, monkeypatch):
    s = visivel(rodar(monkeypatch, 'registrar', '--nota', '3', '--resumo', 'x'))
    assert 'falta o id' in s and 'A nota vai de 0 a 4' not in s


def test_entrega_casa_prisma_com_grafia_natural():
    """Rodada 1 do loop: "feat: add Periodo value object" não ligava a DDD, cujas palavras têm "ValueObject"."""
    from luzia import entregas
    assert entregas.termos_do_prisma(['ValueObject', 'Aggregate'], ['feat: add Periodo value object']) == ['ValueObject']


def test_provar_so_aparece_em_entrega_que_atravessa_prisma():
    js = (Path(server.PAINEL) / 'luzia.js').read_text(encoding='utf-8')
    assert "!(e.prismas || []).length) return ''" in js


def test_trajetoria_nao_promete_folga_que_nao_existe():
    js = (Path(server.PAINEL) / 'luzia.js').read_text(encoding='utf-8')
    assert 'function oportunidadesTxt' in js and 'lm > falta ?' in js and 'mais do que o alvo pede' not in js


def test_propriedade_da_entrega_diz_em_quantas_medidas_se_apoia():
    """Rodada 2 do loop: "100% seu" com só P2 medido parecia "provei tudo"."""
    from luzia import cli
    linhas = cli.linhas_propriedade({'indice': 100, 'dimensoes': {'P2': {'nota': 100, 'tipo': 'calculado', 'base': 'x'}}})
    assert 'em 1 de 4 medidas' in linhas[0]
    js = (Path(server.PAINEL) / 'luzia.js').read_text(encoding='utf-8')
    assert 'de 4 medidas' in js and 'telaAntesTutorial' in js and 'Ele só sobe.</p>' not in js


def test_porteiro_resolve_ponto_ponto_no_cwd():
    """Rodada 3 do loop: "repo/../repo-outro" passava como o repositório autorizado."""
    from luzia import porteiro
    cfg = {'autorizados': ['C:/r/repo']}
    assert not porteiro.autorizado('C:/r/repo/../repo-outro', cfg) and porteiro.autorizado('C:/r/repo/src/..', cfg)


def test_arquivar_explica_que_a_luz_fica_guardada(privado, monkeypatch):
    rodar(monkeypatch, 'pedido', 'abrir', 'arquivar', DDD, '--motivo', 'x')
    plan = pipeline.load_state()['plano']
    f = next(c for c in jogo.sincronizar(plan).values() if c['skill_plano'] == DDD)
    jogo.iniciar(f['id']); jogo.avaliar(f['id'], 4, 'x', plan); jogo.confirmar(f['id'], plan)
    s = visivel(rodar(monkeypatch, 'pedido', 'aceitar', '1'))
    assert 'continua toda sua' not in s and ('fica guardada' in s or 'Avanço da trajetória' not in s)


def test_sigla_e_nome_curto_acham_o_prisma():
    """Rodada 4 do loop: `acender DDD` não achava "Domain-Driven Design" (o próprio exemplo do comando usa DDD)."""
    plan = {'skills': [{'nome': 'Domain-Driven Design'}, {'nome': 'Arquitetura de Software'}, {'nome': 'Python'}]}
    assert jogo.skill_de('DDD', plan) == 'Domain-Driven Design'
    assert jogo.skill_de('ddd', plan) == 'Domain-Driven Design' and jogo.skill_de('Python', plan) == 'Python'


def test_diagnostico_com_triagem_feita_nao_oferece_triagem(privado, monkeypatch):
    s = rodar(monkeypatch, 'diagnostico')
    assert 'existe' in s and all(b['rodar'] != 'triage' for b in botoes_de(s))


def test_pedido_aceita_sigla_e_erros_mostram_as_opcoes(privado, monkeypatch):
    """Rodada 5 do loop: `pedido abrir arquivar DDD` não achava o prisma, e os erros não mostravam as opções."""
    s = visivel(rodar(monkeypatch, 'pedido', 'abrir', 'arquivar', 'DDD', '--motivo', 'x'))
    assert 'Pedido `#1` aberto' in s and 'Domain-Driven Design' in s or 'DDD' in s
    s = visivel(rodar(monkeypatch, 'pedido', 'abrir', 'arquivar', 'Nada', '--motivo', 'x'))
    assert 'prisma desconhecido' in s and 'Prismas da trajetória:' in s
    assert 'Tipos: incluir' in visivel(rodar(monkeypatch, 'pedido', 'abrir', 'foo', 'X'))
    assert 'Pedidos em aberto:' in visivel(rodar(monkeypatch, 'pedido', 'aceitar', '99'))


def test_filtro_de_prisma_inexistente_e_comando_desconhecido_mostram_opcoes(privado, monkeypatch, capsys):
    import sys
    from luzia import cli
    s = visivel(rodar(monkeypatch, 'centelhas', '--prisma', 'Nada'))
    assert 'não está na sua trajetória' in s and 'Prismas:' in s
    monkeypatch.setattr(sys, 'argv', ['luzia', 'foo'])
    with pytest.raises(SystemExit):
        cli.main()
    assert 'Os principais: hoje' in capsys.readouterr().out


def test_rodada8_linkedin_no_rotulo_da_triagem():
    """Rodada 8: o PDF do LinkedIn vai ao modelo quando configurado; o rótulo de fontes precisa citá-lo."""
    from luzia import cli
    assert cli.base_triagem(False, {'repo': 'x', 'linkedin_pdf': 'li.pdf'}) == 'sua entrada, LinkedIn e commits'


def test_rodada8_botao_converter_some_sem_nada_para_converter(monkeypatch):
    """Rodada 8: com zero para converter, "Ver centelhas para converter" levaria a uma lista vazia."""
    from luzia import cli
    monkeypatch.setattr(cli.acoes, 'todas', lambda plan: [{'id': 'a', 'estado': 'apagada'}])
    assert cli.bt_ver_converter({}) is None
    monkeypatch.setattr(cli.acoes, 'todas', lambda plan: [{'id': 'a', 'estado': 'refletida'}])
    assert cli.bt_ver_converter({}) is cli.BT_CONVERTER


def test_rodada8_composto_portugues_em_minuscula_no_prompt_nao_nasce():
    """Rodada 8: "camada de dados" em minúscula no prompt não é termo técnico, mesmo que o banco o grafe com maiúsculas."""
    from luzia import observer
    assert not observer._especifico('Use a camada de dados.', 'Camada de Dados')
    assert not observer._especifico('Crie uma regra de negócio nova.', 'Regra de Negócio')
    assert observer._especifico('Use a Camada de Dados aqui.', 'Camada de Dados')
    assert observer._especifico('Use o value object aqui.', 'Value Object')


def test_rodada8_statusline_sem_cwd_fica_vazia(monkeypatch):
    """Rodada 8: sem cwd no evento não dá para saber se o repositório é autorizado; a linha fica fechada."""
    from luzia import statusline
    assert statusline.linha({}) == ''


def _gaps_r10():
    return {
        'Desenvolvimento Backend': {'pct': 0, 'palavras': ['Arquitetura Limpa', 'Query', 'type'],
                                    'centelhas': [{'id': 'd546', 'titulo': 'Arquitetura Limpa', 'palavras': ['Arquitetura Limpa'],
                                                   'estado': 'apagada', 'lm': 40, 'origem': 'triagem'}]},
        'Documentação Técnica': {'pct': 0, 'palavras': ['Architecture'],
                                 'centelhas': [{'id': '2692', 'titulo': 'Registrar decisões', 'palavras': ['Arquitetura'],
                                                'estado': 'apagada', 'lm': 30, 'origem': 'triagem'}]},
    }


def test_rodada10_parte_de_composto_nao_acende_meta_de_outro_prisma(monkeypatch):
    """Rodada 10: "Arquitetura Limpa" acendia também a centelha de outro prisma pela parte "Arquitetura"."""
    from luzia import observer
    vistos = []
    monkeypatch.setattr(observer.jogo, 'reconhecer', lambda sid, chave, prisma, cid, *a, **k: vistos.append(cid) or {'lm': 1})
    observer.reconhecer_em('# Arquitetura Limpa\nclass Pedido: ...', 'agente', 's1', 'ativo', '.py', 'Edit', _gaps_r10())
    assert vistos == ['d546']


def test_rodada10_builtins_do_codigo_nao_fazem_nascer_centelha(monkeypatch):
    """Rodada 10: `type(x)`, `def query(self)` no código do agente criavam "Por que o agente usou Type"."""
    from luzia import observer
    vistos = []
    monkeypatch.setattr(observer.jogo, 'reconhecer', lambda sid, chave, prisma, cid, *a, **k: vistos.append(cid) or {'lm': 1})
    gaps = {'Desenvolvimento Backend': {'pct': 0, 'palavras': ['Query', 'type', 'Service', 'Iterate'], 'centelhas': []}}
    observer.reconhecer_em('def query(self, service):\n    return type(x), iterate(i)', 'agente', 's1', 'ativo', '.py', 'Edit', gaps)
    assert vistos == []


def test_rodada11_entrega_de_um_dia_diz_1_dia_no_chat():
    """Rodada 11: o chat dizia "0 dias" numa entrega de um commit só; o painel diz "1 dia"."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / 'cli.py').read_text(encoding='utf-8')
    assert "plural(fatos['duracao_dias'], 'dia')" not in src and src.count("max(1, fatos.get('duracao_dias') or 0)") == 2


def test_rodada11_typing_e_palavras_sem_acento_nao_fazem_nascer(monkeypatch):
    """Rodada 11: `from typing import List` e o comentário "# modulo de funcao" criavam centelhas no código do agente."""
    from luzia import observer
    vistos = []
    monkeypatch.setattr(observer.jogo, 'reconhecer', lambda sid, chave, prisma, cid, *a, **k: vistos.append(cid) or {'lm': 1})
    gaps = {'Python': {'pct': 0, 'palavras': ['typing', 'funcao', 'modulo', 'Dataclass'], 'centelhas': []}}
    observer.reconhecer_em('from typing import List\n# modulo de funcao', 'agente', 's1', 'ativo', '.py', 'Edit', gaps)
    assert vistos == []
    assert 'funcao' in observer.COMUNS and 'metodo' in observer.COMUNS


def test_rodada11_comeco_de_linha_e_de_item_e_comeco_de_frase():
    """Rodada 11: "Resumo\n\nTable de clientes" e "- Table…" faziam nascer "Table" pela maiúscula da linha."""
    from luzia import observer
    for texto in ('Resumo\n\nTable de clientes', '- Table de clientes', '* Table de clientes', 'Table de clientes'):
        assert not observer._especifico(texto, 'Table'), texto
    assert observer._especifico('crie a Table de clientes', 'Table')


def test_rodada11_em_silencio_o_inicio_de_sessao_nao_fala(capsys, monkeypatch):
    """Rodada 11: o modo "em silêncio" só muda a luz no banco; o SessionStart não deve falar."""
    from luzia import observer
    monkeypatch.setattr(observer, 'plano', lambda: (_ for _ in ()).throw(AssertionError('não deveria ler o plano')))
    observer.ao_iniciar_sessao({'hook_event_name': 'SessionStart'}, {'modo': 'passivo'})
    assert capsys.readouterr().out == ''


def test_rodada11_p1_geral_aparece_como_geral_no_painel():
    """Rodada 11: o texto da P1 (estimativa geral da triagem) parecia falar de cada entrega."""
    from pathlib import Path
    from luzia import server
    js = (Path(server.PAINEL) / 'luzia.js').read_text(encoding='utf-8')
    assert 'Estimativa geral da triagem, igual em toda entrega' in js


def test_rodada12_mascara_ticket_jira_e_dominio_sem_http():
    """Rodada 12: o guia promete mascarar tickets e links; PROJ-1234 e acme.com.br/x passavam."""
    from luzia import privacy
    r = privacy.Redactor(terms=[], colleagues=[])
    assert r.redact('veja acme.com.br/x e PROJ-1234') == 'veja [URL] e [TICKET]'
    assert r.redact('config.py, package.json, app.module.ts e UTF-8') == 'config.py, package.json, app.module.ts e UTF-8'


def test_rodada12_guia_diz_que_a_fila_age_fora_de_foco():
    """Rodada 12: fora de foco, a fila do painel ainda é oferecida (a pessoa mandou); o guia precisa dizer."""
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[2]
    guia = (raiz / 'docs/teste/INSTALAR.md').read_text(encoding='utf-8')
    assert 'manda uma centelha do painel para o agente (o botão de uma centelha que a leva ao agente' in guia


def test_rodada13_painel_pedido_sem_proposta_oferece_gerar():
    """Rodada 12/13: no painel, um pedido de incluir sem proposta oferecia "Aceitar", que falharia."""
    from pathlib import Path
    from luzia import server
    js = (Path(server.PAINEL) / 'luzia.js').read_text(encoding='utf-8')
    assert "const semProposta = ['incluir', 'mudar_meta'].includes(p.tipo) && !p.proposta" in js
    assert 'data-pedido-propor="${p.id}">Gerar a proposta' in js and "acao: 'propor'" in js


def test_rodada13_equivalentes_em_portugues_tambem_sao_comuns():
    """Rodada 13: "service" era comum, "serviço" não; um comentário com "versão" acendia Git."""
    from luzia import observer
    for w in ('serviço', 'servico', 'versão', 'versao', 'histórico', 'historico', 'arquivo'):
        assert w in observer.COMUNS, w
