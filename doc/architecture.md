# 代码架构

本文介绍 robodojo 的代码结构：评测时有哪些进程，一局（episode）从开始到结束经过哪些模块，以及每个文件负责什么。路径都相对仓库根目录。提示词全文见 [`actual-prompt.zh.md`](actual-prompt.zh.md)，模型交互范式见 [`agent-interaction.md`](agent-interaction.md)，图像帧存档见 [`sim-image-frames.md`](sim-image-frames.md)。

## 1. 总览

robodojo 是一个 code-as-policy 的 agent。没有策略权重。语言模型在回合进行中写 Python，调用 `robo` 对象；`robo` 的运动调用在本进程里解 IK，变成双臂关节目标，经 XPolicyLab 的 websocket 交给 RoboDojo 的评测客户端去执行。

评测时有两个进程，都由 XPolicyLab 启动：

```text
┌──────────────────────────────┐   websocket (XPolicyLab 协议)   ┌───────────────────────────────────────┐
│ 评测客户端 (eval env)         │ ─ reset / update_obs ────────▶ │ 策略服务端 (policy env)                │
│  RoboDojo 仿真器              │ ◀──────────── get_action ───── │  integrations/.../model.py  Model     │
│  integrations/.../deploy.py  │ ─ trial_end(成败) ───────────▶ │    └─ Bridge ── 后台线程跑一局 agent    │
│  eval_one_episode 循环        │                                │          play_episode → LLM → robo    │
└──────────────────────────────┘                                └───────────────────────────────────────┘
```

- 评测客户端拥有仿真器，负责构造观察（三路彩色图和关节状态）、计步、判定成败。`deploy.py` 是我们替换进去的评测循环。
- 策略服务端加载 `model.py` 的 `Model`。它不推理权重，而是在后台线程里跑一整局 agent 对话。
- 两边方向相反：XPolicyLab 是客户端“问”策略要动作，而 agent 是程序“主动”调工具推动仿真。`Bridge`（`src/robodojo/hosts/xpolicylab_bridge.py`）负责把这两种模型对接起来。

## 2. 目录结构

```text
src/robodojo/                 Python 包
├── cli.py, __main__.py       命令行：打印 API 参考或提示词（不跑仿真）
├── play.py                   一局的总控：启动 host、拼提示词、跑 agent、写 result.json
├── openai_runtime.py         agent 循环：OpenAI 兼容 chat-completions + function calling
├── arms.py                   给模型的两个工具 python / finish，以及控制约定（contract）文本
├── sandbox.py                模型代码的执行沙箱和审计
├── prompt.py                 从机器人类的签名和 docstring 生成 API 参考；TaskCard
├── knowledge/robodojo_xpl_rgb.md   手写的操作知识，拼进提示词
├── robots.py                 机器人注册表（RobotAdapter / get_adapter）
├── _backend.py               Backend 协议、ToolError、EpisodeFinished、调用账本 Ledger
├── _robot.py                 RobotBase：所有机器人类共用的调度、账本、图像访问
├── robodojo.py               RobodojoRobot：move_to / set_gripper / home / segment 等 API 和返回类型
├── robodojo_xpl_rgb.py       RobodojoOfficialColourRobot：只用彩色图的 locate / back_project；ADAPTER
└── hosts/                    host 层：把真实环境包装成 Backend
    ├── xpolicylab_robodojo.py    robodojo_xpl_rgb 的 host：boot / make_backend / dump_card
    ├── xpolicylab_bridge.py      Bridge（XPolicyLab 两个调用 ↔ 程序 step）和 BridgeEnv
    ├── robodojo_native.py        NativeToolkit / NativeBackend：工具分发、步骤记录、结果信封
    ├── robodojo_tools.py         工具实现：move_pose、grip、home、locate、back_project、probe
    ├── robodojo_kinematics.py    ARX-X5 双臂正逆运动学（URDF 拟合，本地求解）
    ├── robodojo_sight.py         无深度图的三维测量：相机位姿、射线、物体高度与形状
    ├── sam3_local.py             本进程内加载 SAM3，文本或像素提示 → 单个掩码
    ├── robodojo_cell.py          Cell：一个评测单元（任务、环境配置、布局号）
    └── common.py                 结果 schema 名和停止 host 的通用逻辑

integrations/xpolicylab/robodojo/   交给 XPolicyLab 的适配器（链接到 XPolicyLab/policy/robodojo）
├── model.py                  策略服务端的 Model
├── deploy.py                 评测客户端的评测循环
├── deploy.yml                部署配置（模型、预算、图像策略等）
└── *.sh                      安装、下载 SAM3 权重、启动两端、eval 入口

tests/                        单元测试（不需要仿真器和 GPU）
tools/render_actual_prompt.py 生成 doc/actual-prompt*.md 用的提示词快照
```

