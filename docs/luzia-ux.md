# Luzia · desenho da experiência (gamificação e trajetória)

Decidido com a Rayane em 12/11/2026 (persistência, trajetória, prismas e leituras com base adicionadas após a revisão do mesmo dia). A metáfora é a tese: o código que o agente produz e você não domina é **luz refletida**; quando você explica, decide e defende, a luz passa a ser **própria**. O modelo atual (centelhas e conversão, 18/11/2026) está em `docs/specs/2026-11-18-centelhas-conversao.md`.

## Vocabulário
Nome real primeiro; a metáfora de luz só onde explica algo.

- **Trajetória**: o caminho do rótulo de carreira atual até a meta (ex.: Júnior 3 até Plena), versionado e ajustável por pedido formal de mudança.
- **Prisma (skill)**: **uma única habilidade** da trajetória (ex.: *Domain-Driven Design (DDD)*, *SQL*, *React*), nunca um nome que junta assuntos. Nos rótulos aparece só o nome, sem "Prisma" na frente. Cada prisma mostra uma barra: o avanço até o alvo da meta.
- **Dividir um prisma composto** (`dividir "<prisma>"`, `dividir-todos` ou "Separar em habilidades" no painel): pedido de mudança formal, sem modelo. Cada habilidade herda a meta do antigo; cada centelha vai para a habilidade que ela trata, **com a luz que já tinha** (você confere, renomeia uma parte ou move uma centelha antes de aceitar); o antigo é arquivado com tudo o que acumulou.
- **Centelha**: uma oportunidade de 5 a 30 min ligada a um conceito de um prisma. Nasce na sessão, na triagem, numa entrega ou num pedido de mudança. A origem aparece numa etiqueta curta: *da sessão*, *da triagem*, *da entrega*. Tipos: `praticar`, `explicar`, `estudar`, `explorar`. (No código e no banco, o nome continua `avanco`.) Toda centelha está num de quatro estados:
  - **Por acender** (`apagada`): a Luzia a captou; ninguém aplicou nem explicou o conceito ainda.
  - **Luz refletida** (`refletida`): o agente aplicou o conceito; a luz ainda é dele. Esta é a que você pode converter.
  - **Convertendo** (`convertendo`): você começou a explicar, e a Luzia conduz com uma pergunta por vez.
  - **Luz própria** (`propria`): você explicou, a Luzia confirmou e você disse sim; ou você dirigiu o conceito no seu próprio prompt (centelhas do chat).
  - Há também **descartada**: sai de todas as contas e pode ser restaurada.
- **Converter**: transformar luz refletida em luz própria. A Luzia pergunta, você explica, ela confirma (nota 3 ou 4) e só com o seu sim a luz muda.
- **Lúmen (lm)**: o valor de uma centelha, fixo desde que ela entra no catálogo.
- **Luz própria / Luz refletida**: a luz própria é o que você dirigiu, explicou e confirmou; a refletida é o que o agente aplicou sozinho.
- **Propriedade** (fora do jogo, nas Entregas): quanto de uma **entrega** é seu, medido de P1 a P4 com base visível.
- **Foco**: a Luzia observando a sessão com intenção (*Em foco*, *Em silêncio* ou *Fora de foco*).
- **Cartão da sessão**: no chat, quando a Luzia em foco vê o agente aplicar um conceito, aparece `✦ Centelha da sessão · DDD · 45 lm para converter` com os botões "Converter agora" e "Depois".
- **Análise da Luzia**: todo texto de IA (sobre prisma, entrega ou pedido), sempre com base, modelo e data.

> Nos **dossiês e textos formais** (para líder ou PDI), a Luzia usa linguagem formal ("skill", "ação", "pontos de evidência", "autoria própria"), sem o vocabulário do jogo.

