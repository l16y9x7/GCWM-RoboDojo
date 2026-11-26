# Copyright 2026 PyRUA-Lean Contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""Drive one episode: boot the robot over RoboDojo's evaluation client and run the agent.

:func:`play_episode` is what the XPolicyLab adapter's ``model.py`` calls for each episode.
The host (``robodojo.hosts.xpolicylab_robodojo``) wraps the evaluation client's observations
in the robot class, :class:`robodojo.arms.ArmToolkit` gives the agent its ``python`` and
``finish`` tools, and :func:`robodojo.openai_runtime.run_openai_agent` runs the conversation
against an OpenAI-compatible endpoint.  This module owns the budget and ``result.json``.
One episode per call.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from ._backend import Ledger
from .arms import ArmToolkit, arm_contract, robot_words
from .hosts.common import RESULT_SCHEMA, stop_all
from .openai_runtime import run_openai_agent
from .prompt import api_reference, knowledge_text
from .robots import RobotAdapter, get_adapter
from .sandbox import DESCRIPTION as SANDBOX_DESCRIPTION


def _recordable(options: dict[str, Any]) -> dict[str, Any]:
    """What of a host's boot options ``result.json`` can hold: live objects by their type."""

    kept: dict[str, Any] = {}
    for key, value in options.items():
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            kept[key] = f"<{type(value).__name__}>"
        else:
            kept[key] = value
    return kept


def _conclude(backend: Any) -> None:
    """Tell a backend that the policy has finished, where it wants to know.

    A host that runs RoboDojo's own evaluation loop lets that loop judge the scene once, when
    the policy is done: its backend has ``conclude()``.
    """

    conclude = getattr(backend, "conclude", None)
    if callable(conclude):
        conclude()


def build_prompt(
    card: Any,
    *,
    budget_s: int,
    images: str = "on-motion",
    feedback: str = "rich",
    budget_mode: str = "wall",
    adapter: RobotAdapter | None = None,
) -> str:
    """The agent's prompt: contract, API reference, knowledge, task card."""

    adapter = adapter or get_adapter(getattr(card, "robot", "robodojo_xpl_rgb"))
    contract = arm_contract(
        budget_s=budget_s,
        max_env_steps=card.max_env_steps,
        images=images,
        feedback=feedback,
        budget_mode=budget_mode,
        robot=robot_words(adapter),
    )
    reference = api_reference(adapter.robot_cls)
    return "\n\n".join(
        [
            contract.rstrip(),
            "# API reference (the `robo` object)\n\n" + reference,
            knowledge_text(adapter.knowledge).strip(),
            card.render(),
        ]
    )


