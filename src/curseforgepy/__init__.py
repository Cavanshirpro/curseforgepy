"""
curseforgepy package initializer.

This file exposes the high-level public API for the package:
 - CurseForge (main client)
 - create_client (convenience factory)
 - exceptions (module with custom exceptions)
 - types (typed dataclasses module, tolerant to alternate filenames)

Implementation notes:
 - Keep imports tolerant: types module may be named `types` or `types_models`.
 - Avoid heavy work at import time.
"""

__all__ = ["CurseForge", "create_client", "exceptions", "types", "__version__"]

# package version (update as you release)
__version__ = "0.1.0"

# re-export exceptions for convenience
from .exceptions import *  # noqa: F401,F403


from .client import CurseForge, create_client  # type: ignore
# tolerant import for types module (some users may have renamed types.py to avoid stdlib shadowing)
_types = None

if _types is not None:
    # expose the module under package.types and re-export its public names
    types = _types
    # re-export all public names from types module (safe: skip private names)
    for _name in getattr(_types, "__all__", dir(_types)):
        if _name.startswith("_"):
            continue
        try:
            globals().setdefault(_name, getattr(_types, _name))
        except Exception:
            # ignore problematic attributes
            pass
else:
    types = None
