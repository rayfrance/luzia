# Luzia v2 · centelhas e conversão (plano por etapas)

Aprovado pela Rayane em 18/11/2026. Regras: [docs/specs/2026-11-18-centelhas-conversao.md](../specs/2026-11-18-centelhas-conversao.md). Referência visual e de lógica: `design/v2/Luzia Painel.dc.html`.

## Decisões
- Repositório próprio (`C:\Repositorio\luzia`), histórico limpo, sem remoto nem push até pedido.
- Rubrica: nota 3 ou 4 converte a centelha inteira depois do sim da pessoa; 0 a 2 continua convertendo; sem revisita.
- Prompt que cita o conceito: a centelha vira própria direto; código do agente: vira refletida.
- Sem teto nem limite de captação: cada centelha muda de luz uma vez só.
- Migração: a Luzia propõe as centelhas apagadas de cada meta (pedido `propor_meta`), a pessoa aceita.
- Instalação ativa e banco real só mudam na última etapa, com backup e o sim da Rayane.

## Etapas
0. Novo repositório: pacote, docs e design copiados; caminhos do ai4good adaptados; varredura de privacidade; commit inicial. **Feito** (`fc877d8`).
1. Modelo de centelhas: esquema 4, estados de luz, valor fixo, `avaliar`/`confirmar`, progresso `luz`, reconhecimento por centelha nos hooks, dossiê; módulos periféricos, CLI, servidor e linha de status adaptados; mapeamento dos estados antigos e backup antes de subir do esquema 3.
2. Pedido `propor_meta` (o modelo propõe as centelhas da meta de cada prisma `a_propor`); testes de migração sobre banco sintético v3; ensaio a seco sobre uma cópia do banco real.
3. Textos do chat: `commands/*.md`, skills, `harness/REGRAS.md`, `docs/luzia-ux.md`; prompt da centelha com guia, onde e contexto da entrega; pedidos sem níveis.
3b. Hooks para a experiência: pesquisar os eventos atuais do Claude Code e propor (Stop, commit no PostToolUse, conversão em andamento no UserPromptSubmit, PreToolUse em foco, SubagentStop, PreCompact/SessionEnd); a Rayane escolhe.
4. Painel: tokens "Lume", telas do protótipo (Hoje, Trajetória, Centelhas, Entregas, Ajustes), gavetas, sobreposição de conquista, acessibilidade; conferido no navegador em 1440 e 375 px.
5. Entregas no loop: centelhas refletidas ligadas à entrega, P3/P4 pelas conversões, "Converter a luz desta entrega".
6. Virada: backup do `private/` real, migração numa cópia, conferência, reapontar hooks/linha de status/comandos com o sim; handoff em `docs/handoffs/`.

## Orquestração
Opus orienta e revisa; tarefas de contrato claro vão para Sonnet (ou Haiku quando triviais); núcleo do modelo, migração, painel e revisões ficam no Opus. Nenhum subagente recebe dados reais; dois agentes nunca editam o mesmo arquivo; suíte inteira e checagem no navegador são feitas pelo orquestrador; revisão de código ao fim de cada etapa.
