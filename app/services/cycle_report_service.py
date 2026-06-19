"""Compatibility alias for cycle-report services.

New code should import from app.features.cycle_reports.service.
"""

import sys as _sys

from ..features.cycle_reports import service as _service
from ..features.cycle_reports.service import *  # noqa: F403

_sys.modules[__name__] = _service
