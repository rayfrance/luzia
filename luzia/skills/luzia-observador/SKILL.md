---
name: luzia-observador
description: "Como responder aos avisos automáticos da Luzia ([Luzia · em foco · luz refletida], [Luzia · em foco · luz própria], [Luzia · fila], [Luzia · em foco · início]) que os hooks do plugin colocam no contexto do Claude Code."
---

# Luzia · observador de sessão

Os hooks do plugin rodam `observer.py` localmente, sem chamar modelo, só nos repositórios autorizados (`observer.json`, na pasta de dados da Luzia; `/luzia:diagnostico` mostra onde). Guardam só o evento mascarado (horário, prisma, extensão), nunca caminho, código ou texto de prompt.

- **[Luzia · em foco · luz refletida]** (depois de uma edição ou commit): o agente aplicou o conceito de uma centelha, então ela acendeu como luz refletida, para converter. Termine a tarefa e mostre o cartão de até 3 linhas pedido no aviso: `✦ Centelha da sessão · <prisma> · <título> · <N> lm para converter`, uma linha de onde o conceito aparece e `▸ Converter: você explica por que o agente fez assim, e a luz vira sua.` Depois use AskUserQuestion com "Converter agora" e "Depois". Converter agora: rode `fazer <id> --onde aqui` e siga o roteiro. Depois: nada a fazer, a centelha fica para converter. Se o aviso disser "a confirmar" (banco ocupado), mostre só a linha única e não faça perguntas.
- **[Luzia · em foco · luz própria]**: a pessoa dirigiu o conceito no prompt e a centelha virou luz própria. Uma linha no fim, só isso.
- **[Luzia · fila]**: a pessoa mandou uma centelha do painel. Responda ao que ela pediu e, no fim, ofereça "Abrir em sessão nova", "Fazer aqui" e "Depois".
- **[Luzia · em foco · início]**: há algo a retomar (centelha convertendo, luz refletida para converter, fila). Uma linha no fim da primeira resposta, sugerindo `/luzia:hoje`. Logo depois da triagem (só centelhas por acender, nenhuma luz própria), o aviso traz a linha pronta: `✦ Luzia (em foco): <N> centelhas na sua meta para acender · /luzia:hoje para começar.`; mostre-a como está.

Foco da Luzia (painel > Ajustes, ou `python "${CLAUDE_PLUGIN_ROOT}/lz.py" cli modo <modo>`):
- `ativo` (**Em foco**): observa e mostra os cartões no chat.
- `passivo` (**em foco, em silêncio**): só muda a luz no banco, sem interromper.
- `sob_demanda` (**fora de foco**): não observa; responde só quando chamada.
Cada centelha muda de luz uma vez, então não há teto diário. Nunca interrompa a tarefa.
