"""Observador de foco da Luzia: hooks do Claude Code (PostToolUse, UserPromptSubmit e SessionStart).

Roda localmente, sem chamar o modelo, só nos repositórios autorizados (`private/observer.json`).

- PostToolUse (edição de arquivo ou `git commit`): se o conceito de uma centelha aparece no que o agente escreveu, ela
  acende como **luz refletida** (sem centelha que case, nasce uma do chat). Em foco (`ativo`), a Luzia oferece convertê-la.
- UserPromptSubmit: se o conceito aparece no **seu prompt** (você dirigiu), a centelha vira **luz própria**.
  Também oferece as centelhas que você mandou do painel (fila).
- Cada centelha muda de luz uma vez só: sem teto nem limite de captação (regras em docs/luzia-ux.md).
- Grava só o evento mascarado (horário, prisma, extensão, origem). Nunca o caminho, o código ou o texto do prompt.
- Tudo vai para o banco (`lumen`, `sessao_evento`, `lampejo`) por `banco.gravar_ou_pendurar`, com espera curta: se o banco
  estiver ocupado, o evento fica em `pendentes.jsonl` e a próxima escrita o absorve. O hook nunca levanta nem trava a sessão.
- SessionStart: se há algo a retomar (centelha convertendo, luz para converter, fila), uma linha no fim da 1ª resposta.
- Modos do foco: `ativo` (em foco, com lampejos), `passivo` (em foco, em silêncio), `sob_demanda` (fora de foco).
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
if 'luzia' not in sys.modules:  # checkout de desenvolvimento; pelo lz.py o pacote já foi carregado
    sys.path.insert(0, str(HERE.parent))

from luzia import acoes, arquivos, banco, jogo, porteiro, prismas, trajetoria  # noqa: E402

PRIVATE = arquivos.PRIVATE
CFG = PRIVATE / 'observer.json'
CLI = arquivos.CLI

AGENTES = ('claude-code', 'codex', 'cursor', 'antigravity', 'outro')
NOMES_FOCO = {
    'ativo': 'em foco',
    'passivo': 'em silêncio',
    'sob_demanda': 'fora de foco',
}

# Nomes compostos antigos (a migração e os prismas ainda não divididos usam) + as habilidades isoladas.
PALAVRAS_PADRAO = {
    'Domain-Driven Design (DDD)': ['Domain', 'Aggregate', 'ValueObject', 'Value Object', 'Entity', 'Repository', 'BoundedContext',
                                   'DomainEvent', 'agregado', 'objeto de valor', 'entidade', 'subdomínio', 'contexto delimitado', 'DDD'],
    'Arquitetura .NET / Clean Architecture': ['Interface', 'UseCase', 'Application', 'Infrastructure', 'DependencyInjection',
                                              'IServiceCollection', 'camada', 'injeção de dependência', 'desacopl', 'clean architecture'],
    'Testes e Qualidade / SQL': ['Test', 'xunit', 'Assert', 'Mock', 'Fact', 'teste', 'cobertura', 'SELECT', 'JOIN', 'índice'],
    'Back-end C# / .NET e Integrações': ['HttpClient', 'Controller', 'Integration', 'async Task', 'integração', 'endpoint', 'retry'],
    'Front-end (JS / Razor / React)': ['.cshtml', 'useState', 'fetch(', 'jQuery', 'componente', 'modal', 'razor'],
    'Programação Agêntica e Fluxo com IA': ['CLAUDE.md', 'AGENTS.md', '.claude', 'subagente', 'hook', 'skill', 'plan mode'],
    **prismas.PALAVRAS_PARTE,
}


def read_json(path: Path, default):
    return arquivos.ler_json(path, default)


def config() -> dict:
    return read_json(CFG, {'modo': 'ativo', 'autorizados': [], 'agente': 'claude-code'})


def definir_modo(modo: str) -> dict:
    cfg = config()
    cfg['modo'] = modo
    arquivos.gravar_json(CFG, cfg)
    return cfg




def plano() -> dict:
    return trajetoria.plano(banco.ESPERA_CURTA_MS)


def lacunas(plan: dict) -> dict[str, dict]:
    """Prismas ativos com as palavras do banco + do plano + padrão, o pct próprio e as centelhas com as palavras delas."""
    with trajetoria.abrir(banco.ESPERA_CURTA_MS) as con:
        t = jogo.luz(plan, con)
        do_banco = {p['nome']: p['palavras'] for p in trajetoria.prismas(con)}
        centelhas = jogo.para_casar(con)
    out = {}
    for p in t['prismas']:
        nome = p['nome']
        s = next((x for x in plan.get('skills', []) if x['nome'] == nome), {})
        palavras = (do_banco.get(nome) or []) + (s.get('palavras_chave') or []) + PALAVRAS_PADRAO.get(nome, [])
        out[nome] = {'palavras': list(dict.fromkeys(str(w) for w in palavras if w)), 'pct': p['pct'],
                     'centelhas': centelhas.get(nome, [])}
    return out or {k: {'palavras': p, 'pct': 0, 'centelhas': []} for k, p in PALAVRAS_PADRAO.items()
                   if not prismas.composto(k)}  # sem trajetória: só habilidades isoladas


_PARTES = re.compile(r'[A-ZÀ-Ý]+(?![a-zà-ÿ])|[A-ZÀ-Ý]?[a-zà-ÿ0-9]+')


def _padrao(palavra: str) -> str:
    """Termos compostos casam com ou sem separador: 'ValueObject' ~ 'value object' ~ 'value-object'."""
    if re.fullmatch(r'[\wÀ-ÿ ]+', palavra):
        partes = _PARTES.findall(palavra.replace('_', ' '))
        if len(partes) > 1:
            return r'[\s_-]?'.join(re.escape(x) for x in partes)
    return re.escape(palavra)


def _casa(texto: str, palavra: str) -> bool:
    """Palavra inteira (não casa 'Test' em 'TestHelper'); um radical que não é palavra ('desacopl') casa como prefixo."""
    if not palavra or len(palavra) < 3:
        return False
    fim = '' if palavra in RADICAIS or not palavra[-1].isalnum() else r'(?![A-Za-zÀ-ÿ0-9_])'
    return bool(re.search(r'(?<![A-Za-zÀ-ÿ0-9_])' + _padrao(palavra) + fim, texto, re.IGNORECASE))


# Radicais das listas padrão: casam como prefixo de propósito.
RADICAIS = {'desacopl'}
# Termos genéricos demais para fazer nascer uma centelha do chat sozinhos (ainda ajudam a casar centelhas existentes).
GENERICOS = {w.lower() for w in ('Domain', 'Interface', 'Application', 'Test', 'Assert', 'Fact', 'teste', 'SELECT', 'JOIN',
                                  'Controller', 'endpoint', 'componente', 'modal', 'camada', 'hook', 'skill', 'fetch(',
                                  '.cshtml', '.claude', 'Integration', 'integração', 'Entity', 'Repository', 'Mock')}
# Sintaxe e rotina que todo código e toda sessão têm: nunca fazem nascer uma centelha do chat (teste com testadores, 24/11).
GENERICOS |= {'def', 'class', 'import', 'from', 'return', 'function', 'const', 'let', 'var', 'self', 'this', 'async',
              'await', 'print', 'pass', 'public', 'private', 'static', 'void', 'new', 'null', 'none', 'true', 'false',
              'commit', 'push', 'pull', 'git', 'feat', 'fix', 'docs', 'chore', 'código', 'code', 'arquivo', 'file'}
# Palavras de toda conversa com um agente (e prefixos de commit): nunca casam nem fazem nascer centelha, mesmo quando o
# modelo as pôs nas palavras de um prisma (ex.: "Agente" em Programação Agêntica dava +36 lm a qualquer prompt; 24/11).
COMUNS = {'agente', 'agentes', 'agent', 'agents', 'agêntico', 'agêntica', 'prompt', 'prompts', 'ia', 'ai', 'llm', 'claude',
          'codex', 'gemini', 'modelo', 'model', 'contexto', 'context', 'critério', 'critérios', 'princípio', 'princípios',
          'pacote', 'package', 'tarefa', 'task', 'pedido', 'resposta', 'pergunta', 'refactor', 'test', 'tests', 'style',
          'perf', 'build', 'ci', 'revert', 'wip'}
GENERICOS |= COMUNS


def detectar(texto: str, gaps: dict) -> list[str]:
    achadas = []
    for skill, info in gaps.items():
        for w in info['palavras']:
            if w and len(w) >= 3 and re.search(r'(?<![A-Za-z])' + re.escape(w), texto, re.IGNORECASE):
                achadas.append(skill)
                break
    return achadas


def authorized(cwd, cfg: dict) -> bool:
    """O cwd é um repositório autorizado ou uma subpasta dele (nunca uma pasta irmã com o mesmo prefixo)."""
    return porteiro.autorizado(cwd, cfg)




def sessao_id(event: dict) -> str:
    return hashlib.sha256(event.get('session_id', '').encode()).hexdigest()[:8]


# ------------------------------------------------------------------ foco sem hooks (comando `foco` da CLI)
LIMITE_DIFF = 200_000


def sessao_do_foco(cwd: str, sessao: str = '') -> str:
    """Id da sessão do `foco`: o informado, ou um id diário por pasta (um reconhecimento por prisma por dia e pasta)."""
    bruto = sessao or f"foco|{cwd.replace(chr(92), '/').lower()}|{date.today().isoformat()}"
    return sessao_id({'session_id': bruto})


def _git(cwd: str, *args: str):
    import subprocess  # import tardio: só o comando `foco` chama o git; o hook não paga por isso

    return subprocess.run(['git', '-C', cwd, *args], capture_output=True, timeout=20, encoding='utf-8', errors='replace')


def adicionado_nos_arquivos(caminhos: list[str], cwd: str) -> str:
    """Só as linhas **acrescentadas** pelo `git diff` dos caminhos (contra o HEAD; arquivo novo conta inteiro) + os nomes.

    O código é lido em memória e nunca gravado. Levanta RuntimeError com a mensagem para a pessoa se não for um repositório git.
    """
    import subprocess

    try:
        dentro = _git(cwd, 'rev-parse', '--is-inside-work-tree')
    except (OSError, subprocess.SubprocessError) as e:
        raise RuntimeError(f'não consegui rodar o git ({type(e).__name__})') from e
    if dentro.returncode != 0:
        raise RuntimeError('esta pasta não é um repositório git: o foco lê as mudanças pelo git diff')
    partes = [_git(cwd, 'diff', 'HEAD', '--unified=0', '--no-color', '--', *caminhos).stdout
              or _git(cwd, 'diff', '--unified=0', '--no-color', '--', *caminhos).stdout]  # repositório sem commits: só o diff do índice
    novos = [c for c in _git(cwd, 'ls-files', '--others', '--exclude-standard', '--', *caminhos).stdout.splitlines() if c]
    for novo in novos:  # arquivo ainda fora do git: o diff contra o vazio é o arquivo todo
        partes.append(_git(cwd, 'diff', '--no-index', '--unified=0', '--no-color', '--', os.devnull, novo).stdout)
    linhas = [l[1:] for texto in partes for l in texto.splitlines() if l.startswith('+') and not l.startswith('+++')]
    nomes = [Path(c).name for c in caminhos]
    return ' '.join(nomes + linhas)[:LIMITE_DIFF]


def situacao_do_foco(cwd: str) -> tuple[str, str]:
    """('ok' | 'fora_de_foco' | 'nao_autorizado', modo): confira antes de ler qualquer código ou prompt."""
    cfg = config()
    modo = cfg.get('modo', 'ativo')
    if not authorized(cwd, cfg):
        return 'nao_autorizado', modo
    return ('fora_de_foco' if modo == 'sob_demanda' else 'ok'), modo


def foco(origem: str, texto: str, cwd: str, sessao: str = '', ext: str = '') -> dict:
    """O mesmo reconhecimento dos hooks para agentes sem hooks (Antigravity, Codex, Cursor).

    `origem`: 'prompt' (texto do pedido da pessoa) ou 'agente' (o que o agente escreveu). Nada do texto é gravado.
    Devolve `situacao`, `modo`, `achados` (de `reconhecer_em`) e `gaps`.
    """
    situacao, modo = situacao_do_foco(cwd)
    if situacao != 'ok':
        return {'situacao': situacao, 'modo': modo, 'achados': [], 'gaps': {}}
    gaps = lacunas(plano())
    achados = reconhecer_em(texto, origem, sessao_do_foco(cwd, sessao), modo, 'prompt' if origem == 'prompt' else ext or 'arquivo',
                            'foco', gaps)
    return {'situacao': 'ok', 'modo': modo, 'achados': achados, 'gaps': gaps}


def saida(evento: str, contexto: str) -> None:
    print(json.dumps({'hookSpecificOutput': {'hookEventName': evento, 'additionalContext': contexto}}, ensure_ascii=True))


def sem_quebrar(funcao):
    """O observador nunca atrapalha a sessão: erro do banco ou de qualquer parte vira linha no erros.log (só o tipo)."""
    @functools.wraps(funcao)
    def protegida(*args, **kwargs):
        try:
            return funcao(*args, **kwargs)
        except Exception as e:
            arquivos.registrar_erro(f'observer {funcao.__name__}', e)
    return protegida


RUBRICA_LAMPEJO = ('rubrica 0-4 (0 não explicou, 1 descreveu o código, 2 explicou o porquê, 3 comparou com alternativa, '
                   '4 ligou ao conceito e aos trade-offs)')


def _onde(chave: str, ext: str) -> str:
    """Onde a luz apareceu, sem caminho nem código: o dia, a hora e, no código do agente, só a extensão."""
    agora_ = datetime.now()
    base = f'chat de {agora_:%d/%m}, {agora_:%H:%M}'
    return base + (f' · {ext}' if chave == 'agente' and ext and ext not in ('prompt', 'arquivo', 'foco') else '')


def _id_chat(prisma: str, termo: str) -> str:
    """Id da centelha do chat: 8 hex (as da meta têm 4), para dois conceitos nunca caírem na mesma centelha."""
    return hashlib.sha1(f'chat|{prisma}|{termo.lower()}'.encode('utf-8')).hexdigest()[:8]


def _nova(prisma: str, termo: str, chave: str, prog: dict) -> dict:
    """Centelha que nasce do chat quando nenhuma da meta casa com o conceito (o título traz o termo, nunca o texto)."""
    porque = (f'Você pediu ao agente falando em "{termo}". Quem dirigiu o conceito foi você, então a luz já veio própria.'
              if chave == 'prompt' else
              f'O agente aplicou {termo} na sua sessão. Explicar por que ele fez assim converte essa luz.')
    titulo = f'{termo} no seu pedido ao agente' if chave == 'prompt' else f'Por que o agente usou {termo}'
    f = {'titulo': titulo, 'tipo': 'explicar', 'duracao_min': 5, 'skill_plano': prisma}
    lm, conta = jogo.valor(f, {}, prog)
    return {'titulo': titulo, 'tipo': 'explicar', 'duracao_min': 5, 'valor_lm': lm, 'conta': conta,
            'conteudo': {'skill': prisma, 'palavras': [termo], 'conceitos': [termo], 'titulo_curto': termo,
                         'porque': porque, 'por_que': porque}}


def reconhecer_em(texto: str, origem: str, sid: str, modo: str, ext: str, ferramenta: str, gaps: dict) -> list[dict]:
    """O reconhecimento do foco, uma só implementação (hooks e comando `foco`).

    `origem` é 'prompt' (a pessoa dirigiu o conceito: a centelha vira luz própria) ou 'agente' (o agente aplicou: a
    centelha apagada vira luz refletida). O texto casa com as palavras das centelhas de cada prisma; sem nenhuma que
    case, o primeiro termo do prisma que aparece cria uma centelha do chat (uma por prisma por evento). Nada do texto
    é gravado. Devolve o que aconteceu por centelha: `skill`, `centelha`, `titulo`, `estado`, `lm`, `luz`, `novo`,
    `mudou` e `provisorio` (True se o banco estava ocupado e o resultado não foi confirmado).
    """
    chave = 'prompt' if origem == 'prompt' else 'agente'
    onde = _onde(chave, ext)
    prog = {n: {'pct': i.get('pct', 0)} for n, i in gaps.items()}
    achados = []
    # o nome de um prisma (de qualquer prisma da trajetória) sozinho não é um conceito: "o que é DDD?" não acende nada
    nomes = {n for p in gaps for n in (p.lower(), prismas.nome_curto(p).lower())}
    nomes |= {w for p in gaps for w in re.findall(r'[a-zà-ÿ0-9#+]+', p.lower()) if len(w) >= 4}  # "qualidade" sozinha
    nomes |= COMUNS  # "agente", "prompt", "contexto"...: de toda conversa, não provam conceito nenhum
    for prisma, info in gaps.items():
        acertos = [c for c in info.get('centelhas', [])
                   if any(_casa(texto, w) for w in c['palavras'] if w.lower() not in nomes)]
        if acertos and all(c['estado'] == 'descartada' for c in acertos):
            continue  # a pessoa descartou este conceito: a Luzia respeita
        vivos = [c for c in acertos if c['estado'] != 'descartada']
        if chave == 'agente':  # acende a apagada que mais vale; sem apagada, só registra a evidência da primeira
            vivos.sort(key=lambda c: (c['estado'] != 'apagada', -int(c.get('lm') or 0)))
        else:  # o prompt só faz nascer ou acender centelhas do chat; as da meta passam pela conversa e pela rubrica
            vivos = [c for c in vivos if c.get('origem') == 'chat'] if vivos else []
            if acertos and not vivos:
                continue
        alvo = (vivos[0]['id'], vivos[0].get('titulo'), None, vivos[0].get('lm')) if vivos else None
        if alvo is None:
            termo = next((w for w in info.get('palavras', []) if w.lower() not in GENERICOS and w.lower() not in nomes
                          and _casa(texto, w)), None)
            if termo is None:
                continue
            nova = _nova(prisma, termo, chave, prog)
            alvo = (_id_chat(prisma, termo), termo, nova, nova['valor_lm'])
        cid, titulo, nova, lm = alvo
        estado: dict = {}
        r = jogo.reconhecer(sid, chave, prisma, cid, nova, onde, ext, ferramenta, modo,
                            interveio=modo == 'ativo', estado=estado)
        if r:
            if estado.get('provisorio'):
                r = {**r, 'lm': int(lm or 0)}
            achados.append({'skill': prisma, 'titulo': titulo, **r, 'provisorio': bool(estado.get('provisorio'))})
    return achados


def cartao_refletida(skill: str, titulo: str, centelha: str, lm: int, provisorio: bool = False) -> str:
    curto = prismas.nome_curto(skill)
    if provisorio:  # banco ocupado: o resultado ainda não foi confirmado, então não convida a converter
        return (f'[Luzia · em foco · luz refletida] O código que você (agente) acabou de escrever aplica "{titulo}" ({skill}). '
                'A centelha acendeu como luz REFLETIDA para a pessoa, a confirmar (o banco estava ocupado). Termine a tarefa '
                f'normalmente e, no FIM, em UMA linha, sem perguntas: "✦ Centelha da sessão · {curto} · {titulo} · refletida (a confirmar)"')
    return (
        f'[Luzia · em foco · luz refletida] O código que você (agente) acabou de escrever aplica "{titulo}" ({skill}). Quem aplicou foi '
        f'o agente, então a centelha #{centelha} acendeu como luz REFLETIDA ({lm} lm para converter). Termine a tarefa normalmente. '
        'Só no FIM da resposta, mostre em no máximo 3 linhas:\n'
        f'✦ Centelha da sessão · {curto} · {titulo} · {lm} lm para converter\n'
        '<1 linha: onde o conceito aparece concretamente nesta mudança>\n'
        '▸ Converter: você explica por que o agente fez assim, e a luz vira sua.\n'
        'Depois, use AskUserQuestion com "Converter agora" e "Depois". Converter agora: rode '
        f'`{CLI} fazer {centelha} --onde aqui` e siga o roteiro. Depois: nada a fazer (a centelha fica para converter).'
    )


@sem_quebrar
def ao_enviar_prompt(event: dict, cfg: dict) -> None:
    """UserPromptSubmit: luz própria quando você dirige o conceito; e a fila do painel."""
    sid, modo = sessao_id(event), cfg.get('modo', 'ativo')
    partes = []
    if modo != 'sob_demanda':
        gaps = lacunas(plano())
        for r in reconhecer_em(event.get('prompt', ''), 'prompt', sid, modo, 'prompt', 'prompt', gaps):
            if modo == 'ativo' and r['mudou'] and not r['provisorio']:
                partes.append(f'[Luzia · em foco · luz própria] A pessoa DIRIGIU "{r["titulo"]}" ({r["skill"]}) neste pedido: a centelha '
                              f'#{r["centelha"]} virou luz própria (+{r["lm"]} lm). Responda normalmente e, no FIM, em UMA linha: '
                              f'"✦ Luzia · {prismas.nome_curto(r["skill"])}: você dirigiu {r["titulo"]} · +{r["lm"]} lm de luz própria"')
    try:  # espera curta: o hook não pode travar a sessão; sem a fila, o resto do aviso sai igual
        pend = [f for f in acoes.fila(banco.ESPERA_CURTA_MS) if sid not in f.get('oferecida_em', [])]
    except Exception as e:
        arquivos.registrar_erro('observer fila', e)
        pend = []
    if pend:
        item = pend[0]
        try:
            acoes.marcar_oferecida(item['id'], sid, banco.ESPERA_CURTA_MS)
        except Exception as e:  # o aviso sai mesmo se o banco estiver ocupado; o erro fica registrado
            arquivos.registrar_erro('observer fila', e)
        partes.append(
            f'[Luzia · fila] A pessoa enviou do painel a centelha #{item["id"]} ("{item.get("titulo", "")}"). Responda primeiro ao '
            'que ela pediu. No FIM, em uma linha começando com "✦ Luzia:", lembre a centelha e use AskUserQuestion com '
            '"Abrir em sessão nova", "Fazer aqui" e "Depois". Sessão nova: rode '
            f'`{CLI} prompt {item["id"]} --onde "sessão nova"` e abra uma sessão/agente novo com esse texto pela ferramenta do seu '
            f'harness (se não houver, faça aqui). Fazer aqui: rode `{CLI} fazer {item["id"]} --onde aqui` e siga o roteiro.'
        )
    if partes:
        saida('UserPromptSubmit', '\n'.join(partes))


@sem_quebrar
def ao_usar_ferramenta(event: dict, cfg: dict) -> None:
    """PostToolUse: luz refletida quando o agente aplica um conceito da sua trajetória."""
    modo = cfg.get('modo', 'ativo')
    if modo == 'sob_demanda':
        return
    tool, ti = event.get('tool_name', ''), event.get('tool_input') or {}
    if tool == 'Bash':
        cmd = ti.get('command', '')
        if 'git commit' not in cmd:
            return
        texto, ext = cmd, 'commit'
    else:
        caminho = ti.get('file_path', '')
        edits = ' '.join(e.get('new_string', '') for e in ti.get('edits', []) if isinstance(e, dict))
        texto = ' '.join([ti.get('content', ''), ti.get('new_string', ''), edits])
        ext = Path(caminho).suffix.lower() or 'arquivo'
    gaps = lacunas(plano())
    achados = [r for r in reconhecer_em(texto, 'agente', sessao_id(event), modo, ext, tool, gaps) if r['mudou']]
    if modo != 'ativo' or not achados:
        return
    r = max(achados, key=lambda x: x['lm'])  # um cartão por mudança: a centelha que mais vale converter
    saida('PostToolUse', cartao_refletida(r['skill'], r['titulo'], r['centelha'], r['lm'], provisorio=r['provisorio']))


@sem_quebrar
def ao_iniciar_sessao(event: dict, cfg: dict) -> None:
    """SessionStart: lembra o que dá para retomar, sem interromper."""
    if cfg.get('modo', 'ativo') == 'sob_demanda':
        return
    plan = plano()
    if not plan:
        return
    andamento = jogo.convertendo(banco.ESPERA_CURTA_MS)
    t = jogo.luz(plan, espera_ms=banco.ESPERA_CURTA_MS)
    para_converter = t['n_converter'] - len(andamento)
    try:
        fila = acoes.fila(banco.ESPERA_CURTA_MS)
    except Exception as e:
        arquivos.registrar_erro('observer fila', e)
        fila = []
    partes = []
    if andamento:
        partes.append(f'centelha convertendo: "{andamento[0].get("titulo", "")}"')
    if para_converter > 0:
        partes.append(f"{para_converter} {'centelha' if para_converter == 1 else 'centelhas'} de luz refletida para converter")
    if fila:
        partes.append(f"{len(fila)} {'centelha' if len(fila) == 1 else 'centelhas'} na fila do painel")
    if partes:
        saida('SessionStart', f"[Luzia · em foco · início] {'; '.join(partes)}. Não interrompa o que a pessoa pedir. No FIM da sua "
                              'primeira resposta, em UMA linha: "✦ Luzia (em foco): <resumo curto disso> · /luzia:hoje para continuar."')
        return
    apagadas = sum(p['n_apagada'] for p in t['prismas'])
    if apagadas and not t['propria']:  # logo depois da triagem: só centelhas apagadas e nenhuma luz própria ainda
        frase = f"{apagadas} {'centelha' if apagadas == 1 else 'centelhas'} na sua meta para acender"
        saida('SessionStart', f'[Luzia · em foco · início] A trajetória está pronta e ainda não há luz própria: {frase}. Não interrompa '
                              'o que a pessoa pedir. No FIM da sua primeira resposta, em UMA linha, exatamente assim: '
                              f'"✦ Luzia (em foco): {frase} · /luzia:hoje para começar."')


def main(bruto: bytes | None = None) -> None:
    """`bruto`: o evento já lido do stdin (o `lz.py` lê antes, para o porteiro barrar sem importar o resto)."""
    try:  # o Claude Code envia UTF-8; o pipe do Windows usaria a página de código local e estragaria os acentos
        if bruto is None:
            bruto = sys.stdin.buffer.read()
        event = json.loads(bruto.decode('utf-8', errors='replace'))
    except Exception:
        return
    if not isinstance(event, dict):  # o Claude Code manda um objeto; qualquer outra coisa é ignorada em silêncio
        return
    cfg = read_json(CFG, {'modo': 'ativo', 'autorizados': []})
    if not authorized(event.get('cwd', ''), cfg):
        return
    try:
        if event.get('hook_event_name') == 'UserPromptSubmit':
            ao_enviar_prompt(event, cfg)
        elif event.get('hook_event_name') == 'SessionStart':
            ao_iniciar_sessao(event, cfg)
        else:
            ao_usar_ferramenta(event, cfg)
    except Exception as e:  # o observador nunca deve atrapalhar a sessão, mas o erro fica registrado
        arquivos.registrar_erro(f"observer {event.get('hook_event_name', '')}", e)


if __name__ == '__main__':
    main()
