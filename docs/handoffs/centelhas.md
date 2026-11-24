# Handoff · Luzia v2 centelhas e conversão · atualizado em 24/11/2026

- Repositório: `C:\Repositorio\luzia`, branch `feature/centelhas`. Remoto privado `rayfrance/luzia` (padrão no GitHub: `feature/centelhas`, para o `marketplace add` instalar a versão nova). Commit publicado: `26fcb4f`.

## Teste ponta a ponta antes dos convites (24/11)
Instalação pelo GitHub numa configuração isolada do Claude Code (`CLAUDE_CONFIG_DIR` temporário), repositório sintético Python, triagem real com Gemini, loop pela CLI (agente Sonnet), hooks e linha de status (agente Sonnet), guias (agente Haiku) e painel no navegador.

Corrigido (sem commit ainda), cada um com teste:
- Triagem impunha 11 prismas fixos (.NET, Razor, React…); agora escolhe 6 a 10 pela meta e pelas evidências, com Programação Agêntica sempre (`planner.py`).
- Painel: Testar salva antes; "Coletadas hoje" sem as apagadas; "1 centelha é sua".
- Base da triagem cita só as fontes dadas; aviso AFC do SDK do Gemini não vaza no chat.
- CLI: nota fora de 0–4 não confirma mais; id inexistente e comando sem id com mensagem certa; `acender` sem prisma pergunta; nota baixa diz o que falta pela rubrica.
- Hooks: sintaxe (`def`, `class`, `commit`) não cria centelha; palavra solta do nome do prisma não acende; "value object" casa com "ValueObject"; pasta irmã não passa por autorizada; evento que não é objeto é ignorado.
- Guias: foco em Ajustes › Foco, pypdf opcional separado, "senioridade", botões condicionais explicados.

## Avanço com alvo fixo (24/11, decisão da Rayane; versão 0.4.1, esquema 5)
- Problema: acender centelhas aumentava o total e baixava o % (23% → 11%). Decisão: o avanço da trajetória é uma medida separada da composição da luz, e centelhas são oportunidades, nunca baixam o avanço.
- Avanço (`pct`) = min(própria, `alvo_lm`) ÷ `alvo_lm` por prisma; trajetória = soma do contado ÷ soma dos alvos. `prisma.alvo_lm` é fixado pela primeira sincronização ou pela triagem (`jogo.fixar_alvos`, `refazer=True` na triagem); prisma sem centelha usa `ALVO_PADRAO` (180).
- Composição (`luz_pct`) = própria ÷ (própria + refletida + convertendo).
- A triagem chama `cli.completar_meta`: prismas com menos de 3 centelhas da meta ganham 3 (chamadas em paralelo), depois os alvos são fixados. Triagem real: 6 prismas com 3 a 5 centelhas, alvos de 153 a 360 lm, 29 s.
- Verificado: converter dá 0% → 28% em Python e 5% na trajetória; acender 3 centelhas novas mantém 28% e 5% (oportunidades 3 → 6). Painel em 1440 e 375 px; 468 testes passam.
- Para decidir: a barra segmentada de cada prisma mostra as centelhas (um segmento por centelha, largura pelo lm), então o preenchimento não bate com o % de avanço (Python: ~16% da barra, 28% no número).

Fica para decidir ou para depois:
- Pedidos de mudança da Trajetória (`cli.py` pedido) ainda falam em nível/meta (Etapa 3).
- SessionStart logo após a triagem fica em silêncio (nada refletido nem na fila).
- Hooks levam ~300–500 ms (Python frio); abaixo do timeout, mas soma a cada Edit.
- Nome curto corta "Arquitetura de Sof…" (limite de 20 caracteres).
- Plano: [docs/plans/2026-11-18-centelhas-conversao.md](../plans/2026-11-18-centelhas-conversao.md). Spec: [docs/specs/2026-11-18-centelhas-conversao.md](../specs/2026-11-18-centelhas-conversao.md).
- A Luzia instalada no dia a dia da Rayane e o banco real continuam em `C:\Repositorio\ai4good-sem2\code\luzia` (intocados).

## Objetivo desta rodada (23/11)
Pacote para testadores usarem a partir de quarta, 25/11: núcleo de centelhas, painel v2, textos do chat, instalação pelo marketplace do Claude Code e guias (`docs/teste/`). Decisões da Rayane: uso real separado do teste controlado do sem3; cada testador usa a própria chave Gemini; distribuição por GitHub privado com convite; ficam para depois os hooks novos (3b), o pedido `propor_meta`, a migração do banco dela (2 e 6) e as entregas no loop (5).

## Feito (sem commit)
- Etapa 1 (núcleo de luz, periferia, CLI, servidor, linha de status), com a revisão da Etapa 1 aplicada.
- Textos do chat sem níveis (`commands/*`, skills, `harness/REGRAS.md`, `docs/luzia-ux.md`); `subir.md` removido; `converter.md`, `confirmar.md`, `configurar.md` e `diagnostico.md` criados.
- Instalação pelo marketplace: `luzia/lz.py` (lançador que funciona na pasta de cache com nome de versão); dados em `~/.luzia` (ou `luzia/private` se existir, ou `LUZIA_PRIVATE`); chave em `<dados>/.env`; `luzia/requirements.txt`; versão 0.4.0; `claude plugin validate` OK.
- Primeiro uso: `configurar` grava `entrada.json` e autoriza o repositório no foco; `/luzia:triage` entrevista a pessoa antes de rodar; `/api/estado` vazio traz o modelo, e o painel mostra boas-vindas com a configuração do modelo.
- Painel v2 (`luzia/painel/*`): Hoje, Trajetória, Centelhas, Entregas, Ajustes, gavetas e a sobreposição "Acender luz própria". Conferido no navegador com dados sintéticos em 1440 px e 375 px, sem erros de console; o loop converter → confirmar → % atualizado funciona; boas-vindas conferidas numa cópia de cache.
- Guias: `docs/teste/INSTALAR.md`, `ROTEIRO.md` e `AVALIACAO.md`; README com "Para testadores".
- Varredura de privacidade limpa (termos, domínio, e-mails, caminhos pessoais).

## Pendências
- Commit das correções do teste de 24/11 e push, com o ok da Rayane; depois, convites aos testadores.
- Etapas 2, 3b, 5 e 6 do plano.
