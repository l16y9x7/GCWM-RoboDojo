# Copyright 2026 PyRUA-Lean Contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""Registry of the robots robodojo can drive.

The robot module (``robodojo.robodojo_xpl_rgb``) defines a module-level ``ADAPTER``: the
robot class, the host that serves RoboDojo's evaluation client, the knowledge file and the
words the contract uses. ``get_adapter(name)`` imports the module lazily.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

ROBOTS: tuple[str, ...] = ("robodojo_xpl_rgb",)


@dataclass(frozen=True)
class RobotAdapter:
    """What the host and the prompt need to know about one robot."""

    #: The robot's name (``robodojo_xpl_rgb``).
    name: str
    #: The policy-facing robot class (a :class:`robodojo._robot.RobotBase`).
    robot_cls: type
    #: Module exposing ``Cell``, ``boot``, ``make_backend`` and ``dump_card``
    #: (``robodojo.hosts.xpolicylab_robodojo``).
    host: str
    #: Knowledge file stem (``knowledge/<knowledge>.md``).
    knowledge: str
    #: How the contract names the robot: "a dual-arm ARX-X5 robot in the RoboDojo benchmark".
    blurb: str
    #: Example ``robo.show(...)`` calls quoted by the on-demand image note.
    show_examples: str = "`robo.show(<camera>)`"
    #: Services the robot object is bound to besides the simulator, as a
    #: phrase: "a SAM3 segmentation service".
    services: str = ""

    @property
    def cameras(self) -> tuple[str, ...]:
        return tuple(getattr(self.robot_cls, "CAMERAS", ()))

    def host_module(self) -> Any:
        return importlib.import_module(self.host)


def get_adapter(name: str) -> RobotAdapter:
    """Return the adapter of robot ``name`` (one of :data:`ROBOTS`)."""

    if name not in ROBOTS:
        raise ValueError(f"unknown robot {name!r}; known: {ROBOTS}")
    module = importlib.import_module(f"robodojo.{name}")
    adapter = getattr(module, "ADAPTER", None)
    if not isinstance(adapter, RobotAdapter):
        raise ImportError(f"robodojo.{name} defines no ADAPTER")
    return adapter


__all__ = ["ROBOTS", "RobotAdapter", "get_adapter"]
