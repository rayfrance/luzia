# Luzia · Roteiro do teste

## Para quem é este teste

A Luzia ajuda quem programa com agentes de IA a não perder o domínio do próprio trabalho: ela percebe o que o agente aplicou por você e transforma isso em conceitos que você explica e passa a dominar. O teste faz sentido se você:

- programa de verdade num repositório git com commits seus (trabalho, estágio, projeto pessoal ou da faculdade);
- já usa o **Claude Code** (é nele que a Luzia roda), todo dia ou algumas vezes por semana;
- está no começo ou no meio da carreira (estágio, júnior, pleno) e quer crescer numa direção clara;
- pode usar a Luzia por alguns dias no seu trabalho de sempre e responder a avaliação no fim (uns 10 minutos);
- tem Python 3.11 ou mais novo e pode criar uma chave gratuita do Gemini;
- pode enviar a um modelo de IA externo os assuntos dos seus commits e as respostas da entrevista (se o seu trabalho proíbe isso, use um projeto pessoal).

Não precisa saber nada da Luzia antes. Se você não programa ou não usa agentes de código, a sua opinião ainda vale, mas este teste mede outra coisa.

## Como vai ser

Você vai usar a Luzia no seu trabalho de sempre, a partir do dia em que instalar, até a data que a Rayane combinar com você. Depois, responde à [avaliação](https://docs.google.com/forms/d/e/1FAIpQLSfyMd9apFVT9AGktAQHIlGqPV8N8zAD-bFU0FkcCGKL5wKqPw/viewform) (formulário anônimo, cerca de 10 minutos). Instalação: [INSTALAR.md](INSTALAR.md).

A ideia em uma frase: o que o agente aplica e você não domina é luz refletida. Quando você explica e defende, vira luz própria. Cada prisma (skill) da sua meta tem centelhas (conceitos), cada uma com um valor fixo em lúmens (lm). O % de cada prisma, e o **% do caminho** da trajetória, é a luz própria até o alvo da meta: ele sobe quando uma centelha vira luz própria, e acender centelhas novas só cria oportunidades, então não o baixa. Fora isso, ele só muda quando você muda a trajetória: incluir ou arquivar um prisma muda o alvo (o número pode subir ou descer), e a Luzia mostra o antes e o depois. Ao lado, o **% da luz coletada é sua** mostra quanto da luz que você já tocou é sua, e não do agente.

## Quando converter: na espera do agente

A Luzia não pede um tempo a mais no seu dia. A ideia é aproveitar a espera: quando você dispara uma tarefa longa no agente (implementar uma funcionalidade, rodar a suíte de testes, refatorar), em vez de ficar olhando o agente trabalhar, converta uma centelha. Pode ser uma que essa própria tarefa acendeu ou qualquer outra do painel.

- Numa **segunda sessão** do Claude Code, no mesmo repositório, rode `/luzia:fazer <id>`. Ou, no painel, abra a centelha e use **Copiar prompt** numa outra conversa com o agente.
- Quando o agente terminar, volte para a tarefa. A conversão fica guardada e continua depois de onde parou, com `/luzia:fazer <id>`.

## Registre enquanto usa

Mantenha um arquivo de notas aberto. Anote, com data e hora:

1. Um momento em que a Luzia ajudou você a entender algo.
2. Um momento em que ela atrapalhou.
3. Qualquer coisa errada ou confusa (texto, valor em lm, botão, comportamento).

Frases curtas bastam. Isso vira a sua avaliação no final. Não cole código da empresa nem segredos.

## Missão 1 · Primeiro dia

**Objetivo:** deixar tudo funcionando e entender onde você está na sua trajetória.

1. Siga o [INSTALAR.md](INSTALAR.md) até o passo 10, incluindo o tutorial do painel.
2. Rode `/luzia:hoje` e leia o que ela sugere.
3. No painel, abra as abas **Hoje** e **Trajetória**.

**Repare em:**

- A trajetória fez sentido para o seu cargo e a sua meta?
- Os prismas são habilidades reais do seu trabalho?
- O tutorial explicou o suficiente para você saber o que fazer depois?
- Alguma coisa na instalação ou na triagem travou ou confundiu?

## Missão 2 · Trabalho normal com o agente

**Objetivo:** ver a Luzia no fluxo real e concluir uma conversão.

1. No painel, em Ajustes, deixe o modo **Em foco**.
2. Trabalhe como sempre no repositório autorizado, com o agente, por pelo menos **1 hora**.
3. Quando a Luzia mostrar uma centelha da sessão (luz refletida que o agente usou), aceite convertê-la. Faça isso pelo menos **2 vezes**, de preferência enquanto o agente trabalha numa tarefa longa (veja "Quando converter", acima). Se nenhuma aparecer, rode `/luzia:centelhas` e converta uma de lá com `/luzia:converter <id>`.
4. Responda às perguntas da Luzia, uma por vez, com as suas palavras. Termine **uma** conversão até o botão **Acender luz própria**.

Se quiser retomar uma centelha depois:

```
/luzia:centelhas
```

```
/luzia:fazer <id>
```

**Repare em:**

- O cartão apareceu em hora boa ou interrompeu você?
- Converter na espera do agente aproveitou um tempo em que você só ficaria esperando, ou pareceu tempo a mais?
- As perguntas ajudaram a entender o código, ou pareceram uma prova?
- Ao final, você conseguiria explicar aquele trecho sem a IA?
- Quando o conceito veio de você, no seu prompt, a centelha do chat virou luz própria direto. Isso pareceu justo?
- Depois de converter, o **% do caminho** subiu? Quando o agente fez algo por você, o "% da luz coletada é sua" caiu? Os dois números fizeram sentido?

## Missão 3 · Painel e entregas

**Objetivo:** olhar o seu progresso e provar a sua parte numa entrega.

1. Abra o painel:

```
/luzia:career-map
```

2. Escolha um prisma e veja as suas centelhas e os estados (Por acender, Luz refletida, Convertendo, Luz própria).
3. Abra uma centelha e clique em **Por que N lm**. O valor fez sentido?
4. Abra a aba **Entregas**. Ela mostra quanto de cada entrega do git é seu, em quatro medidas: **P1 · Direção no prompt** (a direção que você deu ao agente), **P2 · Coesão** (poucos arquivos e áreas), **P3 · Aplicação de conceito** (o conceito que você explicou) e **P4 · Decisão de arquitetura** (a decisão que você defendeu).
5. Em uma entrega, use **Provar P3 e P4** (ou só a que faltar; aparece quando falta prova de autoria) ou **Converter a luz desta entrega** (aparece quando há luz refletida ligada a ela).
6. Gere o dossiê de evidências:

```
/luzia:dossie
```

**Repare em:**

- Você confia nos lm e nas notas P1 a P4? Dá para ver de onde vieram?
- A aba Entregas achou os seus commits? Se não, confira o e-mail com `/luzia:identidade`.
- O dossiê serviria para uma conversa com o seu líder ou para um PDI?

## No fim

Responda à [avaliação](https://docs.google.com/forms/d/e/1FAIpQLSfyMd9apFVT9AGktAQHIlGqPV8N8zAD-bFU0FkcCGKL5wKqPw/viewform) usando as suas notas.
