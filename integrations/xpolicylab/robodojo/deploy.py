"""The evaluation loop of the robodojo adapter.

The policy is a program a language model writes while the episode runs: between two actions it
may think for minutes, and it decides itself when it has finished.  The loop is demo_policy's
with three differences, each because of that:

* ``get_action`` is asked again while it answers "wait" (the policy server never holds one
  request longer than a few seconds, so the client's request timeout stays what it is);
* an empty answer means the program has finished: the episode ends there and RoboDojo judges
  the scene as it stands;
* every observation carries the episode's step count and limit, which the program needs to
  budget its motions (``additional_info["robodojo"]``); the benchmark's verdict is reported
  to the policy server once the episode is over (the protocol's ``trial_end``).

Nothing else is read from the environment: the observation is the one RoboDojo's client
builds, the actions are joint targets.  The task's name, the eval seed and the layout are not
sent to the policy server.
"""

from __future__ import annotations

from typing import Any


def _status(task_env: Any, env_idx: int = 0) -> dict[str, Any]:
    info: dict[str, Any] = {}
    # RoboDojo's environment counts per environment; XPolicyLab's debug environment has one
    # counter and its own names
    taken = getattr(task_env, "take_action_cnt", None)
    try:
        info["step"] = int(taken[env_idx])
    except (TypeError, IndexError, ValueError):
        if isinstance(getattr(task_env, "episode_step", None), int):
            info["step"] = task_env.episode_step
    for name in ("step_lim", "episode_step_limit"):
        try:
            info["step_limit"] = int(getattr(task_env, name))
            break
        except (TypeError, ValueError, AttributeError):
            continue
    # The task's name, the eval seed and the layout are the evaluator's: none of them is sent
    # to the policy (RoboDojo Agent Track rule, sections 1, 2 and 6)
    return info


def _waiting(actions: Any) -> bool:
    return (
        isinstance(actions, (list, tuple))
        and len(actions) == 1
        and isinstance(actions[0], dict)
        and actions[0].get("robodojo") == "wait"
    )


def _judge_as_it_stands(task_env: Any) -> None:
    """Mark an episode the program left unfinished as failed; RoboDojo keeps its progress score.

    A completed task has already ended the episode (RoboDojo checks after every
    action).  RoboDojo starts each episode with ``success`` set and counts an
    episode that returns with it still set as a success, so it must be cleared.
    """

    if task_env.is_episode_end() or not hasattr(task_env, "success"):
        return  # over already, or an environment with nothing to judge (the debug one)
    running = (
        task_env.get_running_env_idx_list()
        if hasattr(task_env, "get_running_env_idx_list")
        else [0]
    )
    for env_idx in running:
        task_env.success[env_idx] = False
    task_env.is_episode_end()


def eval_one_episode(TASK_ENV: Any, model_client: Any) -> None:
    model_client.call(func_name="reset")
    try:
        while not TASK_ENV.is_episode_end():
            obs = TASK_ENV.get_obs()
            info = dict(obs.get("additional_info") or {})
            info["robodojo"] = _status(TASK_ENV)
            obs["additional_info"] = info
            model_client.call(func_name="update_obs", obs=obs)
            actions = model_client.call(func_name="get_action")
            while _waiting(actions):
                actions = model_client.call(func_name="get_action")
            if not actions:
                break  # the program has finished
            for action in actions:
                TASK_ENV.take_action(action)
                if TASK_ENV.is_episode_end():
                    break
    finally:
        _judge_as_it_stands(TASK_ENV)
        verdict = dict(_status(TASK_ENV))
        try:
            verdict["success"] = bool(TASK_ENV.success[0])
        except (TypeError, IndexError, AttributeError):
            verdict["success"] = False
        try:
            model_client.call(func_name="trial_end", obs=verdict)
        except Exception as exc:  # noqa: BLE001 - the trial stands whether or not it was heard
            print(f"[robodojo] the verdict did not reach the policy server: {exc}", flush=True)


def eval_one_episode_batch(TASK_ENV: Any, model_client: Any) -> None:
    num_envs = int(getattr(TASK_ENV, "num_envs", 1) or 1)
    if num_envs > 1:
        raise RuntimeError(
            f"RoboDojo started {num_envs} environments; robodojo drives one conversation per "
            "environment.  Keep eval_batch: false in deploy.yml."
        )
    eval_one_episode(TASK_ENV, model_client)
