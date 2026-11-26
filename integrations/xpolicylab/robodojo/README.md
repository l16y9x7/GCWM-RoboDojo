# robodojo

**Contributor:** GCWM | **Based on:** [PyRUA-Lean](https://github.com/DAGroup-PKU/PyRUA-Lean) (Apache-2.0; see `NOTICE` of the robodojo repository)

`robodojo` runs a code-writing agent on RoboDojo: a language model writes Python against a small robot API (`robo`), one cell at a time, while the episode runs; each motion call becomes native joint actions. The same program-writing loop, the same primitives and the same prompt serve every task: nothing is tuned, routed or stored per task. There is no VLA and no training entry; SAM3 (segmentation) is the only model the policy side loads. The adapter is evaluation-only and supports `bench_name=RoboDojo`, `env_cfg_type=arx_x5`, `action_type=joint`.

Shared conventions — argument meanings, checkpoint naming, split-machine deployment, `EVAL_ENV_TYPE` — are documented in the [XPolicyLab README](../../README.md). Official results: [RoboDojo LeaderBoard](https://robodojo-benchmark.com/LeaderBoard).

## Installation

Inside the policy environment (any environment with a CUDA build of `torch` and the `torchvision` built for it; `install.sh` installs neither and keeps both as they are):

```bash
cd XPolicyLab/policy/robodojo
bash install.sh              # XPolicyLab's server, the robodojo package, the sam3 package
bash download_assets.sh      # SAM3's checkpoint (3.4 GB) into ./checkpoints/sam3.pt
```

`install.sh` installs the robodojo package from the checkout this directory is linked from; it takes a robodojo checkout or pip requirement as its argument when the directory was copied out of it. `download_assets.sh modelscope` fetches the checkpoint from the ModelScope mirror; `SAM3_CHECKPOINT_PATH` names a checkpoint kept elsewhere. The simulator's environment needs nothing beyond RoboDojo's own installation.

## Data Processing

Unsupported: there is no dataset. `process_data.sh` is omitted (evaluation-only adapter).

## Training

Unsupported: nothing is trained and there is no checkpoint directory. `train.sh` is omitted (evaluation-only adapter).

## Evaluation

The programs are written by a model behind an OpenAI-compatible chat endpoint:

```bash
export OPENAI_BASE_URL=https://YOUR_API_HOST/v1
export OPENAI_API_KEY=...
export ROBODOJO_MODEL=<model name>         # the model's name at that endpoint

cd XPolicyLab/policy/robodojo
bash eval.sh <bench_name> <task_name> <ckpt_name> <env_cfg_type> <action_type> <seed> \
  <policy_gpu_id> <env_gpu_id> <policy_conda_env> <eval_env_conda_env>

# Example
bash eval.sh RoboDojo stack_blocks no-checkpoint arx_x5 joint 0 0 0 robodojo RoboDojo

# Offline wiring check (no simulator, no model call)
EVAL_ENV_TYPE=debug bash eval.sh RoboDojo stack_bowls no-checkpoint arx_x5 joint 0 0 0 robodojo RoboDojo
```

`action_type` must be `joint`: the program's poses are solved to joint targets by the package's own kinematics. `env_cfg_type` is `arx_x5`. `ckpt_name` is ignored; `no-checkpoint` is the conventional placeholder. Batch evaluation is not supported: one conversation drives one environment (`eval_batch: false`). The policy GPU holds SAM3 (about 8 GB). Each episode's programs, tool calls and transcript are kept under `result_dir` (`./results/<task>_s<seed>-<time>/`, named from the `task_name` and `seed` the policy server is started with; the layout is recorded as -1 there and is in RoboDojo's own `eval_result/`).

`EVAL_ENV_TYPE=debug` holds the robot where the debug client's observation has it: the loop, the action keys and their dimensions are exercised, and no episode is started.

## Configuration

Extra `deploy.yml` keys beyond the shared set:

| Key | Role |
| --- | --- |
| `robot` | `robodojo_xpl_rgb`: the robot the programs are written against, RoboDojo's default observation (three colour images and the robot's state) |
| `model` | the model that writes the programs, by its name at the OpenAI-compatible chat-completions endpoint (or `ROBODOJO_MODEL`) |
| `max_turns`, `budget_s` | an episode's decision budget (model replies that call a tool) and its wall-clock limit in seconds |
| `images`, `feedback` | `on-motion`: final camera images attach after movement; `on-primitive`: each state-changing primitive's final view attaches; `on-sim-step`: every Bridge frame received during each primitive attaches in receive order; `on-demand` attaches requested views; `none` disables automatic return. Each `python` call can override this with `image_return=all|final|none`; `display(image)` always attaches explicitly displayed processed images. `pure`: a tool call returns what the program printed and nothing else |
| `openai_options` | passed to the endpoint with every request (`max_tokens`, `max_context_images` defaults to 40, `extra_body.reasoning_effort`); `nudges` sets the text-only replies tolerated before the episode is ended |
| `poll_s` | the longest the policy server holds one `get_action` before answering "wait" |
| `wrap_up_s` | the longest the verdict's acknowledgement waits for the episode's record to be written |
| `result_dir` | where each episode's record is written, relative to this directory |

