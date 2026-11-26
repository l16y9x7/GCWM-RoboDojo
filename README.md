# robodojo

GCWM 团队提交给 RoboDojo Agent Track 的 agent。包名、命令和 XPolicyLab 适配器都叫 `robodojo`。代码派生自 PyRUA-Lean 和 RPent，来源和许可见 [`NOTICE`](NOTICE)。

标"待确认"的内容需要团队核实后再填写。

## 目录

1. [提交信息](#1-提交信息)
2. [方法简介](#2-方法简介)
3. [仓库结构](#3-仓库结构)
4. [安装与运行](#4-安装与运行)
5. [API 披露](#5-api-披露)
6. [上下文组装说明](#6-上下文组装说明)
7. [技能库说明和清单](#7-技能库说明和清单)
8. [外部模型和服务清单](#8-外部模型和服务清单)
9. [评测记录](#9-评测记录)
10. [开源发布承诺](#10-开源发布承诺)
11. [待确认事项](#11-待确认事项)

## 1. 提交信息

| 项目 | 内容 |
| --- | --- |
| 团队 | GCWM |
| 赛道 | RoboDojo Agent Track（仿真） |
| 模型类型 | Agent |
| 决策模型 | `gpt-6.2-astra`，通过 API 接入 |
| VLA | 无 |
| 训练或微调 | 无，不加载任何策略权重 |
| 机器人配置 | `env_cfg_type=arx_x5`，`action_type=joint` |
| 提交版本 | 待确认（冻结版本的 commit 和 tag） |
| 提交方式 | 待确认（XPolicyLab PR、私有仓库或直接发送） |
| 联系人 | 待确认 |

## 2. 方法简介

robodojo 是一个 code-as-policy agent。语言模型在回合进行中一次写一段 Python（一个 cell），调用机器人对象 `robo`，看执行结果后再写下一段，直到任务完成或预算用完。

一局的流程如下：

1. RoboDojo 的评测客户端通过 XPolicyLab 的 websocket 发来观察：三路彩色图（头部相机、左右腕部相机）、两臂关节和末端状态、官方 Detail Description（`extra_info.detailed_instruction`）。
2. agent 收到一份提示词：工具约定、`robo` API 参考、通用操作知识、本局任务卡。任务卡里的任务描述就是官方 Detail Description 原文。
3. 模型通过 `python` 工具写代码。`robo` 的运动调用在策略进程里求解逆运动学，变成双臂关节目标，逐步交给评测客户端执行，每一步都正常消耗评测步数。
4. 物体位置靠 SAM3 分割彩色图后测量：头部相机的掩码给出物体在桌面上的占地范围，看到同一物体的腕部相机给出高度。没有深度图，也不读物体位姿。
5. 每次运动后，工具结果把相机图和机器人状态返回给模型，模型据此判断进展。场景满足任务后，RoboDojo 自己结束本局；模型也可以调用 `finish` 提前结束。

所有任务共用同一套提示词、工具、配置和模型，没有按任务切换的代码路径、记忆或预写流程。

**方法创新点**：待确认（规则要求有架构或方法上的创新，需要团队写明）。

**论文或技术报告**：待确认（已发布的链接，或发布计划和预计时间）。

## 3. 仓库结构

| 路径 | 作用 |
| --- | --- |
| `integrations/xpolicylab/robodojo/` | XPolicyLab 适配器：`eval.sh`、`deploy.py`、`model.py`、`deploy.yml`、安装和资源下载脚本。放到 XPolicyLab 的 `policy/robodojo` 下使用，`deploy.yml` 的 `policy_name` 与目录名一致 |
| `src/robodojo/` | 策略本体：agent 循环（`openai_runtime.py`、`play.py`）、工具和约定（`arms.py`）、提示词组装（`prompt.py`）、`robo` API（`robodojo.py`、`robodojo_xpl_rgb.py`）、代码沙箱（`sandbox.py`） |
| `src/robodojo/hosts/` | 评测 host：XPolicyLab 桥接、逆运动学、SAM3 测量、运动原语 |
| `src/robodojo/knowledge/robodojo_xpl_rgb.md` | 进入提示词的通用操作知识，所有任务相同 |
| `tests/` | 单元测试 |
| `pyproject.toml`、`uv.lock` | 包定义和依赖锁定 |

## 4. 安装与运行

### 环境要求

- 策略环境里已装好 CUDA 版 `torch` 和对应的 `torchvision`。`install.sh` 不会安装或改动它们。
- 策略 GPU 显存约 8 GB（SAM3）。
- 仿真环境只需要 RoboDojo 自己的安装，不需要额外依赖。

### 安装

适配器要放在 XPolicyLab 的 `policy/` 下再执行 `install.sh`，脚本用 `../..` 找 XPolicyLab：

```bash
ln -s <本仓库>/integrations/xpolicylab/robodojo \
    <RoboDojo>/XPolicyLab/policy/robodojo
bash <RoboDojo>/XPolicyLab/policy/robodojo/install.sh
bash <RoboDojo>/XPolicyLab/policy/robodojo/download_assets.sh
```

`install.sh` 依次安装 XPolicyLab、本仓库的 `robodojo` 包、固定版本的 SAM3，最后检查能否导入。适配器目录如果是复制出去的（不是软链接），要把本仓库路径或 pip 安装地址作为参数传给 `install.sh`。`download_assets.sh` 把 SAM3 权重（3.4 GB）下载到 `./checkpoints/sam3.pt`，加参数 `modelscope` 改用 ModelScope 镜像。

### 模型端配置

```bash
export OPENAI_BASE_URL=https://YOUR_API_HOST/v1
export OPENAI_API_KEY=...
export ROBODOJO_MODEL=gpt-6.2-astra
```

其他环境变量：`ROBODOJO_BASE_URL`、`ROBODOJO_API_KEY_ENV`（指定从哪个环境变量读 key）、`ROBODOJO_RESULT_DIR`、`SAM3_CHECKPOINT_PATH`。API key 只通过环境变量传入，不写进代码和配置。

### 跑一局

从 RoboDojo 根目录运行，`--policy-dir` 指向适配器，`action_type` 必须是 `joint`：

```bash
bash scripts/robodojo.sh eval --policy-dir XPolicyLab/policy/robodojo \
    --task stack_blocks --ckpt no-checkpoint --policy-env <policy_env> \
    --eval-env <eval_env> --env-cfg arx_x5 --action-type joint --seed 0
```

也可以在适配器目录里用 `eval.sh`，参数说明见 [`integrations/xpolicylab/robodojo/README.md`](integrations/xpolicylab/robodojo/README.md)。`EVAL_ENV_TYPE=debug` 可以在不接仿真、不调用模型的情况下检查连线。

不接仿真时查看 API 参考和完整提示词：

```bash
python -m robodojo api
python -m robodojo prompt
```

## 5. API 披露

决策模型是第三方闭源模型，通过 API 调用，按规则的第三方基础模型例外处理：不提供模型权重，提供评测期间可调用的接口和以下披露信息。API key 私下提供给组委会，不公开。

### 模型

| 项目 | 内容 |
| --- | --- |
| 供应商 | 待确认 |
| 模型标识 | `gpt-6.2-astra` |
| 固定版本或快照 | 待确认（如果供应商不支持锁定版本，要在这里说明） |
| 接口 | OpenAI 兼容的 Chat Completions（`POST {base_url}/chat/completions`），使用 function calling |
| Endpoint 地址 | 待确认（只在私下提供给组委会） |
| 评测期间的可用性和额度 | 待确认 |

### 推理参数

以下取值来自 `integrations/xpolicylab/robodojo/deploy.yml` 和 `src/robodojo/openai_runtime.py` 的默认值，所有任务相同。

| 参数 | 取值 | 说明 |
| --- | --- | --- |
| `max_tokens` | 8192 | 单次回复上限 |
| `reasoning_effort` | `high` | 通过 `extra_body` 传给接口 |
| `temperature` | 不传 | 使用供应商默认值，待确认具体数值 |
| `tool_choice` | `auto` | |
| 工具 | `python`、`finish` | 定义见第 7 节 |
| `max_context_images` | 40 | 每次请求最多保留的图片数，超出时先删最旧的 |
| `image_max_side` | 0 | 图片不缩放 |
| `nudges` | 20 | 模型连续不调用工具时的提醒次数上限，用完结束本局 |
| `max_turns` | 100 | 每局最多 100 次工具调用 |
| `budget_s` | 5400 | 每局墙钟上限（秒），只作安全上限，不写进提示词 |
| 单次请求超时 | 900 s | `ROBODOJO_OPENAI_TIMEOUT_S` |
| 重试 | 10 次 | 网络错误和 5xx 重试；429 限流另外等待，最长间隔 120 s，不计入重试次数 |

### 版本一致性

- 每局的 `result.json` 记录请求时用的模型名、endpoint 地址和全部推理参数，`openai_events.jsonl` 记录每次请求的 token 用量。
- 版本锁定方式：待确认。
- 评测日期：待确认（正式评测时记录）。
- 发现供应商侧模型变更的方法：待确认。目前代码不记录接口响应里的模型版本字段（如响应中的 `model`、`system_fingerprint`），需要的话要补上。
- 规则要求：评测中如果发现供应商侧模型版本变化，要报告组委会。

## 6. 上下文组装说明

本节说明模型在一局里看到哪些内容、这些内容从哪里来。结论是：与任务相关的文本只有官方 Detail Description，其余内容对所有任务都一样。

### 提示词组成

提示词由 `src/robodojo/play.py` 的 `build_prompt` 拼接，按顺序分为四部分：

| 部分 | 来源 | 是否随任务变化 |
| --- | --- | --- |
| 1. 工具约定和交互协议 | `src/robodojo/arms.py`（`CELLS_CONTRACT`、`INTERACTION_PROTOCOL` 等常量） | 不变。只代入部署配置（图片策略、反馈模式、预算） |
| 2. `robo` API 参考 | `src/robodojo/prompt.py` 的 `api_reference`，运行时从机器人类的函数签名和 docstring 生成 | 不变 |
| 3. 通用操作知识 | `src/robodojo/knowledge/robodojo_xpl_rgb.md` | 不变。内容是工具和仿真器的行为、坐标约定、判断进展的方法，不含任务配方和评分细节 |
| 4. 任务卡 | `src/robodojo/prompt.py` 的 `TaskCard.render`，由 `src/robodojo/hosts/xpolicylab_robodojo.py` 的 `dump_card` 填写 | 随每局变化，内容见下表 |

### 任务卡内容

| 字段 | 来源 |
| --- | --- |
| 任务描述 | 官方 Detail Description，即观察里的 `extra_info.detailed_instruction`，原样放在 `<<<` 和 `>>>` 之间（`src/robodojo/hosts/robodojo_native.py` 的 `instruction_of`） |
| 任务变体 | 评测客户端提供的变体（`variant`），提供时才出现 |
| 两臂初始位姿和夹爪开度 | 第一帧观察里的机器人本体状态 |
| 动作预算 | 环境的步数上限 |
| 初始图像 | 第一帧观察的三路彩色图，作为图片附在同一条消息里 |

任务卡不包含任务名、评测 seed、layout、物体位姿和成功标志。任务名和 seed 只写进本局记录，不进入提示词，也不发给模型。

### 运行中的上下文

- 模型每次调用 `python` 工具，结果以文本返回：标准输出、异常、最后一个表达式的值、机器人状态。相机图按 `deploy.yml` 的 `images: on-sim-step` 附上：每个改变状态的原语执行期间收到的全部帧，按接收顺序排列。模型可以用 `image_return` 参数改变单次调用的返回方式。
- 每次请求最多保留 40 张图（`max_context_images`），超出时先删最旧的。文本历史全部保留。
- 模型连续回复文本而不调用工具时，系统发固定的提醒语（`openai_runtime.py` 的 `NUDGE_TEXT`），最多 20 次。

### 本局记忆

- 计划、总结和中间变量都是模型在本局运行中自己生成的，存在本局的对话历史和 Python 命名空间里。
- 每局新建对话、新建 Python 命名空间，工作目录在开局时清空重建（`play.py` 的 `play_episode`）。
- 没有跨局记忆、检索库或预写的任务流程。前面各局的结果不会进入后面各局的上下文。

### 演示数据

不使用官方演示数据，也不使用其他任何演示数据。

### 核对方法

- 每局的完整提示词保存在本局目录的 `prompt.txt`，`result.json` 记录它的字符数和 SHA-256。
- 每局发给模型的全部消息保存在 `messages.json`，图片另存为文件、在消息里用引用代替。
- `python -m robodojo prompt` 用占位任务卡打印提示词，可以和各局的 `prompt.txt` 对比。

## 7. 技能库说明和清单

技能库是一组固定的通用工具，与任务无关，在正式评测前冻结。模型在运行中用这些工具编写本局的程序。本局生成的程序和函数只存在于本局的 Python 命名空间，不会写回技能库。

### 模型可调用的工具

定义在 `src/robodojo/arms.py` 的 `ArmToolkit.get_tools_spec`。

| 工具 | 参数 | 作用 |
| --- | --- | --- |
| `python` | `code`，可选 `image_return`（`all`、`final`、`none`） | 在本局持久的 Python 命名空间里执行代码。命名空间里预置了 `robo`、`np`、`math`、`time` 和 `display(image)`（附上处理后的图片） |
| `finish` | `status`（`success`、`failure`、`stuck`）、`summary` | 结束本局 |

### `robo` 对象的方法

机器人类是 `RobodojoOfficialColourRobot`（`src/robodojo/robodojo_xpl_rgb.py`，继承自 `src/robodojo/robodojo.py` 的 `RobodojoRobot`）。`python -m robodojo api` 打印完整的签名和说明。

**观察**

| 方法 | 作用 |
| --- | --- |
| `robo.task` | 本局的任务描述（官方 Detail Description） |
| `robo.state(step=-1)` | 两臂状态：抓取点位置、夹爪朝向（pitch、yaw、roll）、末端位姿、夹爪开度、六个关节角，以及是否用完动作预算 |
| `robo.image(camera, resolution="high", step=-1)` | 读取某个相机某一步的彩色图，返回 RGB 数组（480×640×3） |
| `robo.sim_frames(step=-1, sim_step=None)` | 读取某个原语执行期间收到的全部帧，按接收顺序 |
| `robo.camera_meta(camera, step=-1)` | 相机的内参和位姿，由机器人状态和固定的相机安装参数算出 |
| `robo.show(camera)` | 把某个相机的当前图片附到本次工具结果里 |
| `robo.artifact(name, step=-1)` | 读取本局记录的原始图片文件 |

**感知**（SAM3 分割，只用彩色图）

| 方法 | 作用 |
| --- | --- |
| `robo.segment(text_prompt, camera="cam_head", min_score=0.2)` | 按文字描述分割当前图片里的一个物体，返回掩码中心、面积和置信度 |
| `robo.locate(text_prompt, camera="cam_head", min_score=0.2)` | 按文字描述找物体并测量 3D：中心、顶面高度、占地长宽、朝向、建议的抓取角 `grasp_yaw`。多个相机都看到时才能测出高度 |
| `robo.back_project(row, col, camera="cam_head")` | 返回某个像素看到的世界坐标点 |

**运动**（每次调用阻塞到动作完成，每个原生动作消耗一个评测步）

| 方法 | 作用 |
| --- | --- |
| `robo.move_to(xyz, arm="right", gripper=0, pitch=None, yaw=None, roll=None, path="auto")` | 把一只手臂的抓取点移到指定位置和朝向。内部求解逆运动学，可行时走直线（每步约 2.5 cm 或 8°），否则直接转关节；目标不可达或会碰桌面时不动，并返回原因 |
| `robo.set_gripper(arm, gripper, opening=None)` | 开合一只夹爪，手臂不动。返回最终开度、是否夹住了东西、夹住物体的宽度 |
| `robo.home(arm="both")` | 手臂回到本局开始时的关节角 |

**常量和结果类型**

- 常量：`robo.LEFT`、`robo.RIGHT`、`robo.ARMS`、`robo.CLOSE`（1）、`robo.OPEN`（-1）、`robo.KEEP`（0）。
- 结果类型：`State`、`ArmState`、`Move`、`Gripper`、`Home`、`ObjectSight`、`Segment`、`SeenPoint`。都是不可变的 dataclass。

### 内置的固定参数

工具里用到的参数都是机器人和默认场景的常量，所有任务和所有局都相同。它们取自 RoboDojo 的公开配置，或者在自建仿真场景里测量一次得到：

- 头部相机的位姿和焦距，腕部相机的安装位置（`env_cfg/camera`）
- 两臂基座位姿、连杆几何和关节限位（`env_cfg/robot`、URDF）
- 桌面高度和范围（`env_cfg/scene/default.yml`）
- 夹爪开度和宽度的换算关系

### 代码执行沙箱

模型写的代码在受限环境里执行（`src/robodojo/sandbox.py`）：

- 只能导入纯计算模块（`numpy`、`scipy`、`cv2`、`PIL`、`skimage`、`math`、`json` 等）和本局工作目录里的 `.py` 文件。
- `open()` 只能访问本局工作目录。
- 去掉了 `exec`、`eval`、`compile`；用到 `__globals__`、`__subclasses__` 这类内省属性的代码执行前就会被拒绝。
- 每段代码都做审计，结果记为 `sandbox_flags`。
- 已知限制：沙箱在进程内实现，白名单里的部分模块（如 `io`、`numpy`、`cv2`）本身能读写文件，所以挡不住所有文件访问。待确认：是否需要 OS 级隔离，以及组委会能否接受进程内沙箱加审计日志的做法。

## 8. 外部模型和服务清单

| 名称 | 用途 | 版本或来源 | 许可 |
| --- | --- | --- | --- |
| `gpt-6.2-astra` | 写程序、做决策的语言模型，通过 API 调用 | 供应商和固定版本待确认，见第 5 节 | 第三方闭源，待确认 |
| SAM3（`sam3` 包） | 按文字描述分割彩色图，用于物体定位和测量 | `git+https://github.com/RLinf/sam3.git@c1f6b1e83967c912f675d8975d437ccdc41e17d8` | 待确认 |
| SAM3 权重 `sam3.pt` | SAM3 的 checkpoint（3.4 GB） | Hugging Face 或 ModelScope 上的 `facebook/sam3`，由 `download_assets.sh` 下载 | 待确认 |
| XPolicyLab | policy server 和 websocket 协议 | RoboDojo 仓库自带，版本待确认 | 待确认 |
| RoboDojo | 仿真和评测客户端 | 官方提供，版本待确认 | 待确认 |
| PyRUA-Lean | 本仓库代码的上游 | https://github.com/DAGroup-PKU/PyRUA-Lean | Apache-2.0 |
| RPent | 部分代码的上游（经 PyRUA-Lean） | https://github.com/RLinf/RPent | Apache-2.0 |

除上表外，不使用其他模型、服务、数据集或任务相关资源。

## 9. 评测记录

每局的记录写在 `result_dir` 下的 `<task>_s<seed>-<time>/`（默认是适配器目录下的 `./results/`），包含：

| 文件 | 内容 |
| --- | --- |
| `result.json` | 本局结果、状态、模型名、推理参数、提示词的长度和 SHA-256、步数和用时 |
| `prompt.txt` | 本局的完整提示词 |
| `card.json` | 本局任务卡 |
| `messages.json` | 发给模型和模型返回的全部消息，图片换成文件引用 |
| `openai_events.jsonl` | 每次请求的事件和 token 用量 |
| `request_log/requests.jsonl` | 每次请求包含哪些消息和图片 |
| `tool_turns.json` | 每次工具调用的代码、输出和沙箱审计结果 |
| `calls.jsonl`、`calls.live.jsonl` | `robo` 原语的调用记录 |
| `robodojo.json` | 与 RoboDojo 交互的记录 |
| `steps/NNNN/` | 每个原语执行期间收到的相机帧（`sim_NNN/`）、最终帧（`final/`）和索引 `frames.json`；`steps/0000/` 是初始观察 |

记录里不含 layout、物体位姿等隐藏信息，layout 字段记为 -1。正式评测的分数由 RoboDojo 的 `eval_result/` 给出。

## 10. 开源发布承诺

GCWM 团队承诺：在成绩上榜后三天内，通过 XPolicyLab 公开 "Open-Source Artifact for Verified Publication" 要求的全部材料，包括：

- 部署代码、harness、system prompt 和提示词模板、工具、配置文件
- 加载、推理、部署和评测说明
- 第三方模型的 API 披露信息（第 5 节）
- 开发和评测日志，覆盖 Agent Track 规则第 5 节列出的内容：各组件版本、通用组件的改动、开发数据来源和评测流程、汇总得分和失败分析、正式评测记录和执行结果、最终版本与开发历史的对应关系

API key 等凭据不公开。本方案没有训练或微调，因此没有训练代码和 checkpoint 需要公开。

## 11. 待确认事项

| 事项 | 所在章节 |
| --- | --- |
| 冻结版本的 commit 和 tag、提交方式、联系人 | 1 |
| 方法创新点、论文或技术报告的发布情况 | 2 |
| 模型供应商、固定版本或快照、endpoint、评测期间的可用性和额度 | 5 |
| `temperature` 的实际取值（目前不传，用供应商默认值） | 5 |
| 版本锁定方式、发现模型变更的方法，以及是否记录响应里的版本字段 | 5 |
| 沙箱是否需要 OS 级隔离，组委会能否接受当前做法 | 7 |
| 各外部组件的版本和许可 | 8 |
| 开发和评测日志的整理和发布 | 10 |
