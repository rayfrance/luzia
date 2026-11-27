"""Triagem: coleta local das fontes de carreira e do histórico compartilhado entre IAs.

Fontes autorizadas pela pessoa:
1. Declaração de nível atual, objetivo, horizonte e uso de IA;
2. Currículo (PDF ou texto) e LinkedIn exportado (PDF);
3. Perfil público do GitHub (campo `github` de private/entrada.json);
4. Histórico compartilhado entre as IAs utilizadas, só com o sim da pessoa: do Claude Code (`~/.claude`) os prompts
   recentes, as sessões recentes (título, projeto, trechos dos prompts, ferramentas, comandos e extensões editadas;
   nunca o código que o agente escreveu), as memórias e os CLAUDE.md (global e do repositório autorizado); do Codex
   (`~/.codex`) os títulos das sessões; e o vault da pessoa (campo `vault` de private/entrada.json). Segredos (chaves,
   tokens, senhas) saem sempre, antes de qualquer envio;
5. Metadados dos commits da própria pessoa no repositório local autorizado
   (repositório corporativo local). O código-fonte e o diff nunca são lidos para o modelo.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .privacy import sem_segredos

EXT_AREA = {
    '.cs': 'C#/.NET', '.cshtml': 'ASP.NET MVC/Razor', '.razor': 'Blazor',
    '.js': 'JavaScript', '.ts': 'TypeScript', '.tsx': 'React/TypeScript', '.jsx': 'React',
    '.html': 'HTML', '.css': 'CSS', '.scss': 'CSS/Sass', '.sql': 'SQL',
    '.py': 'Python', '.ipynb': 'Python/Jupyter', '.json': 'configuração JSON',
    '.xml': 'configuração XML', '.csproj': 'build .NET', '.config': 'configuração .NET',
    '.yml': 'CI/CD YAML', '.yaml': 'CI/CD YAML', '.md': 'documentação', '.tex': 'LaTeX',
    # dados, infraestrutura e segurança (o público não é só dev)
    '.r': 'R', '.go': 'Go', '.java': 'Java', '.kt': 'Kotlin', '.rs': 'Rust', '.scala': 'Scala', '.rb': 'Ruby',
    '.php': 'PHP', '.sh': 'Shell', '.ps1': 'PowerShell', '.tf': 'Terraform', '.hcl': 'Terraform/HCL',
    '.kql': 'KQL (detecção)', '.yara': 'YARA (detecção)', '.yar': 'YARA (detecção)', '.spl': 'Splunk SPL',
}


@dataclass
class CommitMeta:
    date: str
    subject: str
    files: int
    insertions: int
    deletions: int
    areas: list[str] = field(default_factory=list)


def read_pdf(data: bytes | Path | None) -> str:
    """Extrai o texto de um PDF ou arquivo texto."""
    if not data:
        return ''
    if isinstance(data, Path):
        if not data.exists():
            return ''
        if data.suffix.lower() in {'.txt', '.md'}:
            return data.read_text(encoding='utf-8', errors='replace').strip()
    from io import BytesIO

    try:
        from pypdf import PdfReader
    except ImportError:  # pypdf é opcional: sem ele, a triagem segue sem o currículo em PDF
        return ''
    try:
        stream = BytesIO(data) if isinstance(data, bytes) else open(data, 'rb')
        with stream:
            reader = PdfReader(stream)
            return '\n'.join((page.extract_text() or '') for page in reader.pages).strip()
    except Exception:  # PDF ilegível ou protegido: segue sem ele
        return ''


def github_profile(username: str, timeout: float = 8.0) -> dict:
    """Perfil público e linguagens dos repositórios recentes, pela API pública."""
    if not username:
        return {}

    def get(url: str):
        req = urllib.request.Request(url, headers={'User-Agent': 'luzia-plugin'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))

    user = get(f'https://api.github.com/users/{username}')
    repos = get(f'https://api.github.com/users/{username}/repos?sort=updated&per_page=15')
    langs = Counter(r['language'] for r in repos if r.get('language'))
    return {
        'usuario': username,
        'bio': user.get('bio') or '',
        'repos_publicos': user.get('public_repos', 0),
        'desde': (user.get('created_at') or '')[:4],
        'linguagens_recentes': dict(langs.most_common(6)),
        'repos_recentes': [
            {
                'nome': r.get('name') or '',
                'descricao': r.get('description') or '',
                'linguagem': r.get('language') or '',
            }
            for r in repos[:8]
        ],
    }


# Limites do histórico do Claude Code na triagem: o bastante para um retrato fiel, sem estourar o envio.
SESSOES_MAX = 25           # sessões mais recentes
SESSOES_DIAS = 120         # só sessões dos últimos 120 dias
PROMPTS_POR_SESSAO = 4     # trechos de prompt por sessão
TRECHO = 240               # caracteres por trecho de prompt
MEMORIAS_MAX = 40          # arquivos de memória
MEMORIA_TRECHO = 700       # caracteres por memória
CLAUDE_MD_TRECHO = 2500    # caracteres por CLAUDE.md / AGENTS.md
HISTORICO_PROMPTS = 40     # prompts recentes de ~/.claude/history.jsonl
SEM_INTERESSE = {  # navegação, laços do shell e utilitários de texto: não dizem nada sobre o trabalho
    'cd', 'echo', 'ls', 'dir', 'cat', 'type', 'pwd', 'true', 'false', 'set', 'export', 'sleep', 'head', 'tail', 'grep',
    'sed', 'awk', 'cut', 'sort', 'uniq', 'wc', 'tr', 'tee', 'xargs', 'find', 'mkdir', 'rm', 'cp', 'mv', 'touch',
    'for', 'while', 'do', 'done', 'if', 'then', 'else', 'fi', 'in', 'source', 'test', 'printf', 'read', 'until',
    'select-object', 'where-object', 'foreach-object', 'select-string', 'get-childitem', 'get-content', 'set-content',
    'out-file', 'write-output', 'write-host', 'set-location', 'test-path', 'new-item', 'remove-item', 'cygpath',
    'foreach', 'try', 'catch', 'date', 'timeout', 'file', 'env', 'time', 'nohup', 'sudo', 'exit', 'return'}


def _texto_usuario(msg) -> str:
    """O texto que a pessoa digitou numa mensagem do Claude Code (sem resultados de ferramenta)."""
    if not isinstance(msg, dict):
        return ''
    c = msg.get('content')
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return ' '.join(b.get('text', '') for b in c if isinstance(b, dict) and b.get('type') == 'text')
    return ''


def _comandos(cmd: str) -> list[str]:
    """Os programas que um comando de terminal chama ("cd x && pytest -q" → pytest), sem argumentos."""
    nomes = []
    # só a primeira linha: o resto costuma ser o corpo de um heredoc (código), não comandos
    for linha in (cmd or '').splitlines()[:1]:
        # só o primeiro programa de cada etapa ("a && b; c"); o que vem depois de um pipe é utilitário de texto
        for parte in re.split(r'&&|\|\||;', linha):
            parte = parte.split('|')[0]
            tokens = [t for t in parte.strip().split() if not re.match(r'^[A-Za-z_]+=', t)]
            if tokens:
                nome = Path(tokens[0].strip('"\'()')).name.lower()
                if nome and nome not in SEM_INTERESSE and re.match(r'^[a-z][a-z0-9._+-]{1,29}$', nome):
                    nomes.append(nome)
    return nomes


def sessoes_claude_code(home: Path, agora: float | None = None) -> list[dict]:
    """As sessões recentes do Claude Code (~/.claude/projects/*/*.jsonl): o que a pessoa pediu e como o agente
    trabalhou, sem o código. Por sessão: data, projeto, título, até PROMPTS_POR_SESSAO trechos de prompt, as
    ferramentas, os comandos de terminal e as extensões dos arquivos editados."""
    agora = agora or time.time()
    arquivos = [f for f in (home / '.claude' / 'projects').glob('*/*.jsonl')
                if agora - f.stat().st_mtime <= SESSOES_DIAS * 86400]
    saida = []
    for f in sorted(arquivos, key=lambda x: x.stat().st_mtime, reverse=True)[:SESSOES_MAX]:
        titulo = projeto = data = ''
        prompts: list[str] = []
        ferramentas, comandos, exts = Counter(), Counter(), Counter()
        try:
            linhas = f.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError:
            continue
        for linha in linhas:
            try:
                d = json.loads(linha)
            except Exception:
                continue
            if not isinstance(d, dict):
                continue
            tipo = d.get('type')
            if tipo == 'custom-title' and d.get('customTitle'):
                titulo = str(d['customTitle'])[:120]
            if not projeto and d.get('cwd'):
                projeto = Path(str(d['cwd'])).name
            if not data and d.get('timestamp'):
                data = str(d['timestamp'])[:10]
            if tipo == 'user' and not d.get('isMeta') and not d.get('isSidechain') and len(prompts) < PROMPTS_POR_SESSAO:
                texto = ' '.join(_texto_usuario(d.get('message')).split())
                if len(texto) > 8 and not texto.startswith('<'):  # comandos e avisos do sistema começam com "<"
                    prompts.append(sem_segredos(texto)[:TRECHO])
            if tipo == 'assistant':
                conteudo = (d.get('message') or {}).get('content') if isinstance(d.get('message'), dict) else None
                for b in conteudo if isinstance(conteudo, list) else []:
                    if not isinstance(b, dict) or b.get('type') != 'tool_use':
                        continue
                    nome = str(b.get('name') or '')
                    ferramentas[nome] += 1
                    entrada = b.get('input') if isinstance(b.get('input'), dict) else {}
                    if nome in ('Bash', 'PowerShell'):
                        comandos.update(_comandos(str(entrada.get('command') or '')))
                    caminho = entrada.get('file_path') or entrada.get('notebook_path')
                    if caminho and nome in ('Edit', 'Write', 'MultiEdit', 'NotebookEdit'):
                        ext = Path(str(caminho)).suffix.lower()
                        if ext:
                            exts[EXT_AREA.get(ext, ext)] += 1
        if prompts or ferramentas:
            saida.append({'data': data, 'projeto': projeto, 'titulo': sem_segredos(titulo), 'prompts': prompts,
                          'ferramentas': dict(ferramentas.most_common(8)), 'comandos': dict(comandos.most_common(10)),
                          'areas_editadas': dict(exts.most_common(8))})
    return saida


