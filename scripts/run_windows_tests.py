"""Run pytest without SQLAlchemy's Windows C extension when App Control blocks it.

This loads SQLAlchemy's bundled Python implementation in this process only;
it does not modify the virtual environment or installed packages.
"""
import importlib.util
import importlib.abc
from pathlib import Path
import sys
import types


def install_sqlalchemy_python_fallback():
    if sys.platform != 'win32':
        return
    package_spec = importlib.util.find_spec('sqlalchemy')
    if package_spec is None or not package_spec.origin:
        raise SystemExit('SQLAlchemy is not installed in this Python environment.')
    package_dir = Path(package_spec.origin).parent
    processor_fallback = package_dir / 'engine' / '_processors_cy.py'
    immutable_fallback = package_dir / 'util' / '_immutabledict_cy.py'
    for fallback_path in (processor_fallback, immutable_fallback):
        if not fallback_path.is_file():
            raise SystemExit(f'SQLAlchemy Python fallback is missing: {fallback_path}')

    # SQLAlchemy's pure-Python extension source uses these decorators only to
    # mark accelerated code. Mark it uncompiled and make the decorators inert.
    cython = types.ModuleType('cython')
    cython.compiled = False
    cython.annotation_typing = lambda *args, **kwargs: (lambda value: value)
    cython.cclass = lambda value: value
    cython.cfunc = lambda value: value
    cython.inline = lambda value: value
    sys.modules.setdefault('cython', cython)

    module_name = 'sqlalchemy.engine._processors_cy'
    spec = importlib.util.spec_from_file_location(module_name, processor_fallback)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    # SQLAlchemy imports this extension from util._collections at package
    # initialization. Intercept only this module so its bundled .py source is
    # loaded before the blocked .pyd extension, without editing site-packages.
    immutable_module_name = 'sqlalchemy.util._immutabledict_cy'

    class _SqlAlchemyFallbackFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == immutable_module_name:
                return importlib.util.spec_from_file_location(
                    fullname, immutable_fallback
                )
            return None

    sys.meta_path.insert(0, _SqlAlchemyFallbackFinder())


def main():
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    install_sqlalchemy_python_fallback()
    import pytest
    return pytest.main(sys.argv[1:] or ['-q'])


if __name__ == '__main__':
    raise SystemExit(main())
