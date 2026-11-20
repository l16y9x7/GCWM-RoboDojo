# Copyright 2026 PyRUA-Lean Contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""roboskylar: code-as-policy for RoboDojo.

Derived from PyRUA-Lean. A language model writes Python against ``robo``;
this package turns those calls into joint targets for RoboDojo's own
evaluation client.
"""

from ._backend import Backend, CallRecord, EpisodeFinished, Ledger, ToolError
from ._robot import RobotBase
from .prompt import PromptBundle, TaskCard, api_reference, knowledge_text, render_prompt
from .robots import ROBOTS, RobotAdapter, get_adapter
from .runner import PolicyLoadError, PolicyOutcome, load_policy, run_policy

__version__ = "0.1.0"

__all__ = [
    "Backend",
    "CallRecord",
    "EpisodeFinished",
    "Ledger",
    "PolicyLoadError",
    "PolicyOutcome",
    "PromptBundle",
    "ROBOTS",
    "RobotAdapter",
    "RobotBase",
    "TaskCard",
    "ToolError",
    "api_reference",
    "get_adapter",
    "knowledge_text",
    "load_policy",
    "render_prompt",
    "run_policy",
    "__version__",
]