def play_episode(
    cell: Any,
    out_dir: Path,
    *,
    model: str,
    budget_s: float = 1200.0,
    base_url: str | None = None,
    api_key_env: str | None = None,
    images: str = "on-motion",
    feedback: str = "rich",
    max_attempts: int = 3,
    max_turns: int | None = None,
    robot: str = "robodojo_xpl_rgb",
    boot_options: dict[str, Any] | None = None,
    openai_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one episode on ``cell`` and write ``result.json``.

    ``robot`` selects the adapter (robot class, host module, knowledge); ``cell`` is that
    host's ``Cell`` and ``boot_options`` its ``boot`` keyword arguments (the bridge the
    adapter serves).  The agent runs in-process against ``base_url`` (else ``OPENAI_BASE_URL``
    or ``ROBODOJO_BASE_URL``), the key read from ``api_key_env`` (else ``OPENAI_API_KEY``);
    ``openai_options`` are :func:`run_openai_agent`'s keyword arguments (``temperature``,
    ``max_tokens``, ``extra_body``, ``image_max_side``, ``nudges`` ...).  ``max_turns``
    switches the episode to a decision budget: at most that many tool calls, ``budget_s``
    then being only a safety ceiling that the prompt does not mention.
    """

    adapter = get_adapter(robot)
    host = adapter.host_module()
    boot_options = dict(boot_options or {})
    out_dir.mkdir(parents=True, exist_ok=True)
    workspace = out_dir / "workspace"
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir()
    started = time.perf_counter()
    result: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "system": "robodojo",
        "backend": adapter.name,
        "robot": adapter.name,
        "suite": cell.suite,
        "task": cell.task,
        "seed": cell.seed,
        "task_language": None,
        "model": model,
        "images": images,
        "feedback": feedback,
        "max_turns": max_turns,
        "budget_mode": "calls" if max_turns else "wall",
        "environment_success": False,
        "status": "boot_error",
        "reason": None,
        "error": None,
        "finish": None,
        "calls": 0,
        "stateful_calls": 0,
        "env_steps": 0,
        "tool_turns": 0,
        "policy_wall_s": None,
        "startup_s": None,
        "total_wall_s": None,
        "timeout_s": budget_s,
        "max_episode_steps": cell.max_episode_steps,
        "prompt": None,
        "generation": None,
        "host": {
            "python": sys.executable,
            "cuda_device": cell.cuda_device,
        },
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "robodojo": {
            "evaluation_id": str(boot_options.get("robodojo_run_id") or "") or None,
            "trial_id": boot_options.get("trial_id"),
            "action_case_id": boot_options.get("action_case_id"),
        },
        "notes": [],
    }
    toolkit = None
    daemons: list[Any] = []
    live_calls_path = out_dir / "calls.live.jsonl"

    def live_call_hook(phase: str, record: Any, context: dict[str, Any]) -> None:
        """Append primitive start/end events while the agent is executing."""
        payload = record.to_dict()
        payload["phase"] = phase
        payload["cell"] = context.get("cell")
        payload["tool_context"] = context.get("tool")
        with live_calls_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
            handle.flush()

    ledger = Ledger(live_hook=live_call_hook)
    arm_toolkit: ArmToolkit | None = None
    try:
        toolkit, daemons = host.boot(cell, out_dir, **boot_options)
        result["host"]["boot_options"] = _recordable(boot_options)
        if result["robodojo"].get("evaluation_id"):
            result["robodojo"]["source"] = "xpolicylab.websocket"
        result["host"]["sandbox"] = SANDBOX_DESCRIPTION
        result["startup_s"] = time.perf_counter() - started
        backend = host.make_backend(toolkit)
        card = host.dump_card(toolkit, cell, out_dir)
        result["task_language"] = card.task_language
        robo = adapter.robot_cls(backend, ledger=ledger)
        # The contract tells the agent its working directory is the scratch workspace; make
        # that true for code run by the `python` tool.  Everything the host touches from here
        # on uses absolute paths.
        os.chdir(workspace)
        arm_toolkit = ArmToolkit(
            robo,
            workspace=workspace,
            images=images,
            feedback=feedback,
            max_turns=max_turns,
        )
        prompt = build_prompt(
            card,
            budget_s=int(budget_s),
            images=images,
            feedback=feedback,
            budget_mode="calls" if max_turns else "wall",
            adapter=adapter,
        )
        (out_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        result["prompt"] = {
            "chars": len(prompt),
            "sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "images": list(card.images.values()),
        }
        events_path = out_dir / "openai_events.jsonl"
        events_path.write_bytes(b"")  # fresh for this episode; retries below append
        images_in = list(card.images.values())
        if not base_url:
            base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("ROBODOJO_BASE_URL")
        if not base_url:
            raise ValueError("the agent needs a base URL (OPENAI_BASE_URL or ROBODOJO_BASE_URL)")
        result["host"]["base_url"] = base_url
        policy_started = time.perf_counter()
        attempts = 0
        generation: dict[str, Any] | None = None
        while True:
            attempts += 1
            remaining = budget_s - (time.perf_counter() - policy_started)
            if remaining <= 0:
                status, returncode = "timeout", None
                break
            generation = run_openai_agent(
                prompt,
                images_in,
                arm_toolkit,
                model=model,
                base_url=base_url,
                api_key=(
                    os.environ.get(api_key_env) if api_key_env else os.environ.get("OPENAI_API_KEY")
                ),
                max_turns=max_turns,
                budget_s=remaining,
                out_dir=out_dir,
                on_timeout=lambda: robo._stop_episode("timeout"),
                # a backend whose environment somebody else owns says when that owner has
                # ended the episode
                should_stop=getattr(backend, "episode_over", None),
                **(openai_options or {}),
            )
            status, returncode = generation["status"], generation["returncode"]
            if status == "error":
                # The provider failed after the retries: judged below like any other provider
                # failure (planner_error when nothing was solved and finish was never called).
                status = "completed"
            # A planner that died before touching the robot (provider overload, 429, transport
            # error) is retried; the episode state is untouched.
            if (
                status == "completed"
                and generation.get("errors")
                and not arm_toolkit.turns
                and attempts < max_attempts
            ):
                result["notes"].append(
                    f"attempt {attempts}: planner failed before any tool call; retrying"
                )
                time.sleep(15)
                continue
            break
        result["policy_wall_s"] = time.perf_counter() - policy_started
        result["status"] = status
        result["reason"] = "timeout" if status == "timeout" else None
        result["openai_returncode"] = returncode
        result["planner_attempts"] = attempts
        result["generation"] = generation or {
            "runtime": "openai",
            "errors": ["the wall clock expired before the agent started"],
            "tool_calls": {},
        }
        result["finish"] = arm_toolkit.finish
        result["generation"]["sandbox_flags"] = arm_toolkit.sandbox_flags
        if arm_toolkit.sandbox_flags:
            result["notes"].append(
                f"{len(arm_toolkit.sandbox_flags)} cell(s) raised sandbox audit flags; "
                "see tool_turns.json"
            )
        _conclude(backend)
        result["environment_success"] = bool(backend.solved())
        if (
            status == "completed"
            and arm_toolkit.turn_budget_exhausted
            and not result["environment_success"]
        ):
            result["status"] = "call_budget"
            result["reason"] = f"call budget exhausted ({max_turns})"
        if (
            result["status"] == "completed"
            and result["generation"].get("errors")
            and arm_toolkit.finish is None
            and not result["environment_success"]
        ):
            # The provider dropped the session (overload, 429, transport) and the agent never
            # got to finish: an infrastructure failure, to be rerun rather than counted
            # against the agent.
            result["status"] = "planner_error"
            result["reason"] = "provider error mid-episode"
        result["env_steps_total"] = backend.env_steps()
        if status == "completed" and returncode != 0:
            result["notes"].append(f"the agent loop exited {returncode}")
        if result["generation"].get("errors"):
            result["notes"].append(f"the agent loop reported errors; see {events_path.name}")
    except BaseException as exc:  # noqa: BLE001 - the result records the failure
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
        if result["status"] == "boot_error":
            result["notes"].append("host failed before the agent started")
        else:
            result["status"] = "error"
    finally:
        result["calls"] = len(ledger)
        result["stateful_calls"] = ledger.stateful_calls()
        result["env_steps"] = ledger.env_steps()
        if arm_toolkit is not None:
            result["tool_turns"] = len(arm_toolkit.turns)
            (out_dir / "tool_turns.json").write_text(
                json.dumps(arm_toolkit.turns, indent=2, ensure_ascii=False) + "\n"
            )
        ledger.write_jsonl(out_dir / "calls.jsonl")
        stop_all(toolkit, daemons)
        result["total_wall_s"] = time.perf_counter() - started
        (out_dir / "robodojo.json").write_text(
            json.dumps(result["robodojo"], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (out_dir / "result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return result


__all__ = ["build_prompt", "play_episode"]
