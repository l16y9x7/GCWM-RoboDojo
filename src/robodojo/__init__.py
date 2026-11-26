# Copyright 2026 PyRUA-Lean Contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""robodojo: code-as-policy for RoboDojo's Agent Track.

A language model writes Python against ``robo`` while the episode runs; this package turns
those calls into joint targets for RoboDojo's own evaluation client, through XPolicyLab.
"""

from ._backend import Backend, CallRecord, EpisodeFinished, Ledger, ToolError
from ._robot import RobotBase
from .prompt import TaskCard, api_reference, knowledge_text
from .robots import ROBOTS, RobotAdapter, get_adapter

__version__ = "0.1.0"

__all__ = [
    "Backend",
    "CallRecord",
    "EpisodeFinished",
    "Ledger",
    "ROBOTS",
    "RobotAdapter",
    "RobotBase",
    "TaskCard",
    "ToolError",
    "api_reference",
    "get_adapter",
    "knowledge_text",
    "__version__",
]
