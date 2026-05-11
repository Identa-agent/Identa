import importlib
import sys

def lazy_import(name):
    """
    Returns a proxy for a module that is only imported when accessed.
    """
    if name in sys.modules:
        return sys.modules[name]
    
    class LazyModule:
        def __init__(self):
            self._module = None

        def _load(self):
            if self._module is None:
                try:
                    self._module = importlib.import_module(name)
                except ImportError:
                    raise ImportError(
                        f"The '{name}' module is required for this feature. "
                        f"Install it with: pip install 'identa-core[enterprise]'"
                    )
            return self._module

        def __getattr__(self, item):
            return getattr(self._load(), item)

        def __dir__(self):
            return dir(self._load())

    return LazyModule()