def _sem_frontmatter(texto: str) -> str:
    if texto.startswith('---'):
        partes = texto.split('---', 2)
        if len(partes) == 3:
            nome = re.search(r'(?m)^name:\s*(.+)$', partes[1])
            desc = re.search(r'(?m)^description:\s*(.+)$', partes[1])
            cab = ' · '.join(x.group(1).strip() for x in (nome, desc) if x)
            return (cab + '\n' if cab else '') + partes[2].strip()
    return texto.strip()


def memorias_claude_code(home: Path) -> list[dict]:
    """As memórias do Claude Code (~/.claude/projects/*/memory/*.md, sem o índice MEMORY.md): o que a pessoa
    pediu para o agente lembrar sobre ela, o trabalho e os projetos."""
    saida = []
    arquivos = sorted((home / '.claude' / 'projects').glob('*/memory/*.md'), key=lambda x: x.stat().st_mtime, reverse=True)
    for md in [a for a in arquivos if a.name.upper() != 'MEMORY.MD'][:MEMORIAS_MAX]:
        try:
            texto = _sem_frontmatter(md.read_text(encoding='utf-8', errors='replace'))
        except OSError:
            continue
        if texto:
            saida.append({'projeto': md.parent.parent.name[-40:], 'memoria': sem_segredos(texto)[:MEMORIA_TRECHO]})
    return saida


