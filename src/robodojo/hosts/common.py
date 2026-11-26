# Copyright 2026 PyRUA-Lean Contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""What every host shares: the result schema and stopping a host's servers.

The host module (``xpolicylab_robodojo``) exposes ``Cell``,
``boot(cell, out_dir, *, bridge, env_only=False, **options)``, ``make_backend(toolkit)`` and
``dump_card(toolkit, cell, out_dir)``; ``robodojo.play`` drives it through the robot's
adapter.
"""

from __future__ import annotations

import contextlib
from typing import Any

RESULT_SCHEMA = "robodojo-episode-v2"


def stop_all(toolkit: Any, daemons: list[Any]) -> None:
    """Close the toolkit and stop its servers, ignoring errors."""

    if toolkit is not None:
        with contextlib.suppress(Exception):
            toolkit.close()
    for daemon in reversed(daemons):
        with contextlib.suppress(Exception):
            daemon.stop()


__all__ = ["RESULT_SCHEMA", "stop_all"]
