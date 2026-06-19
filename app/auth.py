"""Compatibility alias for core security helpers.

New code should import from app.core.security.
"""

import sys as _sys

from .core import security as _security
from .core.security import *  # noqa: F403

_sys.modules[__name__] = _security
