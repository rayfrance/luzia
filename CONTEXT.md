# Luzia · roteamento

| Pasta / arquivo | O que é |
|:--|:--|
| `luzia/` | o pacote Python **e** a raiz do plugin (comandos, skills, hooks, painel). Detalhes em [luzia/CONTEXT.md](luzia/CONTEXT.md) |
| `luzia/tests/` | suíte sobre dados sintéticos |
| `luzia/private/` | dados reais da pessoa (fora do git) |
| `docs/luzia-ux.md` | regras da experiência e do jogo (vocabulário, luz, centelhas) |
| `docs/specs/`, `docs/plans/` | especificações e planos de implementação |
| `docs/handoffs/` | continuidade entre sessões e agentes |
| `design/v2/` | referência visual e de lógica (protótipo do painel, tokens, guia de voz) |
| `.claude-plugin/marketplace.json` | marketplace local: `claude plugin marketplace add <esta pasta>` e `claude plugin install luzia@luzia` |

## Origem
Este repositório nasceu de `code/luzia` do projeto AI4Good (UFRPE), commit `f7e6dfe` da branch `feature/luzia-acoes`, mais os ajustes ainda sem commit de 13/11/2026. O histórico anterior fica no repositório de origem.
