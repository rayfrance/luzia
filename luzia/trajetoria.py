"""Trajetória da pessoa no banco: prismas, perfil e versões da trajetória.

Um prisma é uma skill da trajetória (nome, palavras para o observador). O progresso dele é a luz própria das
centelhas (`jogo.luz`), não um nível. As colunas `prisma.nivel` e `prisma.meta` ficam só como dado de partida da
triagem, e `nivel_registro` é histórico somente de leitura do modelo anterior (`historico_subidas`).
Prisma arquivado sai da trajetória, mas os lúmens dele continuam em todos os totais.

As leituras abrem o banco por `abrir()`; as escritas recebem a conexão e usam `banco.transacao`.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from . import arquivos, banco


def agora() -> str:
    return datetime.now().isoformat(timespec='seconds')


@contextmanager
def abrir(espera_ms: int | None = None) -> Iterator[sqlite3.Connection]:
    """Conexão de curta duração para quem só precisa ler (ou fazer uma escrita).

    `espera_ms` encurta a espera (caminho quente do hook: use `banco.ESPERA_CURTA_MS`).
    """
    con = banco.conectar() if espera_ms is None else banco.conectar(espera_ms=espera_ms)
    try:
        yield con
    finally:
        con.close()


# ------------------------------------------------------------------ perfil
def perfil_ler(con: sqlite3.Connection, chave: str, padrao=None):
    linha = con.execute('SELECT valor_json FROM perfil WHERE chave = ?', (chave,)).fetchone()
    if linha is None:
        return padrao
    try:
        return json.loads(linha['valor_json'])
    except ValueError:
        return padrao


def perfil_gravar(con: sqlite3.Connection, chave: str, valor) -> None:
    """Grava (ou troca) um valor do perfil; chamar dentro de `banco.transacao`."""
    con.execute('INSERT INTO perfil (chave, valor_json) VALUES (?, ?) '
                'ON CONFLICT (chave) DO UPDATE SET valor_json = excluded.valor_json',
                (chave, json.dumps(valor, ensure_ascii=False)))


# ------------------------------------------------------------------ prismas
def prismas(con: sqlite3.Connection, incluir_arquivados: bool = False) -> list[dict]:
    """Prismas na ordem em que entraram. Chaves: nome, nivel e meta (dado de partida), estado, palavras, origem."""
    sql = 'SELECT * FROM prisma' + ('' if incluir_arquivados else " WHERE estado = 'ativo'") + ' ORDER BY rowid'
    out = []
    for r in con.execute(sql):
        try:
            palavras = json.loads(r['palavras_json'] or '[]')
        except ValueError:
            palavras = []
        out.append({'nome': r['nome'], 'nivel': int(r['nivel'] or 0),
                    'meta': int(r['meta'] if r['meta'] is not None else 5),
                    'estado': r['estado'], 'palavras': palavras, 'origem': r['origem']})
    return out


def estado(espera_ms: int | None = None) -> dict:
    """Estado vivo da carreira (plano e resto da última triagem), do `perfil`; o arquivo só vale se o banco não tem plano."""
    if not arquivos.ESTADO.exists():
        arquivos.ler_estado()  # primeira vez: traz a foto do seminário para a pasta privada, antes de o banco migrar
    with abrir(espera_ms) as con:
        plano_db = perfil_ler(con, 'plano')
        if plano_db is None:
            return arquivos.ler_estado()
        return {**(perfil_ler(con, 'estado_legado', {}) or {}), 'plano': plano_db}


def plano(espera_ms: int | None = None) -> dict:
    return estado(espera_ms).get('plano', {})


def historico_subidas(con: sqlite3.Connection) -> list[dict]:
    """Níveis conquistados no modelo anterior (somente leitura; aparece no dossiê como histórico), no formato antigo."""
    return [{'quando': r['quando'], 'skill': r['prisma'], 'para': r['para'], 'lm': r['lm'] or 0,
             'luz_propria': int(r['luz_propria'] or 0)}
            for r in con.execute("SELECT * FROM nivel_registro WHERE origem = 'conquistado' ORDER BY quando, id")]


# ------------------------------------------------------------------ versões
def acrescentar_versao(con: sqlite3.Connection, origem: str, pedido_id: int | None = None) -> int:
    """Como `nova_versao`, dentro de uma transação já aberta (quem chama confirma ou desfaz)."""
    foto = [{k: p[k] for k in ('nome', 'nivel', 'meta', 'estado', 'origem', 'palavras')} for p in prismas(con)]
    numero = (con.execute('SELECT MAX(numero) FROM trajetoria_versao').fetchone()[0] or 0) + 1
    con.execute('INSERT INTO trajetoria_versao (numero, criada_em, origem, pedido_id, foto_json) VALUES (?, ?, ?, ?, ?)',
                (numero, agora(), origem, pedido_id, json.dumps({'prismas': foto}, ensure_ascii=False)))
    return numero


def nova_versao(con: sqlite3.Connection, origem: str, pedido_id: int | None = None) -> int:
    """Foto dos prismas ativos e metas, com o próximo número; devolve o número. Só acrescenta."""
    with banco.transacao(con):
        return acrescentar_versao(con, origem, pedido_id)


def versoes(con: sqlite3.Connection) -> list[dict]:
    return [{'numero': r['numero'], 'criada_em': r['criada_em'], 'origem': r['origem'], 'pedido_id': r['pedido_id'],
             **json.loads(r['foto_json'])} for r in con.execute('SELECT * FROM trajetoria_versao ORDER BY numero')]


# ------------------------------------------------------------------ totais
def lumens_totais(con: sqlite3.Connection) -> tuple[int, int]:
    """(lm total, lm de luz própria) de TODOS os lúmens, inclusive os de prismas arquivados."""
    total, propria = con.execute("SELECT COALESCE(SUM(lm), 0), COALESCE(SUM(CASE WHEN luz = 'propria' THEN lm END), 0) "
                                 'FROM lumen').fetchone()
    return int(total), int(propria)


def sincronizar_prismas(con: sqlite3.Connection, skills: list[dict]) -> bool:
    """Skills de uma triagem que o banco não conhece viram prismas ativos (origem 'triagem'); as conhecidas ficam como estão.

    Nível = autoavaliação ou sugestão da Luzia; meta = `alvo`. Chamar dentro de `banco.transacao`. Devolve True se criou algum.
    """
    criou = False
    for s in skills:
        nome = s.get('nome') if isinstance(s, dict) else None
        if not isinstance(nome, str) or not nome:
            continue
        if con.execute('SELECT 1 FROM prisma WHERE nome = ?', (nome,)).fetchone():
            continue
        nivel = s.get('autoavaliacao') if s.get('autoavaliacao') is not None else s.get('luzia_sugere', 0)
        con.execute("INSERT INTO prisma (nome, palavras_json, nivel, meta, estado, origem, criado_em) "
                    "VALUES (?, ?, ?, ?, 'ativo', 'triagem', ?)",
                    (nome, json.dumps(list(s.get('palavras_chave') or []), ensure_ascii=False), int(nivel or 0),
                     int(s.get('alvo', 5)), agora()))
        criou = True
    return criou
