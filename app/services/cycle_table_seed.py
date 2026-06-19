"""Compatibility alias for cycle-table seed services.

New code should import from app.features.cycle_reports.seed.
"""

import sys as _sys

from ..features.cycle_reports import seed as _seed
from ..features.cycle_reports.seed import *  # noqa: F403

_sys.modules[__name__] = _seed
