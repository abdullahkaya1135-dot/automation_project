"""Compatibility alias for the bootstrap API router.

New code should import from app.features.bootstrap.api.
"""

import sys as _sys

from ..features.bootstrap import api as _api
from ..features.bootstrap.api import *  # noqa: F403

_sys.modules[__name__] = _api