Environment variables: `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `ROBODOJO_MODEL` (above); `SAM3_CHECKPOINT_PATH` (default `./checkpoints/sam3.pt`); `ROBODOJO_RESULT_DIR` overrides `result_dir`.

### Observation

The policy reads what RoboDojo's client sends as it is configured (`env_cfg/arx_x5.yml`, unchanged): the three colour images, the joint and end-effector state and the task's official description (`extra_info.detailed_instruction`). It reads no depth image and no camera matrix; if a client sends them they are ignored. `setup_eval_env_client.sh` is `demo_policy`'s, and nothing in this directory touches the client's configuration.

Where an object is, is measured from its masks in the cameras that see it (SAM3): the head camera's mask bounds the object's footprint on the table, a wrist camera that sees the same object settles its height. That is good to a few millimetres for things up to about 6 cm tall, worse for tall things only one camera sees, and it cannot measure what does not stand on the table (an object in the gripper, on another object, in a rack).

Each episode also records the ordered camera observations received while a state-changing primitive is running under `steps/NNNN/sim_NNN/`, with the primitive's final observation under `steps/NNNN/final/`. `steps/0000/` contains the initial observation. Each step's `frames.json` indexes its received frames by Bridge sequence and source environment step; frame directories are numbered in receive order. Agent code can read a primitive's frames using `robo.sim_frames(step=NNNN)` and process the returned RGB NumPy arrays. See [simulation image frames](../../../doc/sim-image-frames.md) for the API and examples.

## Notes

- **What the policy reads.** The observation RoboDojo's client builds and nothing else: the colour images, the joint and end-effector state and the task's official description. No depth, no camera matrices, no object poses, no layout file, no success signal, no simulator handle: the policy server is a separate process that sees only what the protocol carries.
- **What is built in.** Constants of the embodiment and the default scene, the same for every task and episode, taken from RoboDojo's public configuration or measured once in the simulator: the head camera's pose and focal length and the wrist cameras' mounting (`env_cfg/camera`), the arms' base poses, link geometry and joint limits (`env_cfg/robot`, the URDF), the table top's height and extent (`env_cfg/scene/default.yml`), and the gripper's opening-to-width relation. With them a pixel is a known ray although the client sends no camera matrix.
- **What the model is told.** One text for every task (`src/robodojo/knowledge/robodojo_xpl_rgb.md`): how the tools behave and how to judge progress from images. It holds no task recipes and no scoring details: the only task-conditioned text is the task's official description, passed verbatim, and the final state an episode has to end in is read from that description.
- **`deploy.py` differs from `demo_policy`'s in three places**, each because the policy is a program a model writes while the episode runs: `get_action` is asked again while it answers "wait" (a model thinks for minutes; no request is held longer than `poll_s`); an empty answer means the program has finished (see below for how the episode then ends); every observation carries the episode's step count and limit (`additional_info["robodojo"]`), which the program budgets its motions by, and the verdict is reported back through the protocol's `trial_end` once the episode is over (it is recorded, the model never sees it). A task the program completes ends on its own: RoboDojo checks the scene after every action and ends the episode as soon as its checks pass. If the program finishes and the episode is still running, the scene did not meet the checks, so `deploy.py` marks the episode failed (it clears the environment's success flag and calls `is_episode_end()` once more), and RoboDojo scores it by the progress stages it reached. The flag has to be cleared: RoboDojo starts every episode with it set and counts an episode that returns with it still set as a success. Clearing it can only lower a score, never raise one. `policy/JoyAI_VL` and `policy/GPT_6_Astra_Direct_EEF/inspect` in XPolicyLab end early episodes the same way. `deploy.py` reads the step count and the step limit from the environment object, and nothing else; the task's name, the eval seed and the layout are not sent to the policy server, and the task card the model reads names neither the task nor the seed (RoboDojo Agent Track rule, sections 1 and 6).
- **Cost.** One episode is up to `max_turns` model calls with images; a rate-limited endpoint (HTTP 429) is waited out, not failed.
