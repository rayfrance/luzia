# Handoff · Luzia v2 centelhas e conversão · atualizado em 24/11/2026

- Repositório: `C:\Repositorio\luzia`, branch `feature/centelhas`. Remoto privado `rayfrance/luzia` (padrão no GitHub: `feature/centelhas`, para o `marketplace add` instalar a versão nova). Último commit publicado: `3674c84` (0.4.1).
- Plano: [docs/plans/2026-11-18-centelhas-conversao.md](../plans/2026-11-18-centelhas-conversao.md). Spec: [docs/specs/2026-11-18-centelhas-conversao.md](../specs/2026-11-18-centelhas-conversao.md).
- A Luzia instalada no dia a dia da Rayane e o banco real continuam em `C:\Repositorio\ai4good-sem2\code\luzia` (intocados).

## Rodada 3 (24/11, noite): teste geral antes dos convites (0.4.3)
Reinstalação pelo GitHub numa configuração isolada, dados zerados (só a chave mantida), triagem real e quatro testadores (Sonnet: CLI, painel/tutorial, hooks; Haiku: guias). Corrigido, cada item com teste:
- **Gemini:** o reserva `gemini-2.5-flash` foi aposentado para contas novas (404) e escondia um 503 de sobrecarga do `gemini-3.5-flash-lite`. Agora: tenta o escolhido de novo em erro passageiro, vai às reservas atuais (`gemini-3.1-flash-lite`, `gemini-3.5-flash`) em sobrecarga, mostra o erro real em português; pausas maiores para limite por minuto; sugestão do painel sem o 2.5.
- **Triagem:** pede 3 centelhas por skill na própria resposta; completar a meta com no máximo 2 chamadas simultâneas; avisa quando algum prisma fica com menos de 3.
- **Hooks:** palavras de toda conversa ("agente", "prompt", "contexto", "refactor"…) não casam nem criam centelha (antes, "agente" dava +36 lm a qualquer prompt).
- **Pedidos:** incluir prisma que já está na trajetória é recusado (duplicava centelhas); pergunta certa quando não há pedido a decidir; texto do alvo estimado.
- **Painel:** botões do tutorial sempre visíveis no celular (só o texto rola); exemplo do passo 4 com o que o cartão mostra; abas de Centelhas ligadas aos estados; foco volta a quem abriu a gaveta; memória rotulada em Ajustes.
- **Guias:** "chave FALTANDO" esperada no diagnóstico, GitHub CLI e Python no Windows, P1–P4 explicados, palavras iguais às da tela, sem gênero, privacidade precisa.
Observado e mantido: incluir um prisma baixa o "% do caminho" (o alvo total cresce; a saída explica); o modelo às vezes escreve "nível Pleno" num texto de centelha apesar da regra no prompt.

## Rodada 2 (24/11, tarde): itens do handoff, tutorial e testes orquestrados
Feito (sem commit ainda), cada item com teste:
- **Barra do prisma** acompanha o avanço até o alvo (cartões do Hoje, Trajetória e gaveta); o destaque do Próximo passo continua com o mapa de centelhas.
- **Nome curto** até 24 caracteres, cortando em palavra inteira ("Arquitetura de Software" inteiro).
- **Pedidos sem níveis** (agente Sonnet): proposta com palavras-chave, centelhas iniciais e quanto o alvo cresce; `pedido ajustar <id> --palavras 'a, b'` ou `--motivo '...'`; `PEDIDO_SCHEMA` sem nível/meta; aceitar mostra o alvo real do prisma novo e o avanço antes → depois; arquivar/reativar só de prisma que existe; painel (`/api/pedido` ajustar) com `palavras` e `nota`.
- **Hooks** (agente Sonnet): `porteiro.py` decide antes dos imports caros (não autorizado ~50 ms acima do Python vazio; autorizado ~200 ms acima); SessionStart logo depois da triagem pede ao agente uma linha "N centelhas na sua meta para acender" enquanto não há luz própria.
- **Tutorial de primeiro uso** no painel (8 passos com destaque sobre a tela real, trilha de orbes que vira luz própria, teclado, celular); abre sozinho uma vez depois da triagem (`perfil.tutorial_visto_em`, `POST /api/tutorial`) e em Ajustes › Tutorial.
- **Achados da rodada de testes** (Sonnet: CLI, painel, hooks; Haiku: guias): comando desconhecido em português com botões; dossiê formal contando contra o alvo; "nível" fora dos prompts do modelo; vazio orientado em Centelhas › Para converter; "Lacuna no prisma … quando ela nasceu"; botões do tutorial com 44 px; gaveta com nome acessível; textos do tutorial com lm, Convertendo e P1–P4 (as quatro dimensões de `propriedade.COMO_E_MEDIDO`); `docs/luzia-ux.md` atualizado; guias citam o tutorial e o formulário pergunta sobre ele.

