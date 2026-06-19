"""Compatibility alias for the IFS API router.

New code should import from app.features.ifs.api.
"""

import sys as _sys

from ..features.ifs import api as _api
from ..features.ifs.api import *  # noqa: F403

_sys.modules[__name__] = _api
