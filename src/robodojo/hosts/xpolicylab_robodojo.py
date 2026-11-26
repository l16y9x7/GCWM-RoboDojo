# Copyright 2026 PyRUA-Lean Contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""RoboDojo through its own evaluation client and XPolicyLab: the host of ``robodojo_xpl_rgb``.

RoboDojo's evaluation runs a policy as two processes that talk XPolicyLab's websocket
protocol: the evaluation client owns the simulator (``src/eval_client/main.py``), builds the
observation (three colour images and the robot's state, as its configuration has it) and
counts the task's own action budget; the policy server answers ``update_obs`` /
``get_action``.  XPolicyLab starts both; the adapter's ``model.py`` serves a
:class:`.xpolicylab_bridge.Bridge` and runs the episode, and :func:`boot` returns a
:class:`.robodojo_native.NativeToolkit` over that bridge once the first observation has
arrived.  Perception reads the colour images alone: a depth image or camera matrices, should
a client send them, are not read.

What the client decides stays the client's: when the task is solved it ends the episode at
once, and when the program has finished it judges the scene as it stands
(``backend.conclude()``).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..prompt import TaskCard
from ..robodojo import _arm_state
from .robodojo_cell import Cell, _fmt, _opening
from .robodojo_native import CAMERAS, NativeBackend, NativeToolkit
from .xpolicylab_bridge import Bridge, BridgeEnv

#: The robot this host serves.
ROBOT = "robodojo_xpl_rgb"
BOOT_TIMEOUT_S = 1500.0


def _toolkit(bridge: Bridge, cell: Cell, out_dir: Path, env_only: bool) -> NativeToolkit:
    """The robot's tools over ``bridge``; the verdict is the one the client reports."""

    sam3 = None
    if not env_only:
        from . import sam3_local

        sam3 = sam3_local.shared(cuda_device=cell.cuda_device)
    return NativeToolkit(
        BridgeEnv(bridge),
        sam3,
        out_dir,
        verdict=lambda: bool((bridge.over or {}).get("success")),
    )


def boot(
    cell: Cell,
    out_dir: Path,
    *,
    bridge: Bridge,
    env_only: bool = False,
    boot_timeout_s: float = BOOT_TIMEOUT_S,
    **_: Any,
) -> tuple[NativeToolkit, list[Any]]:
    """Wait for the evaluation client's first observation on ``bridge``; return
    ``(toolkit, daemons)``.

    The client is already talking to the policy server that serves ``bridge`` (XPolicyLab
    started both), so nothing is started here and there are no daemons to stop.
    ``env_only`` leaves SAM3 out (enough to dump a task card).
    """

    out_dir.mkdir(parents=True, exist_ok=True)
    bridge.first_obs(boot_timeout_s)
    return _toolkit(bridge, cell, out_dir, env_only), []


def make_backend(toolkit: NativeToolkit) -> NativeBackend:
    return NativeBackend(toolkit)


def dump_card(toolkit: NativeToolkit, cell: Cell, out_dir: Path) -> TaskCard:
    """Write ``card.json`` plus the step-0 images and return the card.

    Both arms' initial grasp points, gripper angles and openings, and the task's own
    native-action budget.  Nothing privileged.
    """

    record = toolkit.state.records[0]
    raw = record["state"]
    card_dir = out_dir / "card"
    card_dir.mkdir(exist_ok=True)
    images: dict[str, str] = {}
    for camera in CAMERAS:
        source = toolkit.state.artifact_path(f"{camera}.png", step=0)
        if source.is_file():
            target = card_dir / f"{camera}.png"
            shutil.copyfile(source, target)
            images[camera] = str(target)
    facts: dict[str, Any] = {}
    for arm in ("left", "right"):
        start = _arm_state(raw, arm)
        facts[f"{arm} arm initial grasp point [x, y, z]"] = f"{_fmt(start.tcp_pos)} m"
        facts[f"{arm} gripper initial pitch / yaw / roll"] = (
            f"{round(start.pitch)} / {round(start.yaw)} / {round(start.roll)} deg"
        )
        opening = _opening(raw.get(f"{arm}_ee_joint_state"))
        facts[f"{arm} gripper opening"] = f"{opening:.2f} (1 = open, 0 = closed)"
    try:
        budget = int(toolkit._status().get("step_limit"))
    except (TypeError, ValueError):
        budget = cell.max_episode_steps
    facts["native action budget"] = f"{budget} (a motion call spends one or more)"
    card = TaskCard(
        suite=cell.suite,
        task=cell.task,
        seed=cell.seed,
        task_language=record["instruction"],
        object_names=[],
        images=images,
        max_env_steps=budget,
        robot=ROBOT,
        facts=facts,
    )
    (out_dir / "card.json").write_text(card.to_json() + "\n", encoding="utf-8")
    return card


__all__ = ["Cell", "boot", "dump_card", "make_backend"]