## 3. 一局的执行流程

### 3.1 评测客户端侧（`deploy.py`）

`eval_one_episode` 是 XPolicyLab demo_policy 循环的改写，改动有三处：

1. 每次 `update_obs` 前，在 `additional_info["robodojo"]` 里加上当前步数和步数上限，程序要靠它分配动作预算。任务名、评测种子和布局号不发给策略（Agent Track 规则第 1、2、6 节）。
2. `get_action` 回答 `[{"robodojo": "wait"}]` 表示模型还在想，客户端立即再问一次。这样单次请求不会超过 `poll_s`（默认 20 秒），客户端的请求超时设置不用改。
3. 回答空列表表示程序结束。循环退出后 `_judge_as_it_stands` 让 RoboDojo 按当前场景做最终判定，再用 `trial_end` 把成败告诉策略服务端。

### 3.2 策略服务端侧（`model.py`）

- `reset`：放弃上一局的 `Bridge`，新建一个。
- `update_obs`：把观察交给 `Bridge`。如果是本局第一个观察，就启动后台线程 `_play`，线程里调用 `robodojo.play.play_episode`。
- `get_action`：直接转发 `Bridge.get_action()`。
- `on_trial_end`：把客户端的判定交给 `Bridge`，最多等 `wrap_up_s`（默认 30 秒）让本局记录写完盘。这个时间必须远小于客户端 120 秒的请求超时。
- `EVAL_ENV_TYPE=debug` 时不启动模型，每步回一个“保持当前关节”的动作，只用来检查链路。
- 构造时检查 `action_type` 必须是 `joint`，环境必须是两条 6 关节臂、各 1 个夹爪关节（arx_x5）。

### 3.3 Bridge：反转控制方向

`Bridge` 用一个条件变量连接两个线程：

```text
程序线程（agent）                         服务端线程（XPolicyLab 调用）
robo.move_to(...)
  → move_pose 解出关节路径
  → 每个路点 BridgeEnv.step(action)
      Bridge.step: 放入 _action，等待 ─────▶ get_action 取走 _action 返回给客户端
                                              客户端执行 take_action
      ◀──────────────── 新观察到达 ────────── update_obs 写入 _obs，_serial+1，唤醒
  ← 返回新观察
```

- `get_action` 在 `poll_s` 内没有等到动作就回 `WAIT`。
- 程序结束后 `finish()` 置位，`get_action` 返回空列表。
- 客户端结束本局（任务成功或步数用完）后，`Bridge.step` 抛 `EpisodeOver`，运动调用随之失败。
- `subscribe_frames` 让 `NativeToolkit` 在运动原语执行期间存下每一帧图像（`on-sim-step` 图像策略用到）。

### 3.4 `play_episode`：一局的总控

`src/robodojo/play.py` 的 `play_episode` 按顺序做这些事：

1. `get_adapter(robot)` 取得机器人适配器，得到机器人类、host 模块、知识文件名。
2. `host.boot(cell, out_dir, bridge=...)` 等客户端第一个观察（最长 1500 秒），加载 SAM3，构造 `NativeToolkit`。
3. `host.make_backend` 得到 `NativeBackend`，`host.dump_card` 写出任务卡 `card.json` 和第 0 步三路图像。
4. 用 backend 和 `Ledger` 实例化机器人类，得到 `robo`；把工作目录切到 `out_dir/workspace`。
5. 用 `robo` 构造 `ArmToolkit`，调用 `build_prompt` 拼出提示词，写入 `prompt.txt`。
6. 调用 `run_openai_agent` 跑对话。模型在动机器人之前就因接口错误失败时，最多重试 `max_attempts`（3）次。
7. 调 `backend.conclude()`，读取 `backend.solved()`，归类本局状态：`completed`、`timeout`、`call_budget`、`planner_error`、`error`、`boot_error`。
8. 无论成败都在 `finally` 中写出 `result.json`、`calls.jsonl`、`tool_turns.json`、`robodojo.json`。

