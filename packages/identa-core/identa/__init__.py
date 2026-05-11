# packages/identa-core/identa/__init__.py
__path__ = __import__('pkgutil').extend_path(__path__, __name__)
try:
    from .sdk import *
except ImportError:
    pass
