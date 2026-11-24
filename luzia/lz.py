"""Lançador da Luzia: roda um módulo do pacote de qualquer pasta, instalada pelo marketplace ou não.

    python lz.py <cli|observer|statusline|server|instalar> [args...]

O plugin instalado fica numa pasta de cache que não se chama `luzia`; aqui o pacote é carregado sob o nome `luzia`.
"""
import importlib.util
import runpy
import sys
from pathlib import Path

MODULOS = ('cli', 'observer', 'statusline', 'server', 'instalar')


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in MODULOS:
        print('Uso: python lz.py <' + '|'.join(MODULOS) + '> [args...]', file=sys.stderr)
        sys.exit(2)
    mod, rest = sys.argv[1], sys.argv[2:]
    for f in (sys.stdout, sys.stdin, sys.stderr):
        try:
            f.reconfigure(encoding='utf-8')
        except Exception:
            pass
    if 'luzia' not in sys.modules:
        raiz = Path(__file__).resolve().parent
        spec = importlib.util.spec_from_file_location('luzia', raiz / '__init__.py', submodule_search_locations=[str(raiz)])
        pacote = importlib.util.module_from_spec(spec)
        sys.modules['luzia'] = pacote
        spec.loader.exec_module(pacote)
    sys.argv = ['luzia.' + mod, *rest]
    runpy.run_module('luzia.' + mod, run_name='__main__', alter_sys=True)


if __name__ == '__main__':
    main()