### 3.5 提示词组成（`build_prompt`）

提示词由四段按顺序拼接，每局一份，存为 `prompt.txt`：

| 段落 | 来源 | 内容 |
| --- | --- | --- |
| 控制约定 | `arms.arm_contract` | 工具用法、预算、图像策略、反馈模式、交互范式 |
| API 参考 | `prompt.api_reference` | 用 `inspect` 从机器人类的公开方法、签名、docstring 和返回 dataclass 生成 |
| 操作知识 | `knowledge/robodojo_xpl_rgb.md` | 手写，与任务无关，所有任务相同 |
| 任务卡 | `TaskCard.render` | 官方 Detail Description、两臂初始位姿和夹爪开度、动作步数预算 |

API 参考是从代码生成的，所以模型看到的函数和运行时注入的 `robo` 完全一致。机器人类里不打算给模型用的成员必须以下划线开头。

### 3.6 agent 循环（`openai_runtime.py`）

`run_openai_agent` 对任意 OpenAI 兼容的 `/v1/chat/completions` 端点做 function calling：

- 第一条用户消息是提示词加任务卡的三张初始图。
- 每次模型调用工具，就在本进程里执行 `ArmToolkit.execute_tool`，带超时（`_execute_with_deadline`）。工具结果的文本和图片作为下一条消息追加。
- `_Transcript` 维护发送用的消息和落盘用的副本（图片换成文件路径）。图片数量超过 `max_context_images`（默认 40）时从最旧的开始从请求里删去，磁盘上的图片保留。
- 模型只回文本、不调工具时，发提醒（`nudges`，默认 20 次）；用完提醒后结束。
- 停止条件：模型调用 `finish`、工具调用次数达到 `max_turns`、墙钟超过 `budget_s`（超时会先调 `robo._stop_episode`）、或 `should_stop()` 返回真（客户端已经结束本局）。
- 接口错误和 429 按 `retries` 重试。每次请求记录在 `request_log/requests.jsonl`，事件流记录在 `openai_events.jsonl`。

## 4. 分层结构

从模型写的一行 `robo.move_to(...)` 到仿真器里的一次 `env.step`，经过这些层：

```text
模型写的代码
  │  python 工具
ArmToolkit (arms.py)            持久命名空间、沙箱、图像策略、反馈打包
  │  robo.move_to(...)
RobodojoOfficialColourRobot     参数校验、返回类型化结果（Move / Gripper / ObjectSight …）
  └ RobodojoRobot → RobotBase   _stateful / _readonly：记账本、解信封、抛 ToolError
  │  backend.execute_tool("move_pose", kwargs)
NativeBackend → NativeToolkit   工具分发；状态变更工具执行后记录一步观察并包成信封
  │  tools.move_pose(primitives, ...)
robodojo_tools.py               IK 规划、直线插值、逐路点发关节目标
  ├ robodojo_kinematics.py      正逆运动学
  ├ robodojo_sight.py           视觉测量（locate / back_project 用）
  └ sam3_local.py               分割（segment / locate 用）
  │  env.step(action)
BridgeEnv → Bridge → XPolicyLab websocket → RoboDojo 仿真器
```

### 4.1 工具层（`arms.py`、`sandbox.py`）

模型只有两个工具：

- `python(code, image_return?)`：在持久命名空间里执行代码，像 notebook，前一格定义的变量下一格还能用。命名空间预置 `robo`、`np`、`math`、`time`、`display`、`log`。
- `finish(status, summary)`：结束本局，`status` 是 `success`、`failure` 或 `stuck`。

工具结果的内容由两个配置决定：

- `feedback`：`pure` 只返回标准输出、异常、末尾表达式的值和 `robo.show()` 请求的图；`rich` 再加上机器人状态、原语调用账本和步数。
- `images`：`on-motion`、`on-primitive`、`on-sim-step`、`on-demand`、`none`。单次调用可以用 `image_return=all|final|none` 覆盖。`display(image)` 输出的图始终附加。

`sandbox.py` 不能真正封住进程内的 Python，只做三件事：限制 `import` 到纯计算模块（numpy、scipy、cv2、PIL 等）和工作区文件；把 `open` 限制在工作区，移除 `exec`、`eval`、`compile` 等内建函数；代码里出现 `__globals__`、`__subclasses__` 这类自省名时拒绝执行。每格代码都做审计，标记写入 `tool_turns.json` 的 `sandbox_flags`。

