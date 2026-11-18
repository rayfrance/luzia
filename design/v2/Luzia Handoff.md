# Luzia · handoff da direção "Lume"

Referências neste projeto: `Luzia Painel.dc.html` (protótipo navegável), `luzia-tokens.css` (tokens e componentes), `Luzia Guia de Voz.dc.html` (chat), `Luzia Direcoes.dc.html` (crítica e escolha).

## Direção em uma página

- **A luz é o estado.** Apagado = contorno; na fila = ponto lilás; em andamento = meio aceso; aceso = cheio com halo. Vale para centelha, nível, foco e toast.
- **Uma fonte de luz por tela.** Só a ação principal é laranja e tem halo. O resto fica na penumbra.
- **Cada cor, um sentido.** Laranja = luz própria e o ato de acender. Lilás = luz refletida e o que espera por você. Areia = nível conquistado e meta. Branco = navegação, seleção e ações neutras.
- **A conta a um clique.** Todo número com sublinhado pontilhado abre a explicação ("Por que 45 lm", "Ver a conta", "base e modelo").
- **Tom:** segunda pessoa, presente, frases de até 12 palavras. Sem cobrança, sem festa.

## Motion

| Momento | O que acontece | Duração | Curva |
|---|---|---|---|
| Troca de tela, gaveta, detalhe da entrega | sobe 8 px e aparece | 250 ms | ease-out |
| Hover em cartão de centelha | sobe 2 px | 150 ms | linear |
| Lúmens ganhos | o anel do próximo nível avança; toast com ponto aceso | 1200 ms | `--curva` |
| Centelha acesa | o orbe passa de meio para cheio e ganha halo; a borda do cartão acende | 1200 ms | `--curva` |
| Subida de nível | anel completo → orbe areia cresce de 0,82 a 1 e acende, uma vez | 1200 ms | `--curva` |
| `prefers-reduced-motion` | tudo vira troca instantânea de estado | 0 | — |

Nada pisca, repete ou fica em loop. Sem confete e sem som.

## Mudanças por arquivo

### `painel/logo.svg`
| Elemento | Mudança |
|---|---|
| arquivo inteiro | Trocar por duas metades de uma centelha de 4 pontas com arestas retas, `viewBox="0 0 64 64"`: `<polygon points="32,3 25,25 3,32 25,39 32,61" fill="#b9a2f2"/>` e `<polygon points="32,3 39,25 61,32 39,39 32,61" fill="#f08a3c"/>`. Sem degradê. No painel, cada metade recebe `filter: drop-shadow` da própria cor (ver protótipo); no favicon, sem filtro. |

### `painel/luzia.css`
| Elemento | Mudança |
|---|---|
| `:root` | Substituir pelo bloco de `luzia-tokens.css`. Mapa dos nomes antigos: `--superficie` → `--sup-2`, `--superficie-2` → `--sup-3`, `--luz` → `--propria`, `--luz-2` → `--propria-clara`, `--areia` → `--meta`, `--texto-2/3` → `--texto-3/4`. |
| `@font-face` | Novo. Empacotar `painel/fontes/HankenGrotesk-Variable.woff2` (licença OFL). Sem CDN. |
| `:focus-visible` | Contorno passa de laranja para `--texto` (laranja é só luz própria). |
| `.rail` | 208 px com texto → 88 px com ícone e rótulo de 12 px embaixo. Item ativo: fundo `--sup-3`, texto `--texto` (não mais laranja). |
| `@media (max-width: 960px)` `.rail` | Vira barra inferior fixa com os 5 itens (alvo 52 px). "Sair" vai para Ajustes. |
| `main` | `max-width: 1040px`, centralizado; `container-type: inline-size` no corpo para os `clamp(..cqw..)`. |
| `.btn.prim` | Dividir em `.btn.acender` (laranja com halo; só para acender, continuar, revisitar, subir, provar) e `.btn.neutro` (branco; salvar, aceitar, pedir proposta, copiar). Todos em pílula. |
| `.btn.ico` (copiar prompt) | Vira `.btn.sec` com o texto "Copiar prompt". |
| `.destaque` | Raio 28 px, `--brilho-destaque` vindo da direita, sem borda. |
| `.trilha`, `.trajetoria-linha`, `.feed` | Removidos de Hoje. A trajetória vira uma linha clicável no topo; os lúmens viram pílulas abaixo dos prismas. |
| `.avanco` | Substituir por `.centelha` + modificador de estado (`sugerida`, `na-fila`, `em-andamento`, `acesa`). |
| `.pilula.and`, `.pilula.fila` | Removidas dos cartões: o estado passa a ser `.orbe` + rótulo na primeira linha. |
| `.tipo`, `.tipo-chip` | Removidos dos cartões; o tipo é texto na linha de métrica. Ícones de tipo ficam só na gaveta, se desejado. |
| `.espectro`, `.faixa` | Substituir por `.niveis` (5 orbes). `.faixa.f1–f5` coloridas somem: nível feito é sempre `--nivel`. |
| `.barra-nivel` | Removida. O progresso do nível é o anel `.niveis i.proximo` (variáveis `--p` e `--r`). |
| `.prisma-card.pronta` | Borda `rgba(240,138,60,.6)` e halo no anel; sem `box-shadow` interno. |
| `.medidor` | Vira `.luz-barra` (14 px, parte própria com halo). |
| `.dim` | De linha com barra de 4 px para bloco 2×2: nome, nota grande, base. Sem nota: borda tracejada lilás e "Falta você explicar/defender". |
| `.leitura` | Sem a borda esquerda lilás. Texto em `--texto-2`; assinatura "Análise da Luzia · 12 nov · base e modelo" com `.conta-link`. |
| `.info-base::after` | Mantém o popover; âncora passa a ser o texto "base e modelo" em vez do ícone. |
| `.gaveta-corpo` | Largura 520 px, fundo `--sup-1`. |
| `.toast`, `.toast.celebra` | Pílula com ponto aceso. `celebra` e `@keyframes estourar` removidos; `.toast.refletida` para ganhos lilás. |
| `.brilho`, `@keyframes brilho` | Removidos; o ganho anima o anel (transição de `--p`/`--r`). |
| `.opcao.ativo` | Borda `--texto` e fundo `#241a26` (não mais laranja). |
| `.aviso` | Só para "nível pronto": orbe aceso, texto, botão `.acender`. `.aviso.fino` mantém para análises desatualizadas, com orbe lilás. |

