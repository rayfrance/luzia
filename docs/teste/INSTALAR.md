# Luzia · Como instalar (teste)

A Luzia é uma mentora de carreira dentro do agente de código. O código que o agente escreve e você não domina é **luz refletida**. Quando você explica, decide e defende esse código, ele vira **luz própria**. Este guia leva uns 10 minutos.

## O que você precisa

- [ ] Claude Code instalado.
- [ ] Python 3.11 ou mais novo, disponível como `python` no PATH. Confira com:

```
python --version
```

No macOS e no Linux, às vezes só existe `python3`. Um *alias* não basta: os hooks rodam fora do seu terminal e não enxergam aliases. Crie um link de verdade numa pasta do PATH (ex.: `~/.local/bin`, que precisa estar no PATH):

```
mkdir -p ~/.local/bin && ln -sf "$(command -v python3)" ~/.local/bin/python
```

Depois, num terminal novo, `python --version` precisa mostrar 3.11 ou mais. Sem o comando `python`, o plugin não roda.

- [ ] git.
- [ ] Conta no GitHub com acesso ao repositório privado. Você recebe um convite da Rayane.
- [ ] Chave de API do Google Gemini (gratuita): https://aistudio.google.com/apikey

## Instalação

1. Aceite o convite do GitHub (chega por e-mail).
2. Deixe o git usar o seu login do GitHub. Com o GitHub CLI:

```
gh auth login
```

```
gh auth setup-git
```

Se você já tem uma chave SSH configurada no GitHub, pode usá-la no lugar.

3. Adicione o marketplace da Luzia:

```
claude plugin marketplace add rayfrance/luzia
```

4. Instale o plugin:

```
claude plugin install luzia@luzia --scope user
```

5. Instale o SDK do Gemini:

```
python -m pip install google-genai
```

Opcional: o `pypdf`, só se for passar o currículo em PDF.

```
python -m pip install pypdf
```

6. Reinicie o Claude Code. Ou, dentro de uma sessão, rode `/reload-plugins`.
7. Abra uma sessão do Claude Code dentro do seu repositório de trabalho e rode:

```
/luzia:diagnostico
```

Ele confere Python, pasta de dados, SDK, chave e git.

8. Abra o painel:

```
/luzia:career-map
```

Ele abre em http://127.0.0.1:8501, já com a sua sessão aberta. Antes da triagem, aparece uma tela de boas-vindas para escolher o modelo: Provedor **Google Gemini**, modelo `gemini-3.5-flash-lite`, cole a chave e clique em **Testar** (ele salva e testa). Deve aparecer "Respondeu em N s". A chave fica só nesta máquina (na pasta de dados) e nunca passa pelo chat.

9. Faça a triagem:

```
/luzia:triage
```

A Luzia faz uma entrevista curta: onde você está, aonde quer chegar, em quanto tempo, qual repositório de trabalho, qual e-mail aparece nos seus commits, currículo e GitHub (opcionais) e se pode ler o histórico do Claude Code e do Codex (só com o seu sim). Depois monta a sua trajetória, com pelo menos 3 centelhas em cada prisma (cerca de 1 minuto).

10. Volte ao painel. Na primeira vez depois da triagem, ele abre um tutorial curto que mostra cada parte da tela e as ideias da Luzia. Dá para rever quando quiser em **Ajustes › Tutorial**.

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
- Nada vai para servidor nenhum, exceto as chamadas ao modelo do Google com a sua chave (triagem e análises).
- Os hooks rodam localmente, sem modelo, e nunca guardam código nem texto de prompt. Guardam só fatos mascarados: hora, prisma e extensão do arquivo.
- A Luzia só observa o repositório que você autorizou na triagem.
- Mascaramento opcional: painel › Ajustes › "O que vai para o modelo" › Mascarar.

## Modos de foco

Em painel › Ajustes › Foco:

- **Em foco**: mostra centelhas no chat, no fim da resposta do agente.
- **Em silêncio**: coleta sem interromper.
- **Fora de foco**: só age quando você chama um comando.

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
| Erro de chave na triagem | Defina a chave em Ajustes › Modelo e clique em Testar. |
| Os hooks não disparam | Você está fora do repositório autorizado (rode `/luzia:configurar` para mudar) ou o modo é Fora de foco. |
| `python` não encontrado | Instale o Python 3.11+ e reabra o terminal. |
| Nada em Entregas | Rode `/luzia:entregas` e confira o e-mail dos commits com `/luzia:identidade`. |

Não resolveu? Mande a mensagem de erro para a Rayane, sem chaves nem dados pessoais.