## Progresso sem calendário
- O **avanço** de um prisma é a luz própria dele, até o **alvo**, sobre o alvo. O alvo é o lm das centelhas da meta quando ela é definida (na triagem, que completa cada prisma com pelo menos 3 centelhas, ou ao mudar a meta) e fica fixo: acender centelhas novas cria oportunidades e capturar luz refletida não mexe nele, então o avanço só sobe. Ao lado aparece a **composição**: quanto da luz já coletada (própria + refletida + convertendo) é sua; as apagadas ficam de fora. Não há níveis.
- A trajetória soma os prismas ativos. O rótulo de carreira (ex.: Júnior 3 → Plena) vem do plano.
- A luz só muda com o seu sim: a Luzia confirma o entendimento, você decide acender.
- O **prazo** declarado apenas calibra o ritmo sugerido. Não cria datas obrigatórias nem trava o progresso.
- Em 1/3, 2/3 e 100% do lm próprio da trajetória, a Luzia gera um **dossiê de evidências** local (centelhas próprias com nota, onde e data, e os pedidos de mudança aceitos). O que se conquistou no modelo anterior aparece como "Histórico (modelo anterior)".
- Quando um prisma fica sem centelha por converter ou por acender, a Luzia oferece **acender 3 centelhas novas** dele (`/luzia:acender`).

## Sempre uma ação (paridade chat × painel)
Toda saída da Luzia termina em botões (`LUZIA_BOTOES` no CLI e opções equivalentes no painel): continuar uma conversão, confirmar uma luz própria, converter uma luz refletida, acender 3 centelhas, responder ao pedido de mudança ou abrir um filtro. `/luzia:hoje` é o ponto de partida. Toda ação existe no chat e no painel (`Hoje · Trajetória · Centelhas · Entregas · Ajustes`); o painel nunca é obrigatório.

## Lúmens
O valor de uma centelha (`valor_lm`) é calculado **uma vez**, quando ela entra no catálogo, e nunca muda. Assim o percentual não pula sozinho. A conta fica guardada e visível.
- **Profundidade do conceito:** base do tipo (`estudar` 20, `praticar` 20, `explicar` 15, `explorar` 10) mais os minutos (5 a 30).
- **Lacuna no prisma:** até 60% da profundidade, proporcional ao quanto do prisma ainda não é próprio naquele momento.
- **Peso para a meta:** 40% da profundidade se o prisma é um dos 2 com menor percentual, 20% nos outros, 0 se o prisma está em 100%.
- Total entre 10 e 100 lm. Exemplos: uma explicação de 5 min que nasce do chat vale 40 lm; uma prática de 15 min, 70 lm.
- As parcelas seguem a profundidade para que um conceito citado de passagem não valha quase o mesmo que uma prática longa.

**A conversão.** Rubrica 0–4 sobre a sua explicação: `4` e `3` confirmam o entendimento; `0` a `2` pedem outra tentativa, com uma dica do que faltou. A centelha continua convertendo e vale os mesmos lm. Só com nota 3 ou 4 e o seu sim a centelha vira luz própria.

## Passivos: o foco no Claude Code
O foco reconhece por **centelha**, não por prisma, com as palavras de cada uma. Não há teto diário nem limite de captação: o lm é da centelha e **cada centelha muda de luz uma vez**, então repetir não infla o progresso.
- O **agente** aplica o conceito (`PostToolUse`): a centelha por acender vira **luz refletida**. Sem centelha que case, nasce uma de luz refletida, de origem *chat*. Em foco, aparece o cartão com "Converter agora" e "Depois".
- **Você** cita o conceito no seu prompt (`UserPromptSubmit`): uma centelha **do chat** vira **luz própria** direto; sem centelha que case, nasce uma de luz própria. As centelhas da meta e as que já estão convertendo não mudam pelo prompt: citar uma palavra não prova o entendimento, então elas pedem a conversa com a Luzia.
- Um aviso por centelha por sessão, só para não repetir. Apenas fatos mascarados (horário, prisma, extensão, modo) são salvos; nunca código bruto nem texto do prompt.

## Centelhas: estados e filtros combináveis
- Fluxo: **Por acender** → **Luz refletida** → **Convertendo** → **Luz própria**. Uma centelha por acender também pode ir direto a convertendo, e a de luz própria nunca volta. **Descartada** (motivo *"não faz sentido para mim"*, *"já domino"* ou *"agora não"*) vale para o que ainda não é próprio e pode ser restaurada.
- Filtros por estado: **Para converter** (luz refletida e convertendo; é o padrão), **Próprias**, **Por acender** e **Todas**. Combinam com **prisma** e **tipo**.
- No painel: as abas com contagem e menus de prisma e tipo. No chat: `centelhas [--estado converter|propria|apagada|todas] [--prisma P] [--tipo T]`.

