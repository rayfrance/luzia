# Luzia — regras para agentes de IA

> Leia este arquivo e o `CONTEXT.md` da pasta antes de qualquer tarefa.

## Navegação
- `CONTEXT.md` (raiz) roteia o repositório; `luzia/CONTEXT.md` descreve cada módulo do pacote.
- O sistema de arquivos é a fonte da verdade: decisões, protocolos e continuidade ficam em `docs/`.

## Dados pessoais e segredos
- `luzia/private/` guarda os dados reais (banco, currículo, entregas, termos). Nunca entra no git, nunca é lida por testes e nunca é enviada a subagentes.
- Segredos (chaves de API) ficam em `.env` na raiz, fora do git. Se precisar de um, pergunte e escreva o `.env` você mesmo; nunca peça para colar o segredo no chat.
- Nomes da empresa, produtos internos, clientes, colegas, e-mails corporativos e números de ticket/PR nunca entram em arquivo versionado. `luzia/private/termos.txt` lista os termos que não podem aparecer.

## Testes
- `python -m pytest luzia/tests -q` na raiz. A suíte roda sobre dados sintéticos (`LUZIA_PRIVATE` temporário, ver `luzia/tests/conftest.py`).
- TDD: teste que falha primeiro, depois o código.

## Git e commits
- GitFlow: trabalho em `feature/*`, vai para `develop`, depois `main`.
- Nunca faça commit direto em `main` ou `develop` sem permissão explícita.
- Mostre o `git diff` antes de commitar e espere aprovação.
- Mensagens em inglês, Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
- Sem push nem remoto sem pedido explícito.

## Edição vs. criação
- Prefira editar a criar. Proliferação de arquivos é um problema.
- Ao criar, siga o lugar indicado no `CONTEXT.md` da pasta.

## Dúvidas
- Não assuma. Pergunte antes de agir quando a intenção não estiver clara.

## Continuidade
- Ao encerrar trabalho significativo com pendências, registre em `docs/handoffs/{id-tarefa}.md`: objetivo, decisões, arquivos, verificações, pendências, próxima ação e data.
- Agentes simultâneos usam arquivos distintos ou worktrees separados.