### `painel/luzia.js`
| Função | Mudança |
|---|---|
| `cabecalho()` | Nav com rótulo sob o ícone; `aria-current="page"` no ativo. Selo de foco sai do trilho e vai para o topo de Hoje. |
| `telaHoje()` | Nova ordem: linha "Hoje · Júnior 3 → Plena · 2 de 6 níveis" (link para Trajetória) + foco → aviso de nível pronto → destaque → prismas → lúmens de hoje + "Ver N centelhas abertas". "Também abertas" sai. |
| `telaHoje()` destaque | Rótulo "Continue de onde parou" / "Próximo passo". À direita, o anel com o valor em lúmens e o link "Por que 45 lm" (abre a gaveta da centelha). Botões: "Continuar no {agente}" / "Acender no {agente}" + "Copiar prompt". |
| `trajetoriaHero()` | Removida. |
| `feed()` | Vira pílulas `+20 DDD · você dirigiu`; máximo 3; cada uma chama `abrirLumen(i)`. |
| `espectroPrisma()` | Renderiza `.niveis`: `feito` para k ≤ nível, `proximo` com `style="--p:..;--r:.."` para k = nível+1, `meta` na meta. `aria-label` mantido. O losango `sug` sai (a estimativa fica em Ajustes). |
| `barraNivel()` | Removida; `faltaNivel()` continua e alimenta o resumo: `91 de 150 lm · faltam 59 lm`. Mostrar no máximo 2 faltas. |
| `cartaoAvanco()` | Linha 1: orbe + estado (`Em andamento`, `Na fila`, `Sugerida · da triagem`, `Acesa · nota 3 de 4`). Linha 2: título. Rodapé: `Praticar · SQL · 20 min` e lúmens. Acesa com revisita: `Revisitar · vale +17 lm`. |
| `telaAvancos()` | Sem cabeçalhos de grupo: a ordem (em andamento, na fila, sugeridas, acesas) e a luz do cartão fazem o agrupamento. Segmentado em pílulas; `aria-pressed` mantido. |
| `abrirAvanco()` | Ordem: orbe + estado → título → por quê → métrica → botões → Passo a passo → "Por que N lm" (aberto por padrão) → "Descartar…". "Conceitos", "Onde olhar", "Ver prompt" e "Histórico" ficam recolhidos abaixo. |
| `abrirPrisma()` | "A conta do nível N": 4 linhas com orbe aceso/apagado (150 lm · 40% própria · 1 centelha acesa · o seu sim) e o valor atual. Depois centelhas, análise, evidência. |
| `abrirLumen()` | Número grande na cor da luz, título, texto, e a linha "Teto do dia: 20 de 40 lm passivos em DDD". |
| `cartaoEntrega()` | Resumo: título, fatos e prismas numa linha de texto (sem pílulas), `58% seu`, `.luz-barra`, "medido em P1 e P2 · faltam P3 e P4". Detalhe: grade 2×2 das dimensões + análise + "Provar P3 e P4". |
| `renderCardPedido()`, `renderCardDividir()` | Borda lilás, pílula "Proposta", `.niveis` da proposta, texto "+2 níveis na trajetória". Aceitar = `.btn.neutro`; Ajustar e Recusar = links. |
| `toast()` / `celebrar()` | `celebrar` chama `toast(texto, luz === 'refletida' ? 'refletida' : '')` e atualiza `--p`/`--r` do anel (a transição faz a animação). |
| novo `momentoSubida(prisma)` | Sobreposição em duas fases: confirmar ("Subir para o nível 3?" · Confirmar nível 3 / Ainda não) e resultado ("DDD está no nível 3" · Acender 3 centelhas de DDD / Fechar). Chamada por todo `data-subir`. Foco preso no diálogo; Esc = "Ainda não". |
| `telaAjustes()` | "Sair" entra no fim da tela no mobile. Provedor vira `<select>` (era grade de cartões). |

