# Copyright 2026 PyRUA-Lean Contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""One RoboDojo evaluation cell: a task, an environment config and a layout id.

Extracted from the RPent-backed host so the XPolicyLab host does not import it.
``seed`` is the layout id. ``max_episode_steps`` is nominal: the simulator
enforces the task's own ``step_lim``.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any

#: RoboDojo's ``--env-cfg-type`` values this package drives.
ENV_CONFIGS = ("arx_x5",)
#: Nominal step budget handed to a cell when the caller does not set one.
DEFAULT_MAX_EPISODE_STEPS = 700


@dataclass(frozen=True)
class Cell:
    """One RoboDojo evaluation cell."""

    suite: str
    task: str
    seed: int
    max_episode_steps: int = DEFAULT_MAX_EPISODE_STEPS
    cuda_device: int | None = None

    @property
    def tag(self) -> str:
        return f"{self.task}_l{self.seed}"


def add_cell_args(parser: argparse.ArgumentParser) -> None:
    """RoboDojo cell identifiers (``robodojo play --robot robodojo_xpl_rgb``)."""

    parser.add_argument("--task", required=True, help="RoboDojo task name, e.g. stack_blocks")
    parser.add_argument(
        "--suite", default="arx_x5", choices=ENV_CONFIGS, help="RoboDojo environment config"
    )
    parser.add_argument("--seed", type=int, default=0, help="layout id")


def cell_from_args(args: argparse.Namespace) -> Cell:
    return Cell(
        suite=str(getattr(args, "suite", None) or "arx_x5"),
        task=str(args.task),
        seed=int(args.seed),
        max_episode_steps=int(getattr(args, "max_episode_steps", DEFAULT_MAX_EPISODE_STEPS)),
        cuda_device=getattr(args, "cuda_device", None),
    )


def _fmt(values: Any) -> str:
    return "[" + ", ".join(f"{v:.3f}" for v in values) + "]"


def _opening(value: Any) -> float:
    """A gripper opening recorded as ``[0.97]`` (or a one-value numpy array)."""

    for _ in range(4):
        if value is None or isinstance(value, (int, float)):
            break
        try:
            value = next(iter(value))
        except (TypeError, StopIteration):
            break
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
