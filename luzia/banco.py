"""Banco SQLite da Luzia (`private/luzia.db`): a única camada que abre o estado persistente.

Hook, CLI e painel escrevem ao mesmo tempo, então:
- modo WAL (leitores não bloqueiam quem escreve) e `busy_timeout` de 5 s (quem chega espera a vez);
- toda escrita acontece dentro de `transacao(con)`, que abre `BEGIN IMMEDIATE` e confirma ou desfaz tudo;
- a conexão fica em autocommit do Python (`isolation_level=None`): só os `BEGIN` explícitos abrem transação;
- o hook grava por `gravar_ou_pendurar`, com espera curta: se o banco não abre ou está travado, o evento vai para
  `private/pendentes.jsonl` e a próxima `transacao` o absorve (a sessão nunca trava e nenhum evento se perde).

Livros só de acréscimo (`lumen`, `avanco_evento`, `nivel_registro`, `trajetoria_versao`, `chamada_modelo`):
o código só insere neles, nunca reescreve nem apaga (um teste procura isso nas consultas dos módulos).
O estado atual (estado de um avanço, nível de um prisma) fica em colunas e tem de bater com os livros.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

from . import arquivos

if os.name == 'nt':
    import msvcrt
else:
    import fcntl

ESQUEMA_VERSAO = 5  # 2: acesso_sessao e acesso_link; 3: pedido 'dividir'; 4: centelhas (estados de luz, onde, meta_estado)
#                     5: prisma.alvo_lm (avanço com alvo fixo; nulo até a próxima sincronização fixar)
ESPERA_MS = 5000
ESPERA_CURTA_MS = 1500  # caminho quente do hook: abrir e gravar cabem no tempo dele
PENDENTES = 'pendentes.jsonl'
RESERVA = 'pendentes-{ns:020d}-{pid}.absorvendo'  # arquivo reservado por uma absorção (o nome ordena pelo tempo)
MARCA = 'pendentes:'  # meta('pendentes:<reserva>'): aquela reserva já foi aplicada num COMMIT
ESPERA_PENDURAR_S = 0.3  # trava do acréscimo (segurada por microssegundos); 1,5 s do banco + isto cabe em ~2 s
_BYTE_DA_TRAVA = 1 << 40  # byte muito além do fim do arquivo: travá-lo serializa os acréscimos sem bloquear leitura
# Ao lado do banco: a migração falhou com este código (sobrevive ao rollback; apagar o arquivo libera nova tentativa).
MIGRACAO_FALHOU = 'migracao-falhou.json'

# O que o hook pode gravar: tabela → colunas aceitas (só dados do evento já mascarados; nunca texto de prompt ou código).
OPERACOES = {
    'lumen': ('quando', 'prisma', 'lm', 'luz', 'fonte', 'ref'),
    'sessao_evento': ('quando', 'sessao', 'prisma', 'extensao', 'ferramenta', 'modo', 'lm', 'luz', 'interveio'),
    'lampejo': ('prisma', 'sessao', 'quando', 'estado', 'usado_em'),
    # Um reconhecimento do observador inteiro (centelha + luz + evento da sessão): aplicado por `_reconhecer`.
    # `centelha` é o id; `nova_json` traz a centelha a criar se ela ainda não existe (origem 'chat').
    # As colunas antigas (lm, luz, fonte, ref, teto, lampejo) só chegam de pendentes gravados por um código anterior.
    'reconhecimento': ('quando', 'sessao', 'chave', 'prisma', 'centelha', 'nova_json', 'onde', 'extensao',
                       'ferramenta', 'modo', 'interveio', 'lm', 'luz', 'fonte', 'ref', 'teto', 'lampejo'),
}
# Colunas NOT NULL sem padrão (`quando` vem da hora do evento quando falta) e valores aceitos pelos CHECK do esquema.
OBRIGATORIAS = {'lumen': ('prisma', 'lm', 'luz', 'fonte'), 'sessao_evento': (), 'lampejo': ('prisma',),
               'reconhecimento': ('sessao', 'chave', 'prisma')}
VALORES = {'luz': ('propria', 'refletida'), 'estado': ('aberto', 'convertido', 'guardado')}

# Reservas marcadas em meta pela transação aberta de cada conexão (id(con) → arquivos): só podem ser apagadas
# depois do COMMIT dela. `sqlite3.Connection` não aceita atributo nem weakref; `transacao` zera a entrada no BEGIN
# e a retira no fim, então um id reaproveitado no máximo adia a limpeza (nunca apaga antes da hora).
_RESERVAS_ABERTAS: dict[int, list[Path]] = {}

# Banco que falhou numa gravação do hook (caminho → até quando `time.monotonic()` o trata como ocupado): enquanto vale,
# as gravações seguintes do mesmo processo vão direto para os pendentes, em vez de esperar de novo 1,5 s cada uma.
_OCUPADO_ATE: dict[Path, float] = {}
OCUPADO_POR_S = 5.0

ESQUEMA = (
    """CREATE TABLE IF NOT EXISTS meta (
        chave TEXT PRIMARY KEY,
        valor TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS perfil (
        chave TEXT PRIMARY KEY,
        valor_json TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS prisma (
        nome TEXT PRIMARY KEY,
        palavras_json TEXT NOT NULL DEFAULT '[]',
        nivel INTEGER,
        meta INTEGER,
        estado TEXT NOT NULL DEFAULT 'ativo' CHECK (estado IN ('ativo', 'arquivado')),
        origem TEXT NOT NULL DEFAULT 'triagem' CHECK (origem IN ('triagem', 'pedido')),
        ultimo_nivel_em TEXT,
        criado_em TEXT,
        meta_estado TEXT NOT NULL DEFAULT 'definida',  -- 'a_propor': a Luzia ainda vai propor as centelhas da meta
        alvo_lm INTEGER  -- lm de luz própria que completa o prisma; fixado quando a meta é definida (jogo.fixar_alvos)
    )""",
    """CREATE TABLE IF NOT EXISTS leitura (
        id INTEGER PRIMARY KEY,
        alvo_tipo TEXT NOT NULL CHECK (alvo_tipo IN ('prisma', 'entrega', 'pedido')),
        alvo_id TEXT NOT NULL,
        texto TEXT NOT NULL,
        base_json TEXT NOT NULL,
        base_hash TEXT NOT NULL,
        modelo TEXT NOT NULL,
        criado_em TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS pedido (
        id INTEGER PRIMARY KEY,
        tipo TEXT NOT NULL CHECK (tipo IN ('incluir', 'arquivar', 'reativar', 'mudar_meta', 'dividir')),
        prisma TEXT NOT NULL,
        motivo TEXT,
        proposta_json TEXT,
        leitura_id INTEGER REFERENCES leitura (id),
        estado TEXT NOT NULL DEFAULT 'aberto' CHECK (estado IN ('aberto', 'proposto', 'aceito', 'recusado')),
        criado_em TEXT NOT NULL,
        decidido_em TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS trajetoria_versao (
        numero INTEGER PRIMARY KEY,
        criada_em TEXT NOT NULL,
        origem TEXT NOT NULL,
        pedido_id INTEGER REFERENCES pedido (id),
        foto_json TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS entrega (
        id INTEGER PRIMARY KEY,
        chave TEXT NOT NULL UNIQUE,
        titulo TEXT,
        inicio TEXT,
        fim TEXT,
        commits INTEGER NOT NULL DEFAULT 0,
        arquivos INTEGER NOT NULL DEFAULT 0,
        linhas INTEGER NOT NULL DEFAULT 0,
        areas_json TEXT NOT NULL DEFAULT '[]',
        ids_privados_json TEXT NOT NULL DEFAULT '[]',
        fonte TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS commit_ (
        hash TEXT PRIMARY KEY,
        entrega_id INTEGER REFERENCES entrega (id),
        data TEXT,
        mensagem TEXT,
        arquivos INTEGER NOT NULL DEFAULT 0,
        linhas INTEGER NOT NULL DEFAULT 0,
        areas_json TEXT NOT NULL DEFAULT '[]'
    )""",
    """CREATE TABLE IF NOT EXISTS entrega_prisma (
        entrega_id INTEGER NOT NULL REFERENCES entrega (id),
        prisma TEXT NOT NULL,
        termos_json TEXT NOT NULL DEFAULT '[]',
        PRIMARY KEY (entrega_id, prisma)
    )""",
    # O avanço guarda o estado atual; a história fica no livro avanco_evento.
    """CREATE TABLE IF NOT EXISTS avanco (
        id TEXT PRIMARY KEY,
        prisma TEXT,
        tipo TEXT,
        titulo TEXT,
        conteudo_json TEXT NOT NULL DEFAULT '{}',
        duracao_min INTEGER,
        valor_lm INTEGER,
        conta_json TEXT,
        origem TEXT,
        entrega_id INTEGER,
        dimensao TEXT,
        estado TEXT NOT NULL,
        nota INTEGER,
        lm_ganho INTEGER NOT NULL DEFAULT 0,
        tentativas INTEGER NOT NULL DEFAULT 0,
        revisitas INTEGER NOT NULL DEFAULT 0,
        revisita_aberta INTEGER NOT NULL DEFAULT 0,
        criado_em TEXT NOT NULL,
        onde TEXT,           -- onde a luz apareceu (chat de DD/MM, extensão; nunca o caminho)
        confirmada_em TEXT   -- a Luzia confirmou o entendimento; falta o sim da pessoa para virar luz própria
    )""",
    """CREATE TABLE IF NOT EXISTS avanco_evento (
        id INTEGER PRIMARY KEY,
        avanco_id TEXT NOT NULL,  -- sem FK: eventos antigos (evidências P3/P4) citam ids fora do catálogo
        quando TEXT NOT NULL,
        evento TEXT NOT NULL,
        onde TEXT,
        nota INTEGER,
        resumo TEXT,
        motivo TEXT,
        extra_json TEXT  -- campos antigos sem coluna própria (ex.: skill, entrega e dimensão das evidências)
    )""",
    """CREATE TABLE IF NOT EXISTS lumen (
        id INTEGER PRIMARY KEY,
        quando TEXT NOT NULL,
        prisma TEXT NOT NULL,
        lm INTEGER NOT NULL,
        luz TEXT NOT NULL CHECK (luz IN ('propria', 'refletida')),
        fonte TEXT NOT NULL,
        ref TEXT NOT NULL DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS nivel_registro (
        id INTEGER PRIMARY KEY,
        prisma TEXT NOT NULL,
        de INTEGER,
        para INTEGER NOT NULL,
        quando TEXT NOT NULL,
        origem TEXT NOT NULL CHECK (origem IN ('conquistado', 'declarado', 'migrado', 'pedido')),
        lm INTEGER,
        luz_propria REAL
    )""",
    """CREATE TABLE IF NOT EXISTS lampejo (
        id INTEGER PRIMARY KEY,
        prisma TEXT NOT NULL,
        sessao TEXT,
        quando TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'aberto' CHECK (estado IN ('aberto', 'convertido', 'guardado')),
        usado_em TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS fila (
        avanco_id TEXT PRIMARY KEY,
        titulo TEXT,
        quando TEXT NOT NULL,
        oferecida_json TEXT NOT NULL DEFAULT '[]'
    )""",
    """CREATE TABLE IF NOT EXISTS sessao_evento (
        id INTEGER PRIMARY KEY,
        quando TEXT NOT NULL,
        sessao TEXT,
        prisma TEXT,
        extensao TEXT,
        ferramenta TEXT,
        modo TEXT,
        lm INTEGER,
        luz TEXT,
        interveio INTEGER
    )""",
    # Um reconhecimento por prisma por sessão e por origem (prompt/agente): INSERT OR IGNORE decide quem chegou primeiro.
    """CREATE TABLE IF NOT EXISTS sessao_visto (
        sessao TEXT NOT NULL,
        chave TEXT NOT NULL,
        prisma TEXT NOT NULL,
        quando TEXT NOT NULL,
        PRIMARY KEY (sessao, chave, prisma)
    )""",
    """CREATE TABLE IF NOT EXISTS chamada_modelo (
        id INTEGER PRIMARY KEY,
        quando TEXT NOT NULL,
        rotulo TEXT,
        modelo TEXT,
        segundos REAL,
        tokens_in INTEGER,
        tokens_out INTEGER,
        registro_json TEXT
    )""",
    # Entrada no painel (acesso.py): só o SHA-256 dos tokens; o token em claro nunca é gravado.
    """CREATE TABLE IF NOT EXISTS acesso_sessao (
        hash TEXT PRIMARY KEY,
        criada_em REAL NOT NULL,
        ultimo_uso REAL NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS acesso_link (
        hash TEXT PRIMARY KEY,
        expira REAL NOT NULL
    )""",
    'CREATE INDEX IF NOT EXISTS lumen_prisma_quando ON lumen (prisma, quando)',
    'CREATE INDEX IF NOT EXISTS avanco_prisma_estado ON avanco (prisma, estado)',
    'CREATE INDEX IF NOT EXISTS avanco_evento_avanco ON avanco_evento (avanco_id, quando)',
    'CREATE INDEX IF NOT EXISTS nivel_registro_prisma ON nivel_registro (prisma, quando)',
    'CREATE INDEX IF NOT EXISTS lampejo_prisma_estado ON lampejo (prisma, estado)',
    'CREATE INDEX IF NOT EXISTS sessao_evento_sessao ON sessao_evento (sessao, prisma)',
    'CREATE INDEX IF NOT EXISTS commit_entrega ON commit_ (entrega_id)',
    'CREATE INDEX IF NOT EXISTS leitura_alvo ON leitura (alvo_tipo, alvo_id)',
)


def caminho() -> Path:
    """Onde mora o banco; lê `arquivos.PRIVATE` a cada chamada (LUZIA_PRIVATE pode mudar, como nos testes)."""
    return Path(arquivos.PRIVATE) / 'luzia.db'


def _restante_ms(limite: float) -> int:
    return max(0, int((limite - time.monotonic()) * 1000))


def conectar(arquivo: Path | None = None, espera_ms: int = ESPERA_MS) -> sqlite3.Connection:
    """Abre o banco (por padrão `caminho()`), configura WAL, espera e chaves estrangeiras e garante o esquema.

    `espera_ms` é o prazo total da abertura (ligar o WAL e esperar a trava da migração) e o `busy_timeout` da conexão.
    """
    arquivo = Path(arquivo) if arquivo is not None else caminho()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    limite = time.monotonic() + espera_ms / 1000
    con = sqlite3.connect(arquivo, timeout=espera_ms / 1000, isolation_level=None)
    try:
        con.row_factory = sqlite3.Row
        con.execute(f'PRAGMA busy_timeout = {int(espera_ms)}')
        _ligar_wal(con, limite)
        con.execute('PRAGMA foreign_keys = ON')
        con.execute(f'PRAGMA busy_timeout = {_restante_ms(limite)}')  # o que sobrou do prazo, para a trava de garantir
        garantir(con)
        con.execute(f'PRAGMA busy_timeout = {int(espera_ms)}')
    except BaseException:
        con.close()
        raise
    return con


def _ligar_wal(con: sqlite3.Connection, limite: float) -> None:
    """Liga o WAL tentando de novo até `limite`: num banco novo, quem chega junto recebe BUSY na hora.

    `PRAGMA journal_mode = WAL` precisa de trava exclusiva e o SQLite não chama o busy handler para ela,
    então hook, statusline, painel e CLI abrindo o banco pela primeira vez ao mesmo tempo falhariam.
    """
    while True:
        try:
            modo = con.execute('PRAGMA journal_mode = WAL').fetchone()[0]
            if str(modo).lower() == 'wal':
                return
            erro: Exception = RuntimeError(f'luzia.db ficou no modo {modo}, não em WAL')
        except sqlite3.OperationalError as e:
            erro = e
        if time.monotonic() >= limite:
            raise erro
        time.sleep(0.02)


@contextmanager
def transacao(con: sqlite3.Connection, modo: str = 'IMMEDIATE',
              absorver: bool = True) -> Iterator[sqlite3.Connection]:
    """`with transacao(con):` abre `BEGIN IMMEDIATE` (ou `EXCLUSIVE`); confirma no fim ou desfaz se der erro.

    Logo depois do BEGIN, na mesma transação, absorve os eventos pendentes do hook (`absorver=False` só em
    `garantir`, quando o esquema ainda pode não existir); os arquivos absorvidos só são apagados depois do COMMIT.
    """
    if modo not in ('IMMEDIATE', 'EXCLUSIVE'):
        raise ValueError(f'modo de transação inválido: {modo}')
    con.execute(f'BEGIN {modo}')
    _RESERVAS_ABERTAS[id(con)] = []  # transação nova: nada dela marcado ainda
    try:
        if absorver:
            _absorver(con)
        yield con
    except BaseException:
        _RESERVAS_ABERTAS.pop(id(con), None)
        con.rollback()
        raise
    try:
        con.commit()
    except BaseException:
        _RESERVAS_ABERTAS.pop(id(con), None)
        if con.in_transaction:  # o COMMIT falhou (ex.: chave adiada, trava): não deixa a conexão presa
            con.rollback()
        raise
    _apagar(_RESERVAS_ABERTAS.pop(id(con), []))  # inclui o que `absorver_pendentes` aplicou dentro do bloco


# --- Pendentes do hook ---------------------------------------------------------------------------------------------
# Quem absorve reserva o arquivo renomeando-o (`pendentes.jsonl` → `pendentes-<ns>-<pid>.absorvendo`) com a trava de
# escrita do banco na mão; o hook seguinte cria um `pendentes.jsonl` novo, então nada que chega depois se perde.
# A reserva aplicada ganha uma marca em `meta` no mesmo COMMIT das linhas: se o processo morrer antes de apagar o
# arquivo, a próxima absorção vê a marca e só apaga (nunca aplica duas vezes); se a transação desfizer, não há marca
# e o arquivo reservado é aplicado na próxima. No Windows, renomear um arquivo aberto falha: aí a absorção daquele
# arquivo fica para a próxima transação, sem esperar.

def _validar(operacao: str, dados: dict) -> dict:
    """Confere operação, colunas e tipos (erro de programação → ValueError) e devolve uma cópia dos dados."""
    if operacao not in OPERACOES:
        raise ValueError(f'operação desconhecida para o banco: {operacao!r}')
    if not isinstance(dados, dict):
        raise ValueError(f'dados de {operacao} precisam ser um dict')
    estranhas = set(dados) - set(OPERACOES[operacao])
    if estranhas:
        raise ValueError(f'colunas desconhecidas em {operacao}: {sorted(estranhas)}')
    if any(v is not None and not isinstance(v, (str, int, float)) for v in dados.values()):
        raise ValueError(f'valores de {operacao} precisam ser texto, número ou nulo')
    faltando = [c for c in OBRIGATORIAS[operacao] if dados.get(c) is None]
    if faltando:
        raise ValueError(f'colunas obrigatórias faltando em {operacao}: {faltando}')
    for coluna, aceitos in VALORES.items():
        if dados.get(coluna) is not None and dados[coluna] not in aceitos:
            raise ValueError(f'{coluna} inválido em {operacao}; aceitos: {list(aceitos)}')
    return dict(dados)


def _reconhecer(con: sqlite3.Connection, d: dict) -> dict | None:
    """Aplica um reconhecimento do observador a uma centelha (docs/specs/2026-11-18-centelhas-conversao.md).

    - o agente aplicou o conceito (`chave` != 'prompt'): `apagada` → `refletida`;
    - o prompt da pessoa citou o conceito: `apagada`/`refletida`/`convertendo` → `propria` (lúmen próprio, fonte 'prompt').
    Se a centelha não existe e `nova_json` veio, ela nasce (origem 'chat') antes da transição. Cada centelha muda de luz
    uma vez só, então repetir o conceito não infla nada; `sessao_visto` (prisma = 'c:<id>') só evita repetir o aviso.
    Devolve {'centelha', 'estado', 'lm', 'luz', 'novo', 'mudou'} ou None quando não há nada a mostrar.
    Roda igual na hora (hook) e na absorção dos pendentes, então nada se perde e nada se duplica.
    """
    quando = d['quando']
    try:  # poda as sessões com mais de 7 dias
        corte = (datetime.fromisoformat(quando) - timedelta(days=7)).isoformat(timespec='seconds')
        con.execute('DELETE FROM sessao_visto WHERE quando < ?', (corte,))
    except ValueError:
        pass
    cid = d.get('centelha')
    if not cid:  # pendente de um código anterior (modelo de níveis): só o fato da sessão, sem lúmen
        con.execute('INSERT INTO sessao_evento (quando, sessao, prisma, extensao, ferramenta, modo, lm, luz, interveio) '
                    'VALUES (?, ?, ?, ?, ?, ?, 0, ?, 0)',
                    (quando, d['sessao'], d['prisma'], d.get('extensao'), d.get('ferramenta'), d.get('modo'), d.get('luz')))
        return None
    agente = d['chave'] != 'prompt'
    novo = False
    r = con.execute('SELECT estado, valor_lm, prisma, origem FROM avanco WHERE id = ?', (cid,)).fetchone()
    if r is not None and d.get('nova_json') and (r['origem'] != 'chat' or r['prisma'] != d['prisma']):
        return None  # o id pedido para uma centelha do chat já é de outra centelha: nunca mexe na luz dela
    if r is None:
        try:
            nova = json.loads(d.get('nova_json') or 'null')
        except ValueError:
            nova = None
        if not isinstance(nova, dict):
            return None
        con.execute(
            'INSERT OR IGNORE INTO avanco (id, prisma, tipo, titulo, conteudo_json, duracao_min, valor_lm, conta_json,'
            " origem, estado, criado_em, onde) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'chat', 'apagada', ?, ?)",
            (cid, d['prisma'], nova.get('tipo') or 'explicar', nova.get('titulo') or '',
             json.dumps(nova.get('conteudo') or {}, ensure_ascii=False), nova.get('duracao_min'), int(nova.get('valor_lm') or 10),
             json.dumps(nova.get('conta'), ensure_ascii=False) if nova.get('conta') is not None else None, quando, d.get('onde')))
        novo = True
        r = con.execute('SELECT estado, valor_lm, prisma, origem FROM avanco WHERE id = ?', (cid,)).fetchone()
    estado, lm = r['estado'], int(r['valor_lm'] or 0)
    if estado == 'descartada':
        return None
    visto = con.execute('INSERT OR IGNORE INTO sessao_visto (sessao, chave, prisma, quando) VALUES (?, ?, ?, ?)',
                        (d['sessao'], d['chave'], f'c:{cid}', quando)).rowcount == 1
    para = None
    if agente and estado == 'apagada':
        para, luz, fonte, evento = 'refletida', 'refletida', 'agente', 'refletida pelo agente'
    elif not agente and estado in ('apagada', 'refletida') and r['origem'] == 'chat':
        para, luz, fonte, evento = 'propria', 'propria', 'prompt', 'própria pelo prompt'
    if para is None and not visto:
        return None
    if para is not None:
        if para == 'propria':
            con.execute('UPDATE avanco SET estado = ?, onde = COALESCE(?, onde), lm_ganho = ? WHERE id = ?',
                        (para, d.get('onde'), lm, cid))
        else:
            con.execute('UPDATE avanco SET estado = ?, onde = COALESCE(?, onde) WHERE id = ?', (para, d.get('onde'), cid))
        con.execute('INSERT INTO avanco_evento (avanco_id, quando, evento, onde, extra_json) VALUES (?, ?, ?, ?, ?)',
                    (cid, quando, evento, d.get('onde'),
                     json.dumps({'fonte': 'historico', 'sessao': d['sessao'], 'lm': lm}, ensure_ascii=False)))
        con.execute('INSERT INTO lumen (quando, prisma, lm, luz, fonte, ref) VALUES (?, ?, ?, ?, ?, ?)',
                    (quando, r['prisma'], lm, luz, fonte, cid))
    luz_atual = 'propria' if (para or estado) == 'propria' else 'refletida'
    con.execute('INSERT INTO sessao_evento (quando, sessao, prisma, extensao, ferramenta, modo, lm, luz, interveio) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (quando, d['sessao'], r['prisma'], d.get('extensao'), d.get('ferramenta'), d.get('modo'),
                 lm if para else 0, luz_atual, 1 if d.get('interveio') and para else 0))
    return {'centelha': cid, 'estado': para or estado, 'lm': lm, 'luz': luz_atual, 'novo': novo, 'mudou': para is not None}


def _inserir(con: sqlite3.Connection, operacao: str, dados: dict, quando: str):
    """Uma linha na tabela da operação; sem `quando` nos dados, vale a hora em que o evento aconteceu."""
    linha = dict(dados)
    if 'quando' in OPERACOES[operacao] and not linha.get('quando'):
        linha['quando'] = quando
    if operacao == 'reconhecimento':
        return _reconhecer(con, linha)
    colunas = list(linha)  # nomes já conferidos contra OPERACOES
    con.execute(f'INSERT INTO {operacao} ({", ".join(colunas)}) VALUES ({", ".join(["?"] * len(colunas))})',
                [linha[c] for c in colunas])


def _travar(fd: int, prazo: float) -> bool:
    """Trava exclusiva de quem acrescenta em `pendentes.jsonl`, tentando até `prazo`; False se não saiu a tempo.

    No Windows o modo de acréscimo do C busca o fim e depois escreve, em dois passos: dois hooks juntos acham o
    mesmo fim e o segundo sobrescreve o primeiro (o evento some). Travar um byte muito além do fim serializa só os
    acréscimos, sem bloquear leitura; a reserva por renomeação continua falhando enquanto o arquivo estiver aberto.
    """
    while True:
        try:
            if os.name == 'nt':
                os.lseek(fd, _BYTE_DA_TRAVA, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            if time.monotonic() >= prazo:
                return False
            time.sleep(0.002)


def _destravar(fd: int) -> None:
    try:
        if os.name == 'nt':
            os.lseek(fd, _BYTE_DA_TRAVA, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass  # fechar o arquivo solta a trava de qualquer jeito


def _acrescentar(arquivo: Path, dados: bytes, prazo: float) -> bool:
    """Acrescenta `dados` inteiro com a trava na mão; False se a trava não saiu até `prazo` (nada foi escrito)."""
    fd = os.open(arquivo, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, 'O_BINARY', 0), 0o600)
    try:
        if not _travar(fd, prazo):
            return False
        try:
            resto = memoryview(dados)
            while resto:  # com O_APPEND cada write vai para o fim atual, já protegido pela trava
                resto = resto[os.write(fd, resto):]
        finally:
            _destravar(fd)
        return True
    finally:
        os.close(fd)


def _arquivo_proprio(pasta: Path, dados: bytes) -> None:
    """Último recurso: o evento num arquivo só dele, já no formato de reserva (a próxima absorção o aplica).

    Escreve num `.tmp` e renomeia, então a absorção só enxerga o arquivo completo.
    """
    nome = RESERVA.format(ns=time.time_ns(), pid=os.getpid())
    tmp = pasta / (nome + '.tmp')
    tmp.write_bytes(dados)
    os.replace(tmp, pasta / nome)


def _pendurar(arquivo: Path, operacao: str, dados: dict, quando: str) -> None:
    """Acrescenta uma linha `{"operacao", "dados", "quando"}`; nunca levanta (se nem isso der, fica no erros.log).

    O acréscimo é atômico entre processos (`_travar`). Se a trava ou o arquivo não saírem em ESPERA_PENDURAR_S, o
    evento vai para um arquivo próprio em vez de se perder.
    """
    texto = json.dumps({'operacao': operacao, 'dados': dados, 'quando': quando}, ensure_ascii=False) + '\n'
    linha = texto.encode('utf-8')
    prazo = time.monotonic() + ESPERA_PENDURAR_S
    erro: OSError | str = 'trava_ocupada'
    while True:
        try:
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            if _acrescentar(arquivo, linha, prazo):
                return
            break
        except PermissionError as e:  # Windows: uma absorção renomeando o arquivo neste instante
            erro = e
            if time.monotonic() >= prazo:
                break
            time.sleep(0.005)
        except OSError as e:
            erro = e
            break
    arquivos.registrar_erro('banco.pendurar', erro)
    try:
        _arquivo_proprio(arquivo.parent, linha)
    except OSError as e:
        arquivos.registrar_erro('banco.pendurar', e)


def _pasta_do_banco(con: sqlite3.Connection) -> Path | None:
    """Pasta do arquivo principal da conexão (os pendentes moram ao lado do banco); None para banco em memória."""
    for linha in con.execute('PRAGMA database_list'):
        if linha[1] == 'main':
            return Path(linha[2]).parent if linha[2] else None
    return None


def _decodificar(texto: str) -> tuple[str, dict, str]:
    """Uma linha do arquivo de pendentes → (operação, dados conferidos, quando); ValueError se não servir."""
    linha = json.loads(texto)
    if not isinstance(linha, dict) or not isinstance(linha.get('operacao'), str):
        raise ValueError('linha sem operação')
    quando = linha.get('quando')
    return linha['operacao'], _validar(linha['operacao'], linha.get('dados')), quando if isinstance(quando, str) else ''


def _aplicar(con: sqlite3.Connection, arquivo: Path) -> int:
    """Aplica as linhas de um arquivo reservado, em ordem; linha ruim é pulada e registrada (só o tipo do problema)."""
    n = 0
    for texto in arquivo.read_bytes().decode('utf-8', errors='replace').splitlines():
        if not texto.strip():
            continue
        try:
            operacao, dados, quando = _decodificar(texto)
        except ValueError:  # inclui JSON cortado ou inválido
            arquivos.registrar_erro('banco.absorver_pendentes', 'linha_invalida')
            continue
        con.execute('SAVEPOINT pendente_linha')
        try:
            _inserir(con, operacao, dados, quando)
        except (sqlite3.IntegrityError, sqlite3.ProgrammingError, sqlite3.InterfaceError) as e:  # nunca vai entrar
            con.execute('ROLLBACK TO pendente_linha')
            arquivos.registrar_erro('banco.absorver_pendentes', e)
            continue
        finally:
            con.execute('RELEASE pendente_linha')
        n += 1
    return n


def _absorver(con: sqlite3.Connection) -> int:
    """Aplica os pendentes na transação aberta e devolve quantas linhas entraram.

    Os arquivos aplicados ficam em `_RESERVAS_ABERTAS` para serem apagados só depois do COMMIT. Roda num SAVEPOINT:
    se o banco falhar aqui, desfaz só a absorção (os arquivos ficam para a próxima vez) e a escrita de quem chamou segue.
    """
    pasta = _pasta_do_banco(con)
    if pasta is None:
        return 0
    abertas = _RESERVAS_ABERTAS.setdefault(id(con), [])
    desta_transacao = {a.name for a in abertas}
    novas: list[Path] = []
    con.execute('SAVEPOINT pendentes')
    try:
        marcadas = {r[0][len(MARCA):] for r in
                    con.execute('SELECT chave FROM meta WHERE substr(chave, 1, ?) = ?', (len(MARCA), MARCA))}
        for nome in marcadas - desta_transacao:  # aplicadas num COMMIT anterior: só falta apagar o arquivo
            try:
                (pasta / nome).unlink(missing_ok=True)
            except OSError:
                continue
            con.execute('DELETE FROM meta WHERE chave = ?', (MARCA + nome,))
        try:
            os.replace(pasta / PENDENTES, pasta / RESERVA.format(ns=time.time_ns(), pid=os.getpid()))
        except OSError:  # não existe, ou (Windows) um hook está escrevendo agora: fica para a próxima transação
            pass
        n = 0
        for arquivo in sorted(pasta.glob('pendentes-*.absorvendo')):
            if arquivo.name in marcadas:  # inclui as marcadas por esta mesma transação
                continue
            try:
                n += _aplicar(con, arquivo)
            except OSError as e:
                arquivos.registrar_erro('banco.absorver_pendentes', e)
                continue
            con.execute('INSERT INTO meta (chave, valor) VALUES (?, ?)',
                        (MARCA + arquivo.name, datetime.now().isoformat(timespec='seconds')))
            novas.append(arquivo)
    except sqlite3.Error as e:
        con.execute('ROLLBACK TO pendentes')
        con.execute('RELEASE pendentes')
        arquivos.registrar_erro('banco.absorver_pendentes', e)
        return 0
    con.execute('RELEASE pendentes')
    abertas.extend(novas)
    return n


def _apagar(feitos: list[Path]) -> None:
    """Depois do COMMIT: apaga os arquivos absorvidos (se falhar, a marca em meta impede aplicar de novo)."""
    for arquivo in feitos:
        try:
            arquivo.unlink(missing_ok=True)
        except OSError:
            pass


def absorver_pendentes(con: sqlite3.Connection) -> int:
    """Aplica os eventos pendentes do hook na transação de escrita já aberta; devolve quantos entraram.

    `transacao` chama isto sozinha no início; chamada de novo dentro do bloco, não repete nem apaga o que esta
    transação marcou. Os arquivos somem depois do COMMIT de `transacao` (fora dela, na próxima absorção).
    """
    if not con.in_transaction:
        raise RuntimeError('absorver_pendentes precisa de uma transação de escrita aberta (use transacao)')
    return _absorver(con)


def ocupado() -> bool:
    """O banco falhou numa gravação do hook há pouco (as próximas gravações nem esperam: vão direto para os pendentes)."""
    return time.monotonic() < _OCUPADO_ATE.get(caminho(), 0.0)


def gravar_ou_pendurar(operacao: str, dados: dict, ajustar=None, retorno: dict | None = None) -> bool:
    """Caminho quente do hook: grava o evento com espera curta (ESPERA_CURTA_MS) e devolve True.

    Se o banco não abre, não migra ou está travado (qualquer falha do SQLite, do disco ou da migração), acrescenta
    o evento em `pendentes.jsonl` e devolve False, sem levantar. Operação, coluna ou valor fora do previsto é erro
    de programação: levanta ValueError e não vai para os pendentes.

    `ajustar(con, dados)` (opcional) roda dentro da mesma transação curta, antes do INSERT: devolve os dados finais
    ou None (nada a gravar). Se o banco falhar, os dados originais vão para os pendentes.
    `retorno` (opcional) recebe em 'resultado' o que a operação devolveu (ex.: lm de um reconhecimento).
    """
    dados = _validar(operacao, dados)
    quando = datetime.now().isoformat(timespec='seconds')
    if ocupado():
        _pendurar(caminho().parent / PENDENTES, operacao, dados, quando)
        return False
    limite = time.monotonic() + ESPERA_CURTA_MS / 1000
    con = None
    try:
        con = conectar(espera_ms=ESPERA_CURTA_MS)
        con.execute(f'PRAGMA busy_timeout = {_restante_ms(limite)}')
        with transacao(con):
            finais = ajustar(con, dict(dados)) if ajustar is not None else dados
            if finais is not None:
                resultado = _inserir(con, operacao, _validar(operacao, finais), quando)
                if retorno is not None:
                    retorno['resultado'] = resultado
        return True
    except Exception as e:  # a sessão nunca trava por causa do banco
        arquivos.registrar_erro('banco.gravar_ou_pendurar', e)
        _OCUPADO_ATE[caminho()] = time.monotonic() + OCUPADO_POR_S
        _pendurar(caminho().parent / PENDENTES, operacao, dados, quando)
        return False
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass


def _meta(con: sqlite3.Connection) -> dict[str, str]:
    """As marcas `esquema` e `migrado_em`, ou {} se o banco ainda não tem a tabela meta."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'meta'").fetchone():
        return {}
    linhas = con.execute("SELECT chave, valor FROM meta WHERE chave IN ('esquema', 'migrado_em')").fetchall()
    return {r['chave']: r['valor'] for r in linhas}


def _pronto(con: sqlite3.Connection) -> bool:
    marcas = _meta(con)
    versao = marcas.get('esquema')
    if versao is not None and int(versao) > ESQUEMA_VERSAO:
        raise RuntimeError(f'luzia.db tem esquema {versao}, mais novo que o deste código ({ESQUEMA_VERSAO})')
    return versao == str(ESQUEMA_VERSAO) and bool(marcas.get('migrado_em'))


def _marca_falha(con: sqlite3.Connection) -> Path | None:
    pasta = _pasta_do_banco(con)
    return pasta / MIGRACAO_FALHOU if pasta is not None else None


def _bloqueio(arquivo: Path | None, versao: str) -> dict | None:
    """A marca de falha, se ela vale para este código da migração (marca ilegível ou de outro código: não bloqueia)."""
    if arquivo is None:
        return None
    try:
        marca = json.loads(arquivo.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return marca if isinstance(marca, dict) and marca.get('versao') == versao else None


def _onde(erro: BaseException) -> str:
    """Arquivo, linha e função onde a migração quebrou (nunca o dado que a quebrou)."""
    quadros = traceback.extract_tb(erro.__traceback__)
    if not quadros:
        return 'desconhecido'
    q = next((q for q in reversed(quadros) if Path(q.filename).name == 'migrar.py'), quadros[-1])
    return f'{Path(q.filename).name}:{q.lineno} {q.name}'


def _bloqueada(marca: dict) -> RuntimeError:
    return RuntimeError(
        f"migração bloqueada: a migração dos dados antigos falhou ({marca.get('erro')} em {marca.get('onde')}); "
        f'veja {arquivos.PRIVATE / "erros.log"}. Ela só é tentada de novo quando o código da migração mudar ou quando '
        f'{arquivos.PRIVATE / MIGRACAO_FALHOU} for apagado.')


def _completar(con: sqlite3.Connection) -> None:
    """Banco já pronto de uma versão anterior deste esquema: cria só as tabelas que faltam (CREATE IF NOT EXISTS)."""
    existentes = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    faltam = [sql for sql in ESQUEMA if sql.startswith('CREATE TABLE')
              and sql.split('EXISTS', 1)[1].split('(', 1)[0].strip() not in existentes]
    if faltam:
        with transacao(con, absorver=False):
            for sql in faltam:
                con.execute(sql)


TIPOS_PEDIDO_V2 = "CHECK (tipo IN ('incluir', 'arquivar', 'reativar', 'mudar_meta'))"
TIPOS_PEDIDO_V3 = "CHECK (tipo IN ('incluir', 'arquivar', 'reativar', 'mudar_meta', 'dividir'))"


COLUNAS_V4 = (('avanco', 'onde', 'TEXT'), ('avanco', 'confirmada_em', 'TEXT'),
              ('prisma', 'meta_estado', "TEXT NOT NULL DEFAULT 'definida'"), ('prisma', 'alvo_lm', 'INTEGER'))


def _colunas_v4(con: sqlite3.Connection) -> None:
    """4 e 5: colunas novas das centelhas e do alvo (ADD COLUMN só acrescenta; nada do que existe muda)."""
    for tabela, coluna, tipo in COLUNAS_V4:
        if coluna not in {r[1] for r in con.execute(f'PRAGMA table_info({tabela})')}:
            con.execute(f'ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}')


def _estados_v4(con: sqlite3.Connection) -> None:
    """Estados do modelo de níveis → estados de luz (idempotente: só toca nos nomes antigos).

    `conquistado` com nota 3 ou 4 vira `propria` (com o lm cheio); com nota 0–2 volta a `convertendo` e o lm antigo
    fica na história; `sugerido` vira `apagada`; `na_fila` e `em_andamento` viram `convertendo`.
    """
    agora_ = datetime.now().isoformat(timespec='seconds')
    for fid, lm_ganho, nota in con.execute(
            "SELECT id, lm_ganho, nota FROM avanco WHERE estado = 'conquistado' AND COALESCE(nota, 0) < 3").fetchall():
        con.execute("INSERT INTO avanco_evento (avanco_id, quando, evento, nota, extra_json) VALUES (?, ?, 'volta a convertendo', ?, ?)",
                    (fid, agora_, nota, json.dumps({'fonte': 'historico', 'lm_antigo': lm_ganho,
                                                    'motivo': 'nota abaixo de 3 no modelo de níveis'})))
    con.execute("UPDATE avanco SET estado = 'convertendo', lm_ganho = 0 WHERE estado = 'conquistado' AND COALESCE(nota, 0) < 3")
    con.execute("UPDATE avanco SET estado = 'propria', lm_ganho = COALESCE(valor_lm, lm_ganho) WHERE estado = 'conquistado'")
    con.execute("UPDATE avanco SET estado = 'convertendo' WHERE estado IN ('na_fila', 'em_andamento')")
    con.execute("UPDATE avanco SET estado = 'apagada' WHERE estado = 'sugerido'")
    con.execute("UPDATE avanco SET estado = 'descartada' WHERE estado = 'descartado'")


def _backup_antes_centelhas(con: sqlite3.Connection) -> None:
    """Cópia do banco antes de subir do modelo de níveis (esquema 3) para o de centelhas."""
    pasta = _pasta_do_banco(con)
    if pasta is None:
        return
    destino = pasta / f'backup-antes-centelhas-{datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}-{time.monotonic_ns()}'
    destino.mkdir(parents=True, exist_ok=False)
    # Copia por uma conexão de leitura à parte: no WAL ela lê o estado confirmado (o esquema antigo) sem esperar a trava
    # exclusiva que `con` segura; copiar pela própria `con` dentro da transação trava o SQLite esperando por si mesmo.
    arquivo = con.execute('PRAGMA database_list').fetchone()[2]
    origem = sqlite3.connect(f'file:{Path(arquivo).as_posix()}?mode=ro', uri=True)
    copia = sqlite3.connect(destino / 'luzia.db')
    try:
        origem.backup(copia)
        versao = copia.execute("SELECT valor FROM meta WHERE chave = 'esquema'").fetchone()
        if versao is None or int(versao[0]) >= 4:
            raise RuntimeError('backup antes das centelhas não é do esquema antigo')
    finally:
        copia.close()
        origem.close()


def _subir_esquema(con: sqlite3.Connection, versao_antes: str | None = None) -> None:
    """Passos de um esquema antigo para o atual, dentro da transação exclusiva de `garantir` (sem migrar de novo).

    4: colunas das centelhas; vindo de um esquema anterior, os prismas ativos ficam com a meta `a_propor`
    (a Luzia propõe as centelhas apagadas que a meta pede). Os estados são mapeados em `garantir`, depois da migração.

    3: o CHECK de `pedido.tipo` ganha 'dividir'. Só alarga um CHECK (o formato no disco não muda), então segue o
    procedimento do SQLite para isso: trocar o SQL da tabela em `sqlite_master` e somar 1 ao `schema_version`
    (recriar a tabela exigiria desligar as chaves estrangeiras, o que não pode acontecer dentro de uma transação).
    """
    _colunas_v4(con)
    if versao_antes is not None and int(versao_antes) < 4:
        con.execute("UPDATE prisma SET meta_estado = 'a_propor' WHERE estado = 'ativo'")
    linha = con.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'pedido'").fetchone()
    if linha is None or TIPOS_PEDIDO_V2 not in linha[0]:
        return
    versao = int(con.execute('PRAGMA schema_version').fetchone()[0])
    con.execute('PRAGMA writable_schema = ON')
    try:
        con.execute("UPDATE sqlite_master SET sql = ? WHERE type = 'table' AND name = 'pedido'",
                    (linha[0].replace(TIPOS_PEDIDO_V2, TIPOS_PEDIDO_V3),))
        con.execute(f'PRAGMA schema_version = {versao + 1}')
    finally:
        con.execute('PRAGMA writable_schema = OFF')


def garantir(con: sqlite3.Connection) -> None:
    """Cria o esquema que faltar e roda a migração dos JSON uma única vez, numa transação exclusiva.

    Qualquer ponto de entrada (hook, CLI, painel) pode chegar primeiro: quem pega a trava cria e migra;
    quem chega depois só confere as marcas `meta('esquema')` e `meta('migrado_em')`.

    Se a migração levantar um erro inesperado, tudo é desfeito e fica uma marca `migracao-falhou.json` ao lado do
    banco (versão do código da migração, hora, tipo do erro e onde): enquanto ela valer para o código atual, abrir o
    banco levanta `RuntimeError('migração bloqueada: ...')` na hora, sem tentar de novo nem copiar os originais outra
    vez (o hook segue pendurando eventos em `pendentes.jsonl`). Trava ou falha de disco (`OperationalError`, ou
    `OSError` ao copiar os originais para o backup) não marca: a próxima abertura tenta de novo.
    """
    if _pronto(con):
        _completar(con)
        return
    from . import migrar  # import tardio: a migração usa este módulo e não pode criar ciclo
    arquivo, versao = _marca_falha(con), migrar.versao()
    marca = _bloqueio(arquivo, versao)
    if marca is not None:
        raise _bloqueada(marca)
    falha: Exception | None = None
    try:
        with transacao(con, 'EXCLUSIVE', absorver=False):
            if _pronto(con):  # outro processo terminou enquanto esperávamos a trava
                return
            marcas = _meta(con)
            versao_antes = marcas.get('esquema')
            if versao_antes is not None and int(versao_antes) < 4 and marcas.get('migrado_em'):
                _backup_antes_centelhas(con)  # com a trava exclusiva: ninguém sobe o banco no meio da cópia
            for sql in ESQUEMA:
                con.execute(sql)
            _subir_esquema(con, versao_antes)
            con.execute("INSERT INTO meta (chave, valor) VALUES ('esquema', ?) "
                        'ON CONFLICT (chave) DO UPDATE SET valor = excluded.valor', (str(ESQUEMA_VERSAO),))
            if not _meta(con).get('migrado_em'):
                try:
                    migrar.migrar(con)
                except (sqlite3.OperationalError, OSError):  # trava, disco, cópia de backup: tenta de novo depois
                    raise
                except Exception as e:
                    falha = e
                    raise
                con.execute("INSERT INTO meta (chave, valor) VALUES ('migrado_em', ?)",
                            (datetime.now().isoformat(timespec='seconds'),))
            _estados_v4(con)
    except Exception as e:
        if e is not falha:
            raise
        marca = {'versao': versao, 'quando': datetime.now().isoformat(timespec='seconds'),
                 'erro': type(e).__name__, 'onde': _onde(e)}
        arquivos.registrar_erro(f"banco.garantir migração ({marca['onde']})", e)
        if arquivo is not None:
            try:
                arquivos.gravar_json(arquivo, marca)
            except OSError as erro_marca:
                arquivos.registrar_erro('banco.garantir marca da migração', erro_marca)
        raise _bloqueada(marca) from e
    if arquivo is not None:
        try:
            arquivo.unlink(missing_ok=True)  # uma falha antiga (de outro código) não vale mais
        except OSError:
            pass
