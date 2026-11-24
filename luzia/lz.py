"""Lançador da Luzia: roda um módulo do pacote de qualquer pasta, instalada pelo marketplace ou não.

    python lz.py <cli|observer|statusline|server|instalar> [args...]

O plugin instalado fica numa pasta de cache que não se chama `luzia`; aqui o pacote é carregado sob o nome `luzia`.
"""
import importlib
import os
import sys

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
    if mod in ('observer', 'statusline'):  # hooks: quente e frequente; o porteiro barra antes de importar o resto
        bruto = sys.stdin.buffer.read()
        _carregar_pacote()
        from luzia import porteiro
        if mod == 'observer':
            if porteiro.barrar_hook(bruto):
                return
        else:
            pronta = porteiro.barrar_statusline(bruto)
            if pronta is not None:
                if pronta:
                    print(pronta)
                return
        importlib.import_module('luzia.' + mod).main(bruto)
        return
    _carregar_pacote()
    import runpy
    sys.argv = ['luzia.' + mod, *rest]
    runpy.run_module('luzia.' + mod, run_name='__main__', alter_sys=True)


def _carregar_pacote() -> None:
    if 'luzia' not in sys.modules:
        raiz = os.path.dirname(os.path.abspath(__file__))
        try:  # os mesmos construtores de importlib.util, sem pagar o import dele (cerca de 10 ms por hook)
            from importlib import _bootstrap as _b, _bootstrap_external as _e
            nova = _e.spec_from_file_location, _b.module_from_spec
        except ImportError:
            import importlib.util
            nova = importlib.util.spec_from_file_location, importlib.util.module_from_spec
        spec = nova[0]('luzia', os.path.join(raiz, '__init__.py'), submodule_search_locations=[raiz])
        pacote = nova[1](spec)
        sys.modules['luzia'] = pacote
        spec.loader.exec_module(pacote)


if __name__ == '__main__':
    main()