Fica para depois (baixo impacto, anotado pelos testadores):
- O alvo estimado na proposta de incluir pode diferir ~10% do alvo real (a saída do aceitar mostra o real).
- Fechar a gaveta ou o tutorial devolve o foco ao `<body>`, não ao elemento que abriu.
- A linha de status em "fora de foco" aparece também em pasta não autorizada (comportamento antigo).
- O hash da URL não acompanha a tela.
- Etapas 2, 3b, 5 e 6 do plano.

## Rodada 1 (24/11, manhã): teste ponta a ponta antes dos convites
Instalação pelo GitHub numa configuração isolada (`CLAUDE_CONFIG_DIR` temporário), repositório sintético Python, triagem real com Gemini. Corrigido e publicado em `2772d88`: prismas pela meta e evidências (sem a stack fixa .NET), Testar salva antes, nota 0–4 validada, ruído dos hooks, pasta irmã, base da triagem, aviso AFC, guias.

## Avanço com alvo fixo (0.4.1, esquema 5, publicado em `3674c84`)
- Avanço (`pct`) = min(própria, `alvo_lm`) ÷ `alvo_lm` por prisma; trajetória = soma ÷ soma. `prisma.alvo_lm` fixado na primeira sincronização ou pela triagem (`jogo.fixar_alvos`); sem centelha, `ALVO_PADRAO` (180). Composição (`luz_pct`) = própria ÷ luz coletada.
- A triagem completa cada prisma com pelo menos 3 centelhas (`cli.completar_meta`) e fixa os alvos.

## Loop de testes orquestrados e liberação (0.4.4, 25–26/11, publicado em `b9c92a0`)
- 14 rodadas com 4 testadores (Sonnet: chat, painel, hooks; Haiku: guias contra o código), cada uma do zero. Critério: só defeitos reproduzidos ou conferidos no código contam. A Rayane encerrou o loop na rodada 14 para liberar a versão; a jornada no chat dessa rodada passou sem defeito bloqueante (painel, hooks e guias foram interrompidos).
- Principais mudanças: aviso de meta curta no chat e no painel, Testar rápido (uma tentativa, 30 s), pedido sem proposta oferece "Gerar a proposta", ritmo com tempo previsto e prazo dado, menos ruído nos hooks, modo "em silêncio" calado, linha de status fechada sem cwd, mascaramento de tickets PROJ-123 e domínios sem http, guias precisos sobre privacidade.
- `docs/teste/AVALIACAO.md` virou questionário em escala (problema, eficácia, uso, viabilidade, confiança), com nota para a análise; `ROTEIRO.md` abre com o perfil de quem deve testar.
- Repositório tornado público em 26/11 (decisão da Rayane, ciente de que o e-mail pessoal fica visível nos commits). Instalação conferida sem login: marketplace, plugin 0.4.4 e diagnóstico.

## Formulário e conversão na espera (27/11)
- A avaliação é um Google Forms na conta da Rayane, criado por `docs/teste/formulario.gs` (Apps Script) e ligado a uma planilha de respostas; abre sem login. `AVALIACAO.md` ficou como versão em texto. Sem a seção de problemas técnicos (virou a pergunta aberta G5); entraram A6 (quanto a pessoa espera o agente), E7 (a conversão aproveitou a espera) e E8 (invertido: a Luzia tomou tempo).
- Ideia central registrada: converter centelhas enquanto o agente executa tarefas longas, numa segunda sessão, para a Luzia não parecer tempo a mais. Está no roteiro (seção "Quando converter"), no README, no passo "O próximo passo" do tutorial e nas instruções da mentora.

## Pendências
- Mandar os convites (mensagem com data final a definir).
- Nome completo da autora nos manifestos: decisão em aberto.
- Sugestões não bloqueantes dos testadores: o dossiê chama lm de "pontos de evidência"; o texto da P1 (geral) soa estranho em entregas de documentação; a contagem de "Atualizar N análises" varia entre telas.
- Dados de teste em `~/.luzia` (com a chave dela) e pastas `cfg-teste-luzia`, `repo-teste-luzia` e `luzia-dados-hooks` em `%TEMP%\claude`: apagar quando terminar.
