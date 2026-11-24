# Luzia v2 · centelhas e conversão (spec)

Decidido com a Rayane em 18/11/2026. Referência visual e de lógica: `design/v2/Luzia Painel.dc.html` (script no fim do arquivo). Substitui os níveis 0–5 de cada prisma.

## O essencial
- ~~O progresso de um prisma é lm das centelhas próprias ÷ lm de todas as centelhas da meta.~~ Revisto em 24/11/2026, depois do teste ponta a ponta (acender centelhas fazia o % cair): duas medidas separadas.
  - **Avanço** (`pct`): min(lm próprio, alvo) ÷ alvo, por prisma; na trajetória, a soma do contado ÷ a soma dos alvos. O alvo (`prisma.alvo_lm`, esquema 5) é o lm das centelhas da meta (sem as do chat) quando a meta é definida; a triagem completa cada prisma com pelo menos 3 centelhas e fixa os alvos de novo; prisma sem centelha ganha `ALVO_PADRAO` (180 lm). Acender, capturar luz refletida e descartar não mudam o alvo, então o avanço só sobe. O teto por prisma faz chegar à meta exigir todos os prismas.
  - **Composição** (`luz_pct`): própria ÷ (própria + refletida + convertendo). Pode cair quando o agente aplica um conceito por você (é o alerta da luz refletida). Apagadas são oportunidades e ficam de fora.
  - Marcos do dossiê (1/3, 2/3, 100%) e o ritmo seguem o avanço.
- A trajetória soma os prismas ativos. O rótulo de carreira ("Júnior 3 → Plena") continua vindo do plano.
- O loop central é **converter luz refletida em própria**: a Luzia guia, a pessoa explica, a Luzia confirma, a pessoa dá o sim.
- Sem teto nem limite de captação: o lm é da centelha e cada centelha muda de luz uma vez só, então repetição não infla o progresso.

## Estados (`avanco.estado`)
| estado | na tela | conta como |
|:--|:--|:--|
| `apagada` | Por acender | total |
| `refletida` | Luz refletida | total e "para converter" |
| `convertendo` | Convertendo | total e "para converter" |
| `propria` | Luz própria | total e progresso |
| `descartada` | (fora) | nada |

Transições:
- `apagada` ou `refletida` → `convertendo`: `iniciar` / `fazer` / `enviar` (fila do painel). O conteúdo guarda `luz_origem` (`apagada` ou `refletida`).
- `convertendo` + `avaliar(nota ≥ 3)` → continua `convertendo` com `confirmada_em` (a Luzia confirmou). Nota 0–2: continua `convertendo`, `tentativas + 1` e a dica do que faltou.
- `convertendo` confirmada + `confirmar` (o sim da pessoa) → `propria`: lúmen próprio no livro (`fonte` `conversao` se veio de refletida, `acesa` se veio de apagada; `ref` = id), `lm_ganho = valor_lm`.
- Hook, o agente aplicou o conceito: `apagada` → `refletida` (com `onde`). Sem centelha que case: nasce uma `refletida` de origem `chat`.
- Hook, o prompt da pessoa cita o conceito: uma centelha **do chat** `apagada`/`refletida` → `propria` (`fonte` `prompt`). Sem centelha que case: nasce uma `propria` de origem `chat`. Centelhas da meta e conversões em curso não mudam pelo prompt (revisão de 18/11: citar uma palavra não prova o entendimento).
- `descartar` (não vale para `propria`) → `descartada`; `restaurar` volta ao estado anterior (padrão `apagada`).
- Não há revisita nem lm parcial.

Estados antigos → novos (migração e dados legados): `sugerido` → `apagada`; `na_fila` e `em_andamento` → `convertendo`; `conquistado` com nota ≥ 3 → `propria`; `conquistado` com nota ≤ 2 → `convertendo` (o lm antigo fica na história); `descartado` → `descartada`.

## Valor da centelha (fixo na criação)
`valor_lm` é calculado uma vez, quando a centelha entra no catálogo, e nunca é recalculado (o percentual não pode pular sozinho). A conta fica em `conta_json`:
- **Profundidade do conceito:** base do tipo (`estudar` 20, `praticar` 20, `explicar` 15, `explorar` 10) + minutos (5 a 30).
- **Lacuna no prisma:** até 60% da profundidade, proporcional ao quanto do prisma ainda não é próprio no momento da criação.
- **Peso para a meta:** 40% da profundidade se o prisma é um dos 2 com menor pct, 20% nos outros, 0 se o prisma está em 100%.
- Total entre 10 e 100 lm. Exemplos: uma explicação de 5 min que nasce do chat vale 40 lm; uma prática de 15 min, 70 lm.
- As parcelas são proporcionais à profundidade para que um conceito citado de passagem não valha quase o mesmo que uma prática longa.

## Hooks
- Reconhecimento por **centelha**, não por prisma: o texto (em memória, nunca gravado) casa com as palavras da centelha (`conceitos` + `palavras`) e do prisma.
- Centelha criada pelo hook: id estável `aid('chat', prisma|termo)`, título = o termo, `tipo` `explicar`, 5 min, `onde` = "chat de DD/MM, HH:MM" e a extensão do arquivo (nunca o caminho).
- Deduplicação: um evento por centelha por sessão e por origem (`sessao_visto` com `prisma` = `c:<id>`), só para não repetir o aviso; o progresso não depende disso.

## Esquema 4
- `avanco` ganha `onde TEXT` e `confirmada_em TEXT`; o resto do conteúdo novo (`porque`, `guia`, `palavras`, `titulo_curto`, `luz_origem`) vai em `conteudo_json`.
- `prisma` ganha `meta_estado TEXT NOT NULL DEFAULT 'definida'` (`a_propor` nos prismas que vieram do esquema 3).
- `nivel_registro` fica só para leitura (histórico do modelo anterior, mostrado no dossiê).
- Antes de subir um banco do esquema 3, a Luzia grava um backup em `private/backup-antes-centelhas-AAAAMMDD-HHMMSS/luzia.db`.

## Dossiê
Evidência = centelhas próprias (nota, onde, data). Marcos em 1/3, 2/3 e 100% do lm próprio da trajetória. Os níveis conquistados antes aparecem como "Histórico (modelo anterior)".
