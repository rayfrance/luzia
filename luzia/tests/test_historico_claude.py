"""Histórico do Claude Code na triagem (27/11/2026): com o sim da pessoa, a Luzia lê prompts e sessões recentes,
memórias e CLAUDE.md para o plano refletir o trabalho real. Nunca o código que o agente escreveu; segredos saem sempre."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from luzia import privacy, triage

CHAVE = 'sk-' + 'a' * 30


def _sessao(pasta: Path, nome: str, linhas: list[dict], idade_dias: float = 1) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    f = pasta / f'{nome}.jsonl'
    f.write_text('\n'.join(json.dumps(x) for x in linhas), encoding='utf-8')
    t = time.time() - idade_dias * 86400
    os.utime(f, (t, t))
    return f


def _home(tmp_path: Path) -> Path:
    home = tmp_path / 'home'
    proj = home / '.claude' / 'projects' / 'C--trabalho-api'
    _sessao(proj, 'recente', [
        {'type': 'custom-title', 'customTitle': 'Pipeline de churn'},
        {'type': 'user', 'cwd': '/trabalho/api', 'timestamp': '2026-11-20T10:00:00Z',
         'message': {'role': 'user', 'content': f'Crie o modelo de churn com validação cruzada. token={CHAVE}'}},
        {'type': 'user', 'message': {'role': 'user', 'content': '<command-name>/clear</command-name>'}},
        {'type': 'user', 'isMeta': True, 'message': {'role': 'user', 'content': 'aviso interno do sistema'}},
        {'type': 'user', 'message': {'role': 'user', 'content': [{'type': 'tool_result', 'content': 'saída enorme'}]}},
        {'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'name': 'Bash', 'input': {'command': "cd x && pytest -q | tail -3"}},
            {'type': 'tool_use', 'name': 'Bash', 'input': {'command': "python - <<'EOF'\nimport segredo_do_codigo\nEOF"}},
            {'type': 'tool_use', 'name': 'Write', 'input': {'file_path': '/trabalho/api/modelo.py', 'content': 'CODIGO_DO_AGENTE = 1'}},
            {'type': 'tool_use', 'name': 'Edit', 'input': {'file_path': '/trabalho/api/infra/main.tf', 'old_string': 'a', 'new_string': 'b'}},
        ]}},
    ])
    _sessao(proj, 'antiga', [{'type': 'user', 'message': {'role': 'user', 'content': 'pedido de seis meses atrás'}}],
            idade_dias=200)
    mem = proj / 'memory'
    mem.mkdir()
    (mem / 'MEMORY.md').write_text('- [índice](x.md)', encoding='utf-8')
    (mem / 'perfil.md').write_text('---\nname: perfil\ndescription: cientista de dados\nmetadata:\n  type: user\n---\n'
                                   'Trabalha com modelos de churn em Python e Spark.', encoding='utf-8')
    (home / '.claude' / 'CLAUDE.md').write_text('@C:/pessoal/vault/contrato.md\nPrefiro testes antes do código.\n',
                                                encoding='utf-8')
    (home / '.claude' / 'history.jsonl').write_text(
        json.dumps({'display': 'rode a suíte e explique as falhas', 'project': '/trabalho/api'}), encoding='utf-8')
    return home


def test_sessoes_trazem_tarefas_ferramentas_e_comandos_sem_codigo(tmp_path):
    s = triage.sessoes_claude_code(_home(tmp_path))
    assert len(s) == 1  # a sessão de 200 dias fica de fora
    x = s[0]
    assert x['titulo'] == 'Pipeline de churn' and x['projeto'] == 'api' and x['data'] == '2026-11-20'
    assert x['prompts'] == ['Crie o modelo de churn com validação cruzada. token=[SEGREDO]']  # sem /clear, meta e tool_result
    assert x['comandos'] == {'pytest': 1, 'python': 1}  # sem cd, tail nem o corpo do heredoc
    assert x['areas_editadas'] == {'Python': 1, 'Terraform': 1}
    bruto = json.dumps(s)
    assert 'CODIGO_DO_AGENTE' not in bruto and 'segredo_do_codigo' not in bruto and CHAVE not in bruto


def test_memorias_e_instrucoes_do_agente(tmp_path):
    home = _home(tmp_path)
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'AGENTS.md').write_text('Stack: Python, dbt e Airflow.', encoding='utf-8')
    mems = triage.memorias_claude_code(home)
    assert [m['memoria'] for m in mems] == ['perfil · cientista de dados\nTrabalha com modelos de churn em Python e Spark.']
    inst = triage.instrucoes_do_agente(home, repo)
    assert [(i['origem'], i['arquivo']) for i in inst] == [('global', 'CLAUDE.md'), ('repositório', 'AGENTS.md')]
    assert '@C:/pessoal' not in inst[0]['texto'] and 'Prefiro testes' in inst[0]['texto']


def test_historico_completo_tem_todas_as_fontes(tmp_path):
    h = triage.shared_ai_history(home_dir=_home(tmp_path))
    assert h['sessoes_claude_code'][0]['prompt'] == 'rode a suíte e explique as falhas'
    assert len(h['sessoes_detalhadas_claude_code']) == 1 and len(h['memorias_claude_code']) == 1
    assert h['instrucoes_do_agente'][0]['arquivo'] == 'CLAUDE.md'


def test_segredos_saem_sempre():
    texto = (f'use {CHAVE} e AIza{"b" * 30} e ghp_{"c" * 30} e senha: hunter2 e '
             '-----BEGIN RSA PRIVATE KEY-----\nMIIE\n-----END RSA PRIVATE KEY-----')
    limpo = privacy.sem_segredos(texto)
    for s in (CHAVE, 'AIza', 'ghp_', 'hunter2', 'MIIE'):
        assert s not in limpo, s
    assert privacy.sem_segredos('rode pytest -q no módulo de churn') == 'rode pytest -q no módulo de churn'


def test_sem_pasta_do_claude_nada_quebra(tmp_path):
    h = triage.shared_ai_history(home_dir=tmp_path / 'vazio')
    assert h['sessoes_detalhadas_claude_code'] == [] and h['memorias_claude_code'] == [] and h['instrucoes_do_agente'] == []
