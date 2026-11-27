# Luzia · Como instalar (teste)

A Luzia é uma mentora de carreira dentro do agente de código. Por enquanto, ela roda no **Claude Code**; o suporte a outros agentes (Codex, Antigravity, Cursor) está nos planos. O código que o agente escreve e você não domina é **luz refletida**. Quando você explica, decide e defende esse código, ele vira **luz própria**. Este guia leva uns 10 minutos.

## O que você precisa

- [ ] Claude Code instalado.
- [ ] Python 3.11 ou mais novo, disponível como `python` no PATH. Confira com:

```
python --version
```

No macOS e no Linux, às vezes só existe `python3`. Um *alias* não basta: os hooks rodam fora do seu terminal e não enxergam aliases. Crie um link de verdade numa pasta do PATH (ex.: `~/.local/bin`; se ela não estiver no PATH, acrescente `export PATH="$HOME/.local/bin:$PATH"` ao seu `~/.zshrc` ou `~/.bashrc`):

```
mkdir -p ~/.local/bin && ln -sf "$(command -v python3)" ~/.local/bin/python
```

Depois, num terminal novo, `python --version` precisa mostrar 3.11 ou mais. Sem o comando `python`, o plugin não roda.

No Windows, instale o Python pelo site python.org marcando **Add python.exe to PATH**. Se `python` abrir a Microsoft Store, desligue o atalho em Configurações › Aplicativos › Aliases de execução de aplicativo.

- [ ] git.
- [ ] Uma chave de API de um modelo de IA, do provedor que você preferir: Anthropic, OpenAI, Google Gemini ou outro compatível. Se não tiver uma, estas têm opção gratuita (é só uma sugestão; os limites e as condições mudam, confira no site):
  - Google Gemini: https://aistudio.google.com/apikey
  - NVIDIA: https://build.nvidia.com (crie a conta e use "Get API Key"; pode pedir verificação por telefone)
  - Groq: https://console.groq.com/keys
  - OpenRouter: https://openrouter.ai/keys (use um modelo com `:free` no nome)

  No plano gratuito, o provedor pode usar os dados enviados para treinar os modelos dele. Se isso importa para você, use uma chave paga ou ligue o mascaramento (veja "Onde ficam os dados e privacidade").

## Instalação

1. Adicione o marketplace da Luzia (o repositório é público; não precisa de convite):

```
claude plugin marketplace add rayfrance/luzia
```

2. Instale o plugin:

```
claude plugin install luzia@luzia --scope user
```

3. Instale o SDK do provedor da sua chave (só o dele):

| Provedor | Comando |
|---|---|
| Google Gemini | `python -m pip install google-genai` |
| Anthropic | `python -m pip install anthropic` |
| OpenAI, NVIDIA, Groq, OpenRouter ou outro compatível | `python -m pip install openai` |

Opcional: o `pypdf`, só se for passar o currículo em PDF.

```
python -m pip install pypdf
```

4. Reinicie o Claude Code. Ou, dentro de uma sessão, rode `/reload-plugins`.
5. Abra uma sessão do Claude Code dentro do seu repositório de trabalho e rode:

```
/luzia:diagnostico
```

Ele confere Python, pasta de dados, SDK, chave e git. Agora é normal aparecer **Chave do modelo: FALTANDO**: você cola a chave no próximo passo.

6. Abra o painel:

```
/luzia:career-map
```

Ele abre em http://127.0.0.1:8501, já com a sua sessão aberta. Antes da triagem, aparece uma tela de boas-vindas para escolher o modelo: escolha o **Provedor** da sua chave (os que têm opção gratuita aparecem marcados), o **Modelo** (a lista traz sugestões; em "Outro…" você digita o nome exato que aparece no site do provedor), cole a chave e clique em **Testar** (ele salva e testa, em no máximo 30 s). Deve aparecer "Funcionou: … respondeu em N s". A chave fica só nesta máquina (na pasta de dados) e nunca passa pelo chat.

7. Faça a triagem:

```
/luzia:triage
```

A Luzia faz uma entrevista curta: onde você está, aonde quer chegar, em quanto tempo, qual repositório de trabalho, qual e-mail aparece nos seus commits, currículo e GitHub (opcionais) e se pode ler o histórico do Claude Code e do Codex (só com o seu sim). Depois monta a sua trajetória e pede pelo menos 3 centelhas para cada prisma (costuma levar de 1 a 4 minutos; se o Gemini estiver sobrecarregado, a Luzia tenta de novo e usa um modelo reserva sozinha). Se o modelo falhar para algum prisma, ele fica com menos centelhas, e a Luzia avisa em Hoje e na Trajetória e oferece acender mais.

8. Volte ao painel. Na primeira vez depois da triagem, ele abre um tutorial curto que mostra cada parte da tela e as ideias da Luzia. Dá para rever quando quiser em **Ajustes › Tutorial**.

## Atualizar

```
claude plugin marketplace update luzia
```

```
claude plugin update luzia@luzia
```

Depois rode `/reload-plugins`.

## Desinstalar

```
claude plugin uninstall luzia@luzia
```

Se quiser apagar os dados, apague à mão a pasta `~/.luzia` (no Windows, `C:\Users\<você>\.luzia`).

## Onde ficam os dados e privacidade

