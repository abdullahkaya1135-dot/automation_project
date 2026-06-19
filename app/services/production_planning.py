"""Compatibility alias for production-planning services.

New code should import from app.features.production_planning.service.
"""

import sys as _sys

from ..features.production_planning import service as _service
from ..features.production_planning.service import *  # noqa: F403

_sys.modules[__name__] = _service
