# Copyright 2026 PyRUA-Lean Contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""Command line: print the robot API, print the prompt, or run one episode."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from ._robot import PRIMITIVE_SETS
from .prompt import api_reference, render_prompt
from .robots import ROBOTS, get_adapter

DEFAULT_ROBOT = "robodojo_xpl_rgb"


def _api(args: argparse.Namespace) -> int:
    adapter = get_adapter(args.robot)
    print(api_reference(adapter.robot_cls, primitives=args.primitives))
    return 0


def _prompt(args: argparse.Namespace) -> int:
    from .prompt import TaskCard

    card = None
    if args.robot != DEFAULT_ROBOT:
        card = TaskCard(
            suite="arx_x5",
            task="",
            seed=0,
            task_language="",
            object_names=[],
            robot=args.robot,
        )
    bundle = render_prompt(card, budget_s=args.budget_s, primitives=args.primitives)
    print(bundle.system if args.system_only else bundle.text())
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "play":
        from .play import main as play_main

        return play_main(argv[1:])

    parser = argparse.ArgumentParser(prog="robodojo", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    api = sub.add_parser("api", help="print the generated robot API")
    api.add_argument("--robot", default=DEFAULT_ROBOT, choices=ROBOTS)
    api.add_argument("--primitives", choices=PRIMITIVE_SETS, default="no-vla")
    api.set_defaults(_run=_api)

    prompt = sub.add_parser("prompt", help="print the prompt the model sees")
    prompt.add_argument("--robot", default=DEFAULT_ROBOT, choices=ROBOTS)
    prompt.add_argument("--primitives", choices=PRIMITIVE_SETS, default="no-vla")
    prompt.add_argument("--budget-s", type=int, default=5400)
    prompt.add_argument("--system-only", action="store_true")
    prompt.set_defaults(_run=_prompt)

    args = parser.parse_args(argv)
    return args._run(args)
