"""Compatibility alias for core filesystem paths.

New code should import from app.core.paths.
"""

import sys as _sys

from .core import paths as _paths
from .core.paths import *  # noqa: F403

_sys.modules[__name__] = _paths