- Tudo fica em `~/.luzia`: o banco `luzia.db`, a configuração e o `.env` com a sua chave.
- O que sai da máquina:
  - **Para o provedor de modelo** que você escolher em Ajustes › Modelo (o que vem marcado de início é o Google Gemini), com a sua chave. No plano gratuito, o provedor pode usar esses dados para treinar os modelos dele:
    - na **triagem**: as suas respostas da entrevista e a autoavaliação (se houver); o currículo (até 6.000 caracteres, se você passar um); do seu GitHub público (se você passar o usuário), a bio, o ano de criação da conta, quantos repositórios públicos você tem, as linguagens e o nome e a descrição de até 8 repositórios recentes; dos seus commits recentes, a data, o assunto, quantos arquivos e linhas mudaram e as áreas (por extensão), nunca o código nem os nomes dos arquivos; e, só se você autorizar o histórico das IAs, até 12 trechos curtos (180 caracteres) dos seus prompts recentes no Claude Code com o nome da pasta do projeto, títulos curtos das sessões do Codex, os nomes dos plugins instalados e, se configurado à mão em `entrada.json`, notas do seu vault; o PDF do LinkedIn (até 6.000 caracteres) só vai se for configurado à mão em `entrada.json`, com ou sem o histórico;
    - depois (as análises vencidas também rodam sozinhas quando você abre o painel com o modelo configurado): os fatos de cada prisma ou entrega para as análises (inclusive o título de cada entrega, que é o assunto do commit ou o título do PR), as centelhas novas, as propostas de mudança da trajetória (com o motivo e a nota que você escrever), os motivos que você deu ao descartar centelhas e, quando você pede as oportunidades da sessão, os eventos que os hooks guardaram (sem código nem prompt).
  - **Para o GitHub**, se você passar o usuário na triagem: uma consulta à API pública do seu perfil e dos seus repositórios.
- O que a Luzia mostra no chat (centelhas, entregas, trajetória) entra na conversa do seu agente (Claude Code), sem mascaramento: o agente vê os dados reais, como já vê o seu código. A conversa de conversão também acontece no seu agente, não passa pela Luzia.
- Os hooks rodam localmente, sem modelo, e nunca guardam código nem texto de prompt. Guardam só fatos: hora, sessão (como código embaralhado), prisma, ferramenta, extensão do arquivo, modo, a luz que acendeu, os lúmens e se a Luzia comentou no chat. Quando nasce uma centelha do chat, ela guarda também o termo técnico que casou, tirado das palavras do próprio prisma, nunca o resto da frase.
- A Luzia só observa o repositório que você autorizou na triagem.
- O mascaramento vem **desligado**. Ligado (painel › Ajustes › "O que vai para o modelo" › Mascarar), ele troca por marcadores (ou remove), antes do envio ao modelo, e-mails, links (com http, www ou domínios como .com e .br), hashes, números de PR (PR 12, #123) e de ticket (#1234, PROJ-123), CPF, telefone, CEP, os nomes (de 4 letras ou mais) das outras pessoas que aparecem no git do repositório e os termos que você listar (empresa, clientes) em `termos.txt`, na pasta de dados. Os nomes dos prismas não passam pela máscara, porque o modelo precisa devolvê-los iguais: se um nome de prisma citar a empresa ou um cliente, peça a mudança na Trajetória.

## Modos de foco

Em painel › Ajustes › Foco:

- **Em foco**: mostra centelhas no chat, no fim da resposta do agente.
- **Em silêncio**: coleta sem interromper.
- **Fora de foco**: não observa; só age quando você chama um comando ou manda uma centelha do painel para o agente (o botão de uma centelha que a leva ao agente, como "Acender no Claude Code" ou "Converter com a Luzia"), que ele oferece na sua próxima mensagem.

## Comandos principais

- `/luzia:hoje`: ponto de partida.
- `/luzia:career-map`: abre o painel.
- `/luzia:centelhas`: lista e filtra suas centelhas.
- `/luzia:converter <id>` e `/luzia:fazer <id>`: iniciam ou continuam uma conversão.
- `/luzia:confirmar <id>`: o seu sim.
- `/luzia:trajetoria`, `/luzia:entregas`, `/luzia:acender <prisma>`, `/luzia:dossie`, `/luzia:configurar`, `/luzia:diagnostico`.

## Se algo der errado

| Sintoma | O que fazer |
|---|---|
| "Luzia desligada" no painel | Rode `/luzia:career-map` de novo. |
| Porta 8501 ocupada | Feche o outro painel aberto. |
| "chave sem permissão ou inválida" na triagem ou no Testar | Defina a chave em Ajustes › Modelo e clique em Testar. |
| "Triagem não rodou", seguido de "o Gemini está sobrecarregado agora" (ou "o provedor … está sobrecarregado") | É do lado do provedor. Com o Gemini, a Luzia já tenta de novo e usa um modelo reserva; espere alguns minutos e rode o comando de novo, ou troque de modelo em Ajustes › Modelo. |
| "cota esgotada no momento" | O plano da sua chave (comum no gratuito) atingiu o limite. Espere um pouco ou escolha outro modelo ou provedor em Ajustes › Modelo. |
| Os hooks não disparam | Você está fora do repositório autorizado (rode `/luzia:configurar` para mudar) ou o modo é Fora de foco. |
| `python` não encontrado | Instale o Python 3.11+ e reabra o terminal. |
| "Nenhuma entrega encontrada" em Entregas | Rode `/luzia:entregas` e confira o e-mail dos commits com `/luzia:identidade`. |

Não resolveu? Mande a mensagem de erro para a Rayane, sem chaves nem dados pessoais.