def instrucoes_do_agente(home: Path, repo_dir: Path | None = None) -> list[dict]:
    """CLAUDE.md global e CLAUDE.md / AGENTS.md do repositório autorizado: como a pessoa configura o agente (stack,
    práticas, regras). Linhas de import (`@caminho`) ficam de fora: apontam para arquivos pessoais."""
    candidatos = [('global', home / '.claude' / 'CLAUDE.md')]
    if repo_dir:
        candidatos += [('repositório', Path(repo_dir) / nome) for nome in ('CLAUDE.md', 'AGENTS.md')]
    saida = []
    for origem, arq in candidatos:
        if not arq.is_file():
            continue
        try:
            linhas = arq.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError:
            continue
        texto = '\n'.join(l for l in linhas if not l.strip().startswith('@')).strip()
        if texto:
            saida.append({'origem': origem, 'arquivo': arq.name, 'texto': sem_segredos(texto)[:CLAUDE_MD_TRECHO]})
    return saida


def shared_ai_history(
    vault_dir: Path | None = None,
    home_dir: Path | None = None,
    repo_dir: Path | None = None,
) -> dict:
    """Lê o histórico compartilhado entre Claude Code, Codex e o vault de impressões (Gemini/Obsidian).

    Preserva a separação do contrato do ecossistema: distingue notas autorais da pessoa
    de blocos de revisão assistida por IA (`<!-- revisao-ia:inicio -->`).
    """
    home = home_dir or Path.home()
    out: dict = {
        'notas_autorais_vault': [],
        'sessoes_claude_code': [],
        'sessoes_codex': [],
        'plugins_agentes_ativos': [],
        'sessoes_detalhadas_claude_code': [],
        'memorias_claude_code': [],
        'instrucoes_do_agente': [],
    }

    # 1. Vault compartilhado da pessoa (só se `vault` estiver em private/entrada.json)
    frentes = Path(vault_dir) / '01-frentes' if vault_dir else None
    if frentes and frentes.exists():
        for md in sorted(frentes.rglob('*.md')):
            raw = md.read_text(encoding='utf-8', errors='replace')
            # Remove o bloco de revisão automática da IA para ficar só com a impressão/registro da autora
            autoral = raw.split('<!-- revisao-ia:inicio -->')[0].strip()
            if autoral:
                out['notas_autorais_vault'].append({
                    'frente': md.parent.name,
                    'arquivo': md.name,
                    'conteudo_autoral': sem_segredos(autoral)[:1800],
                })

    # 2. Histórico recente do Claude Code (~/.claude/history.jsonl)
    claude_hist = home / '.claude' / 'history.jsonl'
    if claude_hist.exists():
        entries = []
        for line in claude_hist.read_text(encoding='utf-8', errors='replace').splitlines()[-(HISTORICO_PROMPTS * 2):]:
            try:
                d = json.loads(line)
                disp = (d.get('display') or '').strip()
                proj = Path(d.get('project') or '').name
                if disp and len(disp) > 5:
                    entries.append({'projeto': proj, 'prompt': sem_segredos(disp)[:TRECHO]})
            except Exception:
                continue
        out['sessoes_claude_code'] = entries[-HISTORICO_PROMPTS:]

    # 2b. Sessões recentes, memórias e CLAUDE.md: o retrato do trabalho real com o agente
    for chave, ler in (('sessoes_detalhadas_claude_code', lambda: sessoes_claude_code(home)),
                       ('memorias_claude_code', lambda: memorias_claude_code(home)),
                       ('instrucoes_do_agente', lambda: instrucoes_do_agente(home, repo_dir))):
        try:
            out[chave] = ler()
        except Exception:  # uma fonte ilegível não derruba a triagem
            out[chave] = []

    # 3. Plugins instalados no Claude Code (~/.claude/plugins/installed_plugins.json)
    plugins_file = home / '.claude' / 'plugins' / 'installed_plugins.json'
    if plugins_file.exists():
        try:
            pdata = json.loads(plugins_file.read_text(encoding='utf-8'))
            out['plugins_agentes_ativos'] = list((pdata.get('plugins') or {}).keys())
        except Exception:
            pass

    # 4. Histórico de sessões interativas do Codex (~/.codex/session_index.jsonl)
    codex_idx = home / '.codex' / 'session_index.jsonl'
    if codex_idx.exists():
        codex_threads = []
        for line in codex_idx.read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                d = json.loads(line)
                t = (d.get('thread_name') or '').strip()
                if t and not any(w in t for w in ('Watcher', 'Guardian', 'New voice chat')):
                    codex_threads.append({
                        'data': (d.get('updated_at') or '')[:10],
                        'tarefa': t[:120],
                    })
            except Exception:
                continue
        out['sessoes_codex'] = codex_threads[-18:]

    return out


