"""Compatibility alias for core configuration.

New code should import from app.core.config.
"""

import sys as _sys

from .core import config as _config
from .core.config import *  # noqa: F403

_sys.modules[__name__] = _config