### 4.2 机器人 API 层（`_robot.py`、`robodojo.py`、`robodojo_xpl_rgb.py`）

`RobotBase` 是与具体机器人无关的部分：

- `_stateful(tool, kwargs, build)`：用于会推动仿真的调用。先检查本局是否已结束，在账本里开一条记录，调用 backend，解开信封，遇到错误抛 `ToolError`，被取消时抛 `EpisodeFinished`，最后记下耗时和消耗的环境步数。
- `_readonly(...)`：用于只读调用，不检查结束状态，账本记为非状态变更。
- `image`、`state`、`sim_frames`、`show`、`artifact` 等观察接口。

`RobodojoRobot` 定义 RoboDojo 的 API 和返回类型（都是 frozen dataclass）：

| 方法 | 底层工具 | 类别 | 说明 |
| --- | --- | --- | --- |
| `move_to` | `move_pose` | 状态变更 | 一条臂的抓取点移到给定位置和 pitch/yaw/roll |
| `set_gripper` | `grip` | 状态变更 | 夹爪全行程开合，报告是否夹住东西 |
| `home` | `home` | 状态变更 | 回到本局开始时的关节位置 |
| `segment` | `segment` | 只读 | SAM3 分割，文本或像素提示 |
| `locate` | `locate` | 只读 | 分割加三维测量，返回物体中心、顶面高度、尺寸、建议抓取 yaw |
| `back_project` | `back_project` | 只读 | 某像素处物体表面的世界坐标 |
| `state` / `image` / `show` / `camera_meta` | `view_env_state` 等 | 只读 | 关节状态、相机图像、相机参数 |

RoboDojo 在回合中不报告任务是否成功，只在结束后判定场景。所以 `done` 和 `world_map` 列在 `ABSENT_MEMBERS` 里，访问会报错，也不出现在 API 参考中。这样模型写不出 `while not robo.done` 这种死循环。

`RobodojoOfficialColourRobot` 继承 `RobodojoRobot`，把 `locate`、`back_project`、`camera_meta` 改成只依赖彩色图和机器人状态的版本（评测客户端的 `env_cfg/arx_x5.yml` 关闭了深度图和相机矩阵）。模块末尾的 `ADAPTER` 把这个类、host 模块 `robodojo.hosts.xpolicylab_robodojo` 和知识文件注册给 `robots.py`。

### 4.3 host 层（`hosts/`）

host 层把评测客户端包装成 `_backend.Backend` 协议（`execute_tool`、`solved`、`artifact`、`sim_frames`、`env_steps`、`cancel`）。机器人类只通过这个协议访问环境，所以测试可以换成假 backend。

- `xpolicylab_robodojo.py`：`robodojo_xpl_rgb` 的 host 模块，提供 `Cell`、`boot`、`make_backend`、`dump_card` 四个入口，`play.py` 只通过这四个函数访问 host。成败判定直接取客户端在 `trial_end` 里报告的结果。
- `robodojo_native.py`：`NativeToolkit` 把工具名映射到 `robodojo_tools` 的函数。状态变更工具（`move_pose`、`grip`、`home`）执行完后，用 `Steps` 记录新的一步：状态保存在内存，图像写到 `steps/NNNN/`；执行过程中收到的每一帧写到 `steps/NNNN/sim_NNN/`。返回给机器人类的是带步号、状态和工具结果的“信封”。`NativeBackend` 是它外面薄薄的一层 `Backend` 实现。
- `robodojo_tools.py`：工具的具体实现。每个原生动作是一次 `env.step`，计入本局步数预算。`move_pose` 对目标姿态求 IK；两指可互换，所以也会尝试绕指向轴转 180° 的目标，取关节行程小的解；`path="line"` 时抓取点走直线，每 2.5 cm 或 8° 一个路点。`grip` 走完夹爪行程并根据开度判断是否夹住物体。`locate` 和 `probe` 组合 SAM3 掩码和 `robodojo_sight` 的测量结果。
- `robodojo_kinematics.py`：ARX-X5 双臂运动学，链结构来自基准的 URDF，底座位姿按仿真报告的末端位姿拟合（残差 0.00 mm / 0.000°）。仿真器自带的末端位姿动作在 IK 发散时会甩臂，所以在本地求解，下发关节角。包括 FK、雅可比、IK 求解、多解选择、桌面间隙检查、直线路径插值。
- `robodojo_sight.py`：没有深度图时的三维测量。头部相机固定，腕部相机固连在末端连杆上，所以每个像素对应一条已知射线。物体立在已知平面上时，用一个视角的掩码确定底面轮廓，用其他视角的掩码确定高度（棱柱、悬挂等形状假设），并排除机器人自身遮挡的像素。
- `sam3_local.py`：在本进程加载 SAM3（bfloat16），一张图加一个提示返回得分最高的一个掩码。权重由 `download_assets.sh` 下载。

