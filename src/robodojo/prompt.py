# Copyright 2026 PyRUA-Lean Contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""Model-facing prompt built from the live library.

The API reference is generated from the robot class's signatures and
docstrings (``inspect``), so the model always sees exactly the functions the
host will inject. The default robot is ``robodojo_xpl_rgb``. The operating
knowledge is a hand-written markdown file, the same for every task, for an agent that writes
code against the robot.
"""

from __future__ import annotations

import inspect
import json
import textwrap
from dataclasses import dataclass, field, fields, is_dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from ._robot import RobotBase

_HOST_ONLY = frozenset({"ledger", "backend"})
_LINE = 88


def _annotation(value: Any) -> str:
    if value is inspect.Parameter.empty:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, type):
        return value.__name__
    return str(value).replace("typing.", "")


def _format_parameters(sig: inspect.Signature) -> list[str]:
    parts: list[str] = []
    seen_kw_only = False
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        if param.kind is inspect.Parameter.KEYWORD_ONLY and not seen_kw_only:
            parts.append("*")
            seen_kw_only = True
        text = name
        annotation = _annotation(param.annotation)
        if annotation:
            text += f": {annotation}"
        if param.default is not inspect.Parameter.empty:
            text += f" = {param.default!r}" if annotation else f"={param.default!r}"
        parts.append(text)
    return parts


def _render_callable(owner: str, name: str, fn: Any) -> str:
    sig = inspect.signature(fn)
    params = _format_parameters(sig)
    ret = _annotation(sig.return_annotation)
    suffix = f" -> {ret}" if ret else ""
    head = f"{owner}.{name}({', '.join(params)}){suffix}"
    if len(head) > _LINE:
        joined = ",\n    ".join(params)
        head = f"{owner}.{name}(\n    {joined},\n){suffix}"
    doc = inspect.getdoc(fn) or ""
    return head + "\n" + textwrap.indent(doc, "    ") if doc else head


def _render_property(owner: str, name: str, prop: property) -> str:
    fn = prop.fget
    ret = ""
    if fn is not None:
        ret = _annotation(inspect.signature(fn).return_annotation)
    head = f"{owner}.{name}" + (f" -> {ret}" if ret else "") + "  (read-only attribute)"
    doc = inspect.getdoc(fn) if fn is not None else ""
    return head + ("\n" + textwrap.indent(doc, "    ") if doc else "")


def _render_result_type(cls: type) -> str:
    parts = []
    for item in fields(cls):
        parts.append(f"{item.name}: {_annotation(item.type)}")
    head = f"class {cls.__name__}({', '.join(parts)})"
    if len(head) > _LINE:
        head = f"class {cls.__name__}(\n    " + ",\n    ".join(parts) + ",\n)"
    extra = []
    for name, member in vars(cls).items():
        if isinstance(member, property) and not name.startswith("_"):
            ret = _annotation(inspect.signature(member.fget).return_annotation)
            doc = inspect.getdoc(member.fget) or ""
            extra.append(f"    .{name} -> {ret}: {doc}")
    doc = inspect.getdoc(cls) or ""
    body = textwrap.indent(doc, "    ") if doc else ""
    return "\n".join(part for part in [head, body, *extra] if part)


def _public_members(robot_cls: type) -> dict[str, Any]:
    """Public methods and properties in definition order, base classes first.

    An override keeps the position of the member it overrides, so a robot
    that re-documents ``image`` for its own cameras does not reorder the
    reference.  ``RobotBase``'s configuration attributes never show, and
    neither do the members the robot declares absent (``ABSENT_MEMBERS``).
    """

    absent = frozenset(getattr(robot_cls, "ABSENT_MEMBERS", ()))
    members: dict[str, Any] = {}
    for klass in reversed(robot_cls.__mro__):
        if klass is object:
            continue
        for name, member in vars(klass).items():
            if name.startswith("_") or name in _HOST_ONLY or name in absent:
                continue
            if isinstance(member, property) or inspect.isfunction(member):
                members[name] = member
    return members


def api_reference(robot_cls: type | None = None, *, var: str = "robo") -> str:
    """Render the policy-facing API of ``robot_cls`` from its live definition.

    With no class, the reference is ``robodojo_xpl_rgb``.
    """

    if robot_cls is None:
        from .robots import get_adapter

        robot_cls = get_adapter("robodojo_xpl_rgb").robot_cls
    sections: list[str] = []
    class_doc = inspect.getdoc(robot_cls) or ""
    sections.append(f"class {robot_cls.__name__}\n{textwrap.indent(class_doc, '    ')}")
    # Base-class configuration, ``RESULT_TYPES`` (rendered as the result-type
    # section below) and ``ClassVar``-annotated configuration are not
    # constants the policy needs.
    hidden = set(vars(RobotBase)) | {"RESULT_TYPES"}
    # A robot class may build on another robot's (the same robot on another host): what it
    # inherits from that one is as much its API as what it defines itself.
    lineage = [cls for cls in reversed(robot_cls.__mro__) if not issubclass(RobotBase, cls)]
    defined: dict[str, Any] = {}
    for cls in lineage:
        hidden |= {
            name
            for name, annotation in inspect.get_annotations(cls).items()
            if str(annotation).replace("typing.", "").startswith("ClassVar")
        }
        defined.update(vars(cls))
    constants = [
        f"{var}.{name} = {value!r}"
        for name, value in defined.items()
        if name.isupper() and not name.startswith("_") and name not in hidden
    ]
    if constants:
        sections.append("Constants:\n" + "\n".join(f"    {c}" for c in constants))
    members: list[str] = []
    for name, member in _public_members(robot_cls).items():
        if isinstance(member, property):
            members.append(_render_property(var, name, member))
        else:
            members.append(_render_callable(var, name, member))
    sections.append("Methods and attributes of `robo`:\n\n" + "\n\n".join(members))
    result_types = tuple(getattr(robot_cls, "RESULT_TYPES", ()))
    results = [_render_result_type(cls) for cls in result_types if is_dataclass(cls)]
    sections.append(
        "Result types (frozen dataclasses; access fields as attributes):\n\n" + "\n\n".join(results)
    )
    # A robot without ``done`` never ends an episode as "terminated".
    absent = frozenset(getattr(robot_cls, "ABSENT_MEMBERS", ()))
    reasons = "truncated | timeout | cancelled"
    if "done" not in absent:
        reasons = "terminated | " + reasons
    sections.append(
        "Exceptions:\n"
        "    ToolError(RuntimeError): a call was rejected or a service failed; "
        "catch it if you have a fallback.\n"
        "    ValueError: an argument was invalid (e.g. a planar move over "
        "0.30 m) - nothing was executed.\n"
        "    EpisodeFinished(BaseException): the episode is over "
        f"(reason: {reasons}); return."
    )
    return "\n\n".join(sections)


def knowledge_text(name: str = "robodojo_xpl_rgb") -> str:
    """Return the packaged operating-knowledge markdown (``knowledge/<name>.md``) for a backend."""

    path = resources.files("robodojo").joinpath(f"knowledge/{name}.md")
    return path.read_text(encoding="utf-8")


@dataclass
class TaskCard:
    """What the policy author is told about one evaluation cell.

    Everything here is what the robot's own first ``view_env_state`` shows, plus the
    task's official description; nothing privileged such as object poses is included.
    """

    suite: str
    task: int | str
    seed: int
    task_language: str
    object_names: list[str]
    images: dict[str, str] = field(default_factory=dict)
    max_env_steps: int = 10000
    #: Which robot the card describes (one of :data:`robodojo.robots.ROBOTS`).
    robot: str = "robodojo_xpl_rgb"
    #: Robot-specific initial facts rendered as extra bullets (both arms'
    #: initial pose, the action budget).
    facts: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, path: str | Path) -> TaskCard:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def render(self) -> str:
        """The card as the agent reads it: robot, facts, images, then the task description.

        The description is the benchmark's text as it came (for RoboDojo the official Detail
        Description, :func:`robodojo.hosts.robodojo_native.instruction_of`), between ``<<<``
        and ``>>>`` so that its line breaks and quotes reach the agent unchanged.

        The task's identity and its seed (the layout) stay out: RoboDojo's
        Agent Track allows no task-conditioned text but the official task
        description (rule sections 1 and 6).  ``task`` and ``seed`` remain on
        the card for the episode's records.
        """

        lines = [
            "# Task card",
            f"- robot: {self.robot}",
        ]
        if self.suite:
            lines.append(f"- variant: {self.suite}")
        if self.object_names:
            lines.append(f"- objects named by the benchmark: {', '.join(self.object_names)}")
        for key, value in self.facts.items():
            lines.append(f"- {key}: {value}")
        lines.append(f"- simulator step budget: {self.max_env_steps}")
        if self.images:
            names = ", ".join(f"{k} ({Path(v).name})" for k, v in self.images.items())
            cameras = ", ".join(f"`robo.image({k!r})`" for k in self.images)
            lines.append(
                f"- attached images: {names}. They are step 0 of your run, "
                f"exactly what {cameras} return before any motion."
            )
        lines += [
            "",
            "## Task description (official, authoritative)",
            "",
            "The benchmark's own description of this task, verbatim:",
            "",
            "<<<",
            self.task_language.strip(),
            ">>>",
        ]
        return "\n".join(lines)


__all__ = [
    "TaskCard",
    "api_reference",
    "knowledge_text",
]
