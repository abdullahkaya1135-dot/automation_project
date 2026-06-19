"""Compatibility alias for core database infrastructure.

New code should import from app.core.database.
"""

import sys as _sys

from .core import database as _database
from .core.database import *  # noqa: F403

_sys.modules[__name__] = _database