def repo_authors(repo: Path, excluir: list[str] | tuple[str, ...] = ()) -> list[str]:
    """Nomes dos demais autores do repositório, para mascarar colegas. `excluir`: identidades da própria pessoa
    (nome ou e-mail); ela e as palavras do nome dela nunca entram na lista."""
    from .entregas import casa_identidade
    minhas = [i for i in excluir if i and '@' not in i]
    tokens = {t.casefold() for i in minhas for t in [i, *i.split()]}
    out = subprocess.run(
        ['git', '-C', str(repo), 'log', '--all', '--format=%an'],
        capture_output=True, text=True, encoding='utf-8', errors='replace', check=True,
    ).stdout
    names = set()
    for name in out.splitlines():
        name = name.strip()
        if name and not any(casa_identidade(i, name, '') for i in minhas):
            names.add(name)
            names.update(p for p in name.split() if len(p) >= 4 and p.casefold() not in tokens)
    return sorted(names)


def my_commits(repo: Path, author: str, limit: int = 40) -> list[CommitMeta]:
    """Metadados dos commits da pessoa (sem merges, sem diff)."""
    out = subprocess.run(
        ['git', '-C', str(repo), 'log', '--all', '--no-merges', f'--author={author}',
         f'-{limit}', '--date=short', '--numstat', '--format=@@%ad|%s'],
        capture_output=True, text=True, encoding='utf-8', errors='replace', check=True,
    ).stdout
    commits: list[CommitMeta] = []
    cur: CommitMeta | None = None
    areas: Counter = Counter()
    for line in out.splitlines():
        if line.startswith('@@'):
            if cur:
                cur.areas = [a for a, _ in areas.most_common(4)]
                commits.append(cur)
            date, _, subject = line[2:].partition('|')
            cur, areas = CommitMeta(date, subject, 0, 0, 0), Counter()
        elif line.strip() and cur:
            parts = line.split('\t')
            if len(parts) != 3:
                continue
            ins, dels, path = parts
            cur.files += 1
            cur.insertions += int(ins) if ins.isdigit() else 0
            cur.deletions += int(dels) if dels.isdigit() else 0
            ext = Path(path).suffix.lower()
            areas[EXT_AREA.get(ext, ext or 'outro')] += 1
    if cur:
        cur.areas = [a for a, _ in areas.most_common(4)]
        commits.append(cur)
    return [c for c in commits if not c.subject.startswith(('index on', 'WIP on'))]
