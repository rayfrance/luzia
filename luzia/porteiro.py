"""Porteiro dos hooks: decide se vale carregar o resto da Luzia, usando só `os`, `json` e `sys` (sem pathlib, sem banco).

O hook roda a cada edição e a cada atualização do rodapé. Em repositório não autorizado ele precisa sair em poucos
milissegundos, antes de qualquer import caro. Qualquer dúvida (arquivo ilegível, formato estranho) devolve "deixe o
caminho completo decidir": o porteiro só barra o que é certo, e quem trata erro e cópia de arquivo corrompido é o resto.
"""

from __future__ import annotations

import json
import os


def privado() -> str:
    """Pasta dos dados pessoais: LUZIA_PRIVATE; senão `private/` ao lado do código; senão `~/.luzia`."""
    env = os.environ.get('LUZIA_PRIVATE')
    if env:
        return env
    aqui = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'private')
    return aqui if os.path.isdir(aqui) else os.path.join(os.path.expanduser('~'), '.luzia')


def ler_config() -> dict | None:
    """`observer.json` como dicionário (padrão se não existe); None se estiver ilegível ou não for um objeto."""
    try:
        with open(os.path.join(privado(), 'observer.json'), 'rb') as f:
            dados = json.loads(f.read().decode('utf-8'))
    except FileNotFoundError:
        return {'modo': 'ativo', 'autorizados': []}
    except (OSError, ValueError):
        return None
    return dados if isinstance(dados, dict) else None


def autorizado(cwd, cfg: dict) -> bool:
    """O cwd é um repositório autorizado ou uma subpasta dele (nunca uma pasta irmã com o mesmo prefixo)."""
    if not isinstance(cwd, str) or not cwd:
        return False
    cwd_n = cwd.replace('\\', '/').rstrip('/').lower()
    for r in cfg.get('autorizados') or []:
        r_n = str(r).replace('\\', '/').rstrip('/').lower()
        if r_n and (cwd_n == r_n or cwd_n.startswith(r_n + '/')):
            return True
    return False


def barrar_hook(bruto: bytes) -> bool:
    """True só quando é certo que o hook do observador não tem nada a fazer (evento ilegível, ou cwd não autorizado)."""
    try:
        evento = json.loads(bruto.decode('utf-8', errors='replace'))
    except Exception:
        return True  # o observador também ignora, em silêncio, o que não é JSON
    if not isinstance(evento, dict):
        return True
    cfg = ler_config()
    if cfg is None:
        return False
    if not autorizado(evento.get('cwd', ''), cfg):
        return True
    # As mesmas saídas antecipadas do observador, sem importar o banco: fora de foco só a fila do painel (prompt) age,
    # e um Bash que não é `git commit` não tem o que reconhecer.
    nome = evento.get('hook_event_name')
    if nome == 'UserPromptSubmit':
        return False
    if cfg.get('modo', 'ativo') == 'sob_demanda':
        return True
    if nome == 'SessionStart':
        return False
    if evento.get('tool_name') == 'Bash':
        ti = evento.get('tool_input') or {}
        cmd = ti.get('command', '') if isinstance(ti, dict) else None
        return isinstance(cmd, str) and 'git commit' not in cmd
    return False


def barrar_statusline(bruto: bytes) -> str | None:
    """None: carregue o caminho completo. Texto (possivelmente vazio): é a linha final, sem importar mais nada."""
    try:
        cru = bruto.decode('utf-8', errors='replace')
        dados = json.loads(cru) if cru.strip() else {}
        cwd = str(((dados.get('workspace') or {}).get('current_dir') or dados.get('cwd') or ''))
    except Exception:
        return None
    cfg = ler_config()
    if cfg is None or 'modo' not in cfg:
        return None
    if cfg['modo'] == 'sob_demanda':
        return '✦ Luzia · fora de foco (/luzia:hoje)'
    if cwd and not autorizado(cwd, cfg):
        return ''
    return None