### 4.4 账本与结果

- `Ledger`（`_backend.py`）记录每次原语调用的工具名、参数、成败、耗时、消耗步数和结果摘要。执行中通过 `live_hook` 实时追加到 `calls.live.jsonl`，结束时写成 `calls.jsonl`。
- `ArmToolkit.turns` 记录每次工具调用（第几格、是否移动、消耗步数、沙箱标记），写成 `tool_turns.json`。

## 5. 一局的输出目录

`result_dir`（默认 `./results`，可用 `ROBODOJO_RESULT_DIR` 覆盖）下每局一个目录 `<task>_s<seed>-<时间戳>/`：

| 文件 | 内容 |
| --- | --- |
| `result.json` | 本局汇总：状态、成败、调用次数、步数、耗时、提示词哈希、生成记录（schema `robodojo-episode-v2`） |
| `prompt.txt` | 发给模型的完整提示词 |
| `card.json`、`card/` | 任务卡和第 0 步三路图像 |
| `openai_events.jsonl` | agent 循环的事件流 |
| `request_log/requests.jsonl` | 每次模型请求的清单 |
| `images/` | 发给模型的所有图片 |
| `calls.jsonl`、`calls.live.jsonl` | 原语调用账本 |
| `tool_turns.json` | 每次工具调用的记录 |
| `steps/NNNN/` | 每个状态变更步的观察图像，`sim_NNN/` 是执行过程中的逐帧图像 |
| `workspace/` | 模型代码的工作目录 |
| `robodojo.json`、`batch_runtime.json` | 评测 ID 等对账信息 |

## 6. 配置

部署配置在 `integrations/xpolicylab/robodojo/deploy.yml`，由 XPolicyLab 传给 `Model.__init__`：

| 键 | 默认值 | 作用 |
| --- | --- | --- |
| `robot` | `robodojo_xpl_rgb` | 选用的机器人适配器 |
| `model` | `null`（取 `ROBODOJO_MODEL`） | 模型名 |
| `max_turns` | 100 | 工具调用次数预算 |
| `budget_s` | 5400 | 墙钟上限（秒） |
| `images` | `on-sim-step` | 自动附图策略 |
| `feedback` | `pure` | 工具结果的反馈模式 |
| `openai_options` | `max_tokens: 8192` 等 | 传给 `run_openai_agent` 的参数，含 `max_context_images`、`nudges`、`extra_body` |
| `poll_s` | 20 | `get_action` 最长等待时间 |
| `wrap_up_s` | 30 | `trial_end` 等待写盘的时间 |
| `action_type` | `joint` | 必须是 `joint` |
| `eval_batch` | `false` | 一个对话只驱动一个环境 |

模型端点用 `OPENAI_BASE_URL`（或 `ROBODOJO_BASE_URL`）和 `OPENAI_API_KEY`（或 `ROBODOJO_API_KEY_ENV` 指定的变量）。

## 7. 测试与工具

测试不需要仿真器和 GPU，用 `pytest` 运行：

- `test_openai_runtime.py`：transcript 的图片保留与淘汰、请求清单、各图像策略和 `image_return` 覆盖。
- `test_robodojo_motion.py`：运动学、IK、`move_pose` / `grip` / `home`。
- `test_robodojo_sight.py`：无深度测量。
- `test_robodojo_colour.py`：彩色版机器人类的 `locate`、`back_project` 等。
- `test_play.py`：检查控制约定里包含规划、动作检查点和图片上下文规则。

`python -m robodojo api` 打印 API 参考，`python -m robodojo prompt` 打印提示词。`tools/render_actual_prompt.py` 用占位任务卡生成 `doc/actual-prompt*.md` 中的提示词快照。
