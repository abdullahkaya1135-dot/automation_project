"""Compatibility alias for the IFS client.

New code should import from app.integrations.ifs.client.
"""

import sys as _sys

from .ifs import client as _client
from .ifs.client import *  # noqa: F403

_sys.modules[__name__] = _client
