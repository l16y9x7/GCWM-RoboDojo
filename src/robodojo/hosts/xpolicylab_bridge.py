# Copyright 2026 PyRUA-Lean Contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""Between XPolicyLab's two calls and an environment a program steps.

XPolicyLab's evaluation client owns the simulator and asks a policy for actions: it sends an
observation (``update_obs``) and asks what to do (``get_action``).  An episode of this
package is the other way round: a program calls a tool, the tool steps the environment and
reads what came of it.  :class:`Bridge` turns one into the other.  The policy server answers
``get_action`` with the next native action a tool has asked for; the tool's ``step`` returns
when the client has taken it and sent the observation that followed.

A model thinks for minutes between two actions, far longer than the client waits for one
answer, so ``get_action`` never holds the client longer than ``poll_s``: when no tool has
stepped by then it answers :data:`WAIT`, and the adapter's ``deploy.py`` asks again.  An empty
answer means the program has finished.  ``deploy.py`` adds the episode's step count and limit
to each observation (``additional_info["robodojo"]``) and reports the benchmark's verdict
when the episode is over (the protocol's ``trial_end``, which the server hands to
``on_trial_end``).

The adapter's ``model.py`` is the ``Model`` XPolicyLab's policy server serves; it hands each
call to a :class:`Bridge`.
"""

from __future__ import annotations

import copy
import threading
import time
from typing import Any

#: ``get_action``'s answer while the program is still thinking.
WAIT = [{"robodojo": "wait"}]
#: The key ``deploy.py`` puts the episode's status under, in an observation's additional_info.
STATUS_KEY = "robodojo"


class EpisodeOver(RuntimeError):
    """The evaluation client has ended the episode: no observation will follow."""


class Bridge:
    """One episode's meeting point of the evaluation client and the tools."""

    def __init__(self, poll_s: float = 20.0) -> None:
        self._cv = threading.Condition()
        self.poll_s = poll_s
        self._obs: dict[str, Any] | None = None
        self._serial = 0
        self._action: dict[str, Any] | None = None
        self._finished = False
        self._over: dict[str, Any] | None = None
        self._status: dict[str, Any] = {}
        self._frame_subscribers: set[Any] = set()
        self.resets = 0

    # -- the evaluation client's side (the policy server calls these) -------------------------

    def reset(self) -> None:
        with self._cv:
            self.resets += 1
            self._cv.notify_all()

    def update_obs(self, obs: dict[str, Any]) -> None:
        callbacks: tuple[Any, ...]
        frame_event: dict[str, Any] | None = None
        with self._cv:
            info = (obs.get("additional_info") or {}).get(STATUS_KEY)
            if isinstance(info, dict):
                self._status = dict(info)
            self._obs = obs
            self._serial += 1
            callbacks = tuple(self._frame_subscribers)
            if callbacks:
                vision = obs.get("vision") or {}
                images = {
                    name: copy.deepcopy(cam["color"])
                    for name, cam in vision.items()
                    if isinstance(cam, dict) and cam.get("color") is not None
                }
                if images:
                    frame_event = {
                        "seq": self._serial,
                        "step": self._status.get("step"),
                        "images": images,
                    }
            if frame_event is not None:
                for callback in callbacks:
                    callback(frame_event)
            self._cv.notify_all()

    def subscribe_frames(self, callback: Any) -> None:
        """Receive an immutable image snapshot for each observation as it arrives."""
        with self._cv:
            self._frame_subscribers.add(callback)

    def unsubscribe_frames(self, callback: Any) -> None:
        with self._cv:
            self._frame_subscribers.discard(callback)

    def get_action(self) -> list[dict[str, Any]]:
        with self._cv:
            self._cv.wait_for(lambda: self._action is not None or self._finished, self.poll_s)
            if self._action is not None:
                action, self._action = self._action, None
                self._cv.notify_all()
                return [action]
            return [] if self._finished else WAIT

    def episode_end(self, info: dict[str, Any] | None) -> None:
        with self._cv:
            self._over = dict(info or {})
            self._cv.notify_all()

    # -- the tools' side ------------------------------------------------------------------------

    def first_obs(self, timeout_s: float, alive: Any = None) -> dict[str, Any]:
        """The first observation of the episode; ``alive()`` false means the client died."""

        deadline = time.monotonic() + timeout_s
        with self._cv:
            while self._obs is None:
                if self._over is not None:
                    raise EpisodeOver("the episode ended before it began")
                if alive is not None and not alive():
                    raise RuntimeError("the evaluation client exited before its first observation")
                left = deadline - time.monotonic()
                if left <= 0:
                    raise TimeoutError(
                        f"no observation from the evaluation client in {timeout_s:.0f} s"
                    )
                self._cv.wait(min(left, 2.0))
            return self._obs

    def get_obs(self) -> dict[str, Any]:
        with self._cv:
            if self._obs is None:
                raise RuntimeError("no observation yet")
            return self._obs

    def status(self) -> dict[str, Any]:
        with self._cv:
            status = dict(self._status)
            if self._over is not None:
                status["over"] = True
                # nothing more can be done: the budget is what has been spent
                status["step_limit"] = status.get("step", 0)
            return status

    @property
    def over(self) -> dict[str, Any] | None:
        with self._cv:
            return None if self._over is None else dict(self._over)

    def step(self, action: dict[str, Any], timeout_s: float = 600.0) -> dict[str, Any]:
        """Have the client take one native action; returns the observation that follows.

        Raises :class:`EpisodeOver` when the client ended the episode on that action (the task
        is solved, or the budget is spent) or had ended it before.
        """

        deadline = time.monotonic() + timeout_s
        with self._cv:
            if self._over is not None or self._finished:
                raise EpisodeOver("the episode is over")
            before = self._serial
            self._action = action
            self._cv.notify_all()
            while self._serial == before and self._over is None:
                left = deadline - time.monotonic()
                if left <= 0:
                    self._action = None
                    raise TimeoutError(f"the evaluation client did not answer in {timeout_s:.0f} s")
                self._cv.wait(min(left, 2.0))
            if self._serial == before:
                raise EpisodeOver("the episode ended on this action")
            assert self._obs is not None
            return self._obs

    def finish(self) -> None:
        """The program has no more actions: the client judges the scene and ends the episode."""

        with self._cv:
            self._finished = True
            self._cv.notify_all()

    def abandon(self) -> None:
        """The client has left this episode (it reset): nothing more will come of it.

        A verdict the client has already reported stands.
        """

        with self._cv:
            self._finished = True
            if self._over is None:
                self._over = {"success": False, "abandoned": True}
            self._cv.notify_all()

    def verdict(self, timeout_s: float = 300.0, alive: Any = None) -> dict[str, Any] | None:
        """What the client reported at the end of the episode.

        ``None`` when nothing came in time or ``alive()`` turned false (the client died).
        """

        deadline = time.monotonic() + timeout_s
        with self._cv:
            while self._over is None:
                left = deadline - time.monotonic()
                if left <= 0 or (alive is not None and not alive()):
                    return None
                self._cv.wait(min(left, 2.0))
            return dict(self._over)


class BridgeEnv:
    """The environment :mod:`.robodojo_tools` steps, over a :class:`Bridge`."""

    def __init__(self, bridge: Bridge, alive: Any = None) -> None:
        self.bridge = bridge
        self.alive = alive  # false once the evaluation client's process has gone

    def get_obs(self) -> dict[str, Any]:
        return self.bridge.get_obs()

    def get_status(self) -> dict[str, Any]:
        return self.bridge.status()

    def step(self, action: dict[str, Any]) -> tuple[dict[str, Any], float, bool, dict[str, Any]]:
        try:
            obs = self.bridge.step(action)
            done = False
        except EpisodeOver:
            obs, done = self.bridge.get_obs(), True
        return obs, 0.0, done, {"status": self.bridge.status()}

    def episode_over(self) -> bool:
        """The client has ended the episode and reported its verdict."""

        return self.bridge.over is not None

    def conclude(self) -> None:
        self.bridge.finish()
        self.bridge.verdict(alive=self.alive)


__all__ = [
    "Bridge",
    "BridgeEnv",
    "EpisodeOver",
    "STATUS_KEY",
    "WAIT",
]
