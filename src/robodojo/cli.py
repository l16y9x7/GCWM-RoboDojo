# Copyright 2026 PyRUA-Lean Contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""Command line: print the robot API or the prompt the agent reads.

Episodes are run by RoboDojo's evaluation through the XPolicyLab adapter
(``integrations/xpolicylab/robodojo``), not from this command.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .arms import FEEDBACK_MODES, IMAGE_POLICIES
from .prompt import api_reference
from .robots import ROBOTS, get_adapter

DEFAULT_ROBOT = "robodojo_xpl_rgb"


def _api(args: argparse.Namespace) -> int:
    adapter = get_adapter(args.robot)
    print(api_reference(adapter.robot_cls))
    return 0


def _prompt(args: argparse.Namespace) -> int:
    """The prompt an episode sends, with placeholders where the episode fills in."""

    from .play import build_prompt
    from .prompt import TaskCard

    adapter = get_adapter(args.robot)
    card = TaskCard(
        suite="arx_x5",
        task="",
        seed=0,
        task_language="<the task's official description>",
        object_names=[],
        images={camera: f"<{camera} at step 0>" for camera in adapter.cameras},
        max_env_steps="<the task's step budget>",  # type: ignore[arg-type]
        robot=args.robot,
        facts={"initial arm state": "<both arms' initial state>"},
    )
    print(
        build_prompt(
            card,
            budget_s=args.budget_s,
            images=args.images,
            feedback=args.feedback,
            budget_mode="calls",
            adapter=adapter,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="robodojo", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    api = sub.add_parser("api", help="print the generated robot API")
    api.add_argument("--robot", default=DEFAULT_ROBOT, choices=ROBOTS)
    api.set_defaults(_run=_api)

    prompt = sub.add_parser("prompt", help="print the prompt the model sees (deploy.yml defaults)")
    prompt.add_argument("--robot", default=DEFAULT_ROBOT, choices=ROBOTS)
    prompt.add_argument("--budget-s", type=int, default=5400)
    prompt.add_argument("--images", default="on-sim-step", choices=IMAGE_POLICIES)
    prompt.add_argument("--feedback", default="pure", choices=FEEDBACK_MODES)
    prompt.set_defaults(_run=_prompt)

    args = parser.parse_args(argv)
    return args._run(args)
