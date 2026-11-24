# Luzia

Líder técnica de carreira dentro do agente de código (Claude Code, Codex, Cursor, Antigravity).

A tese: o código que o agente produz e você não domina é **luz refletida**. Quando você explica, decide e defende, a luz passa a ser **própria**. A Luzia captura **centelhas** (conceitos que aparecem no seu trabalho), mostra quanto de cada prisma (skill) da sua meta já é luz própria e guia a conversão do que ainda é refletido.

## Rodar
```
python -m pytest luzia/tests -q      # suíte
python -m luzia.cli hoje              # ponto de partida no terminal
python -m luzia.server                # painel em http://127.0.0.1:8501
```

## Instalar no Claude Code
```
claude plugin marketplace add <esta pasta>
claude plugin install luzia@luzia
```
Sem o sistema de plugins: `python -m luzia.instalar` (com `--hooks` e `--statusline` opcionais). Outros agentes: `python -m luzia.instalar --regras`.

Regras do jogo: [docs/luzia-ux.md](docs/luzia-ux.md). Mapa do código: [luzia/CONTEXT.md](luzia/CONTEXT.md).

## Para testadores
Vai testar a Luzia? Comece por aqui:

- [Instalar](docs/teste/INSTALAR.md): requisitos, instalação, atualização, privacidade e problemas comuns.
- [Roteiro](docs/teste/ROTEIRO.md): três missões curtas e o que registrar enquanto usa.
- [Avaliação](docs/teste/AVALIACAO.md): o formulário para responder no fim do teste.