## Trajetória flexível (pedido de mudança)
Qualquer ajuste na trajetória — **incluir prisma**, **mudar meta**, **arquivar** ou **reativar** — segue um fluxo formal no chat ou no painel:
1. A pessoa abre o pedido informando o motivo.
2. Para inclusões e mudanças de meta, a Luzia analisa contra a meta final e propõe a meta, as palavras-chave, 3 centelhas iniciais (por acender) e a Análise da Luzia.
3. A pessoa escolhe **Aceitar**, **Ajustar** (alterando a meta ou as partes para nova proposta, registrado no histórico do pedido) ou **Recusar**.
4. Ao aceitar, nasce uma nova **versão imutável da trajetória**; nenhum progresso anterior (lúmens e centelhas, com a luz que cada uma tem) é perdido. Prismas arquivados preservam tudo e podem ser reativados.

## Entregas (detecção local no git + P1–P4)
- Rastreia entregas localmente nos repositórios autorizados (apenas commits da pessoa): merge commits de PR (`Merged PR ...`, `Merge pull request #...`), commits agrupados por id de ticket (`AB#...`, `#...`) ou commits isolados.
- Janela inicial de **90 dias** (ampliável pelo chat ou painel); atualizações seguintes são incrementais.
- Cada entrega exibe fatos medidos (período, duração em dias, nº de commits, arquivos, linhas, áreas), **prismas atravessados** com termos detectados, **lúmens ligados** na janela, **centelhas feitas e que ajudam**, **propriedade P1–P4** (com P2 calculado sobre o total da entrega) e a **Análise da Luzia**. No painel o cartão fica recolhido (`58% seu`, um medidor e `Ver detalhe`). Títulos e mensagens são os reais, com os números de PR/ticket, e aparecem só para quem abriu o painel pelo próprio agente e no chat da própria pessoa; hashes de commit nunca saem do banco.

## Análises com base (sem texto solto)
- Toda Análise da Luzia (por **prisma**, por **entrega** ou por **pedido de mudança**) armazena no SQLite os fatos usados, o hash da base, o modelo e a data. No painel: o texto e a assinatura `Luzia · 12 nov` com um ícone de informação (focável) que mostra base e modelo; no chat: `texto _— Análise da Luzia, 12 nov · base: … · modelo_`.
- Análises desatualizadas são atualizadas em lote apenas quando o hash da base muda ou sob pedido explícito (`analises`). Sem modelo ou sem base suficiente, a interface exibe apenas os fatos medidos e diz `Sem análise`.

## Entrada no painel e privacidade
- **Sem senha: a entrada vem do seu agente.** `/luzia:career-map` (ou o botão "Abrir painel", ou `LUZIA career-map` em qualquer agente) abre o painel já logado. Aberto direto no navegador sem sessão, o painel só mostra "Abra pelo seu agente" e não busca nenhum dado.
- **Você permanece logada.** A sessão dura 30 dias sem uso e renova a cada uso; reiniciar o computador ou o painel não derruba. O que o painel faz sozinho (atualizar a tela, análises automáticas) não conta como uso.
- **Sair.** O botão **Sair** encerra a sessão daquele navegador; `/luzia:acesso` no chat mostra as sessões abertas e encerra todas, depois do seu sim.
- **Dados visíveis.** Para você, logada, nada é mascarado na tela: empresa, módulos, clientes, colegas e números de ticket/PR aparecem como são. Arquivos versionados nunca recebem esses dados.
- **Envio ao modelo.** Por padrão vai real. Em **Ajustes > O que vai para o modelo** (ou `privacidade mascarar-modelo on|off` no chat) você liga o mascaramento antes de cada chamada.

## Fora do desenho (por decisão)
Sequência de dias (streaks), nomes fantasiosos fora do vocabulário acima e recompensas sem evidência.
