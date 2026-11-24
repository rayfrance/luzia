# Handoff · Luzia v2 centelhas e conversão · atualizado em 23/11/2026

- Repositório: `C:\Repositorio\luzia`, branch `feature/centelhas` (base `develop` = `main` = `fc877d8`). Sem remoto ainda.
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
- Commit (`feat: centelha light model, v2 panel and tester package`) depois do ok da Rayane; criar o repositório privado `rayfrance/luzia`, push e convites, também com o ok dela.
- Triagem real ponta a ponta com uma chave (não testada nesta rodada: exige chave do modelo).
- Etapas 2, 3b, 5 e 6 do plano.