### `painel/index.html`
| Elemento | Mudança |
|---|---|
| `.marca` | Só a logo no trilho; "Luzia · sua líder técnica" fica no login. |
| `<aside class="rail">` | Remover `#selo`; manter `#sair`. |
| novo `<div id="subida" role="dialog" aria-modal="true" hidden>` | Recipiente do momento de subida. |
| `#toast` | Sem mudança estrutural. |

### Chat: `luzia/cli.py` e `comandos-chat/*.md`
| Onde | Mudança |
|---|---|
| linha de trajetória (`hoje`, `trajetoria`) | `Júnior 3  ▰▰▱▱▱▱  Plena` (uma faixa por nível) + linha `2 de 6 níveis · 201 lm · 70% própria`. Sai `━━◉──`. |
| `hoje` | Sai "Perto de subir". `+N lm hoje` só quando N > 0. Lista até 2 centelhas (em andamento, na fila) em duas linhas cada. |
| `trajetoria` | Duas linhas por prisma (nome + faixas + níveis; lm + o que falta). Sem centelhas, sem ritmo, "Sem análise" uma vez no fim. |
| `centelhas` | Padrão `--estado abertos`. Duas linhas por centelha, id no fim sem crase. Acima de 3, resumir: `○ mais 2 sugeridas`. |
| `entregas` | Duas linhas por entrega. Análise só em `entrega <id>`. |
| `registrar` | Abre com `✦ **+N lm de luz própria** · nota X de 4` ou `◐ Nota X de 4 · ainda não valeu lúmens`. Depois prisma, análise assinada. |
| `subir` | Antes do sim: conta em uma linha. Depois: `✦ **DDD · nível 3**` + faixas + dossiê. |
| `LUZIA_BOTOES` | `rotulo` = verbo + apelido (2–4 palavras, ≤ 48, sem "…"). Novo campo de apelido por centelha (`titulo_curto`, gerado junto com a centelha). `descricao` com números primeiro. |
| `LUZIA_PERGUNTA` | Fixas: "Próximo passo?", "Qual entrega?", "Sobe para o nível N?", "Onde fazer?", "Decide o pedido?". |
| bloco **Botões** de cada `comandos-chat/*.md` | Acrescentar as regras 4 e 6 do guia de voz à instrução da frase de contexto (segunda pessoa; diz por que agora; não lê os botões; sem cobrança nem festa). |
| centelha da sessão (hook / `foco`) | Formato fixo de 3 linhas + 2 botões; só depois que o agente termina. |
| linha de status | `{sinal} Luzia · {foco} · {n}/{total} níveis · {p}% própria`; variantes no guia. |

## Acessibilidade (conferir na implementação)

- Texto mínimo 13 px; `--texto-4` só em rótulos, nunca em corpo.
- Estado nunca só por cor: todo orbe vem com o rótulo escrito; a parte refletida é hachurada.
- Alvos de 44 px no mobile (nav 52 px).
- Foco visível branco em tudo; gaveta e subida prendem o foco e fecham com Esc.
- 375 px: tudo em uma coluna; o anel do destaque desce para baixo do texto.

## O que o protótipo simula e o que falta desenhar

- Simulado: dados fixos de exemplo; fila, descarte, filtros, pedidos (incluir e dividir), subida de nível (Tweak "momento"), mobile (Tweak "viewport"), login (Tweak "sessão").
- Não desenhado ainda: estado vazio de Entregas, formulário de "Ajustar" pedido, arquivados, análise desatualizada, tela do dossiê.
