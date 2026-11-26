# robodojo

robodojo 是 GCWM 团队提交至 RoboDojo Agent Track 的 Agent 系统。Python 包、命令行工具和 XPolicyLab 适配器均命名为 `robodojo`。本项目代码派生自 PyRUA-Lean 和 RPent，来源与许可信息见 [`NOTICE`](NOTICE)。

本文中的"回合"指一次评测 episode。

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

## 1. 提交信息

| 项目 | 内容 |
| --- | --- |
| 团队 | GCWM |
| 赛道 | RoboDojo Agent Track（仿真） |
| 模型类型 | Agent |
| 决策模型 | `gpt-6.2-astra`（第三方 API） |
| VLA | 不使用 |
| 训练或微调 | 无，不加载任何策略权重 |
| 机器人配置 | `env_cfg_type=arx_x5`，`action_type=joint` |
| 提交版本 | 待确认 |
| 联系人 | 待确认 |

## 2. 方法简介

robodojo 采用 code-as-policy 方法：在回合进行过程中，语言模型逐段编写 Python 代码，调用机器人接口 `robo` 完成感知和操作；每段代码执行后，模型根据返回的图像和机器人状态决定下一步，直至任务完成或预算耗尽。

单个回合的执行流程如下：

1. RoboDojo 评测客户端经 XPolicyLab websocket 发送观察，包括三路彩色图像（头部相机与左右腕部相机）、双臂本体状态和官方 Detail Description。
2. 系统组装提示词，内容包括工具约定、`robo` API 参考、通用操作知识和本回合任务卡。任务卡中的任务描述为官方 Detail Description 原文。
3. 模型通过 `python` 工具提交代码。运动指令在策略端经逆运动学求解为双臂关节目标，通过官方接口逐步执行，并正常消耗评测步数。
4. 每次运动完成后，相机图像和机器人状态返回给模型，用于判断任务进展。场景满足任务要求时由 RoboDojo 结束回合；模型也可调用 `finish` 主动结束。

所有任务使用同一套提示词、工具、配置和模型，不存在按任务选择的代码路径、记忆或预置流程。

**方法创新点**：待确认

**论文或技术报告**：待确认

## 3. 仓库结构

| 路径 | 说明 |
| --- | --- |
| `integrations/xpolicylab/robodojo/` | XPolicyLab 适配器，包括 `eval.sh`、`deploy.py`、`model.py`、`deploy.yml` 及安装和资源下载脚本。部署时置于 XPolicyLab 的 `policy/robodojo` 目录，`deploy.yml` 中的 `policy_name` 与目录名一致 |
| `src/robodojo/` | 策略主体：Agent 运行循环（`openai_runtime.py`、`play.py`）、工具与约定（`arms.py`）、提示词组装（`prompt.py`）、`robo` API（`robodojo.py`、`robodojo_xpl_rgb.py`）、代码沙箱（`sandbox.py`） |
| `src/robodojo/hosts/` | 评测宿主：XPolicyLab 桥接、逆运动学、SAM3 测量、运动原语 |
| `src/robodojo/knowledge/robodojo_xpl_rgb.md` | 提示词中的通用操作知识，所有任务相同 |
| `tests/` | 单元测试 |
| `pyproject.toml`、`uv.lock` | 包定义与依赖锁定 |

## 4. 安装与运行

### 环境要求

- 策略环境需预装 CUDA 版 `torch` 及与之匹配的 `torchvision`。`install.sh` 不安装、也不修改这两个包。
- 策略端 GPU 显存需求约 8 GB（用于 SAM3）。
- 仿真环境仅需 RoboDojo 官方安装，无额外依赖。

### 安装

将适配器置于 XPolicyLab 的 `policy/` 目录后执行安装脚本。`install.sh` 通过相对路径 `../..` 定位 XPolicyLab。

```bash
ln -s <本仓库路径>/integrations/xpolicylab/robodojo \
    <RoboDojo>/XPolicyLab/policy/robodojo
bash <RoboDojo>/XPolicyLab/policy/robodojo/install.sh
bash <RoboDojo>/XPolicyLab/policy/robodojo/download_assets.sh
```

`install.sh` 依次安装 XPolicyLab、本仓库的 `robodojo` 包和指定版本的 SAM3，并检查导入是否成功。若适配器目录以复制而非软链接方式部署，需将本仓库路径或 pip 安装地址作为参数传入 `install.sh`。`download_assets.sh` 将 SAM3 权重（3.4 GB）下载至 `./checkpoints/sam3.pt`；指定参数 `modelscope` 时改从 ModelScope 镜像下载。

### 模型接口配置

```bash
export OPENAI_BASE_URL=https://YOUR_API_HOST/v1
export OPENAI_API_KEY=<API key>
export ROBODOJO_MODEL=gpt-6.2-astra
```

可选环境变量：

| 变量 | 说明 |
| --- | --- |
| `ROBODOJO_BASE_URL` | 接口地址，设置时优先于 `OPENAI_BASE_URL` |
| `ROBODOJO_API_KEY_ENV` | 读取 API key 的环境变量名 |
| `ROBODOJO_RESULT_DIR` | 评测记录的输出目录 |
| `SAM3_CHECKPOINT_PATH` | SAM3 权重路径，默认 `./checkpoints/sam3.pt` |

API key 仅通过环境变量传入，不写入代码或配置文件。

### 运行评测

在 RoboDojo 根目录执行，`--policy-dir` 指向适配器目录，`--action-type` 须为 `joint`：

```bash
bash scripts/robodojo.sh eval --policy-dir XPolicyLab/policy/robodojo \
    --task stack_blocks --ckpt no-checkpoint --policy-env <policy_env> \
    --eval-env <eval_env> --env-cfg arx_x5 --action-type joint --seed 0
```

也可在适配器目录中使用 `eval.sh`，参数说明见 [`integrations/xpolicylab/robodojo/README.md`](integrations/xpolicylab/robodojo/README.md)。设置 `EVAL_ENV_TYPE=debug` 可在不连接仿真、不调用模型的情况下检查通信链路。

查看 API 参考和完整提示词（无需连接仿真）：

```bash
python -m robodojo api
python -m robodojo prompt
```

## 5. API 披露

决策模型为第三方闭源模型，通过 API 调用，适用评测协议中的第三方基础模型例外条款：不提供模型权重，改为提供评测期间可调用的接口及以下披露信息。API key 单独提供给组委会，不公开。

### 模型信息

| 项目 | 内容 |
| --- | --- |
| 供应商 | 待确认 |
| 模型标识 | `gpt-6.2-astra` |
| 固定版本或快照 | 待确认 |
| 接口类型 | OpenAI 兼容 Chat Completions（`POST {base_url}/chat/completions`），使用 function calling |
| 接口地址 | 单独提供给组委会 |
| 评测期间的可用性保障 | 待确认 |

### 推理参数

以下取值来自 `integrations/xpolicylab/robodojo/deploy.yml` 及 `src/robodojo/openai_runtime.py` 的默认值，所有任务一致。

| 参数 | 取值 | 说明 |
| --- | --- | --- |
| `max_tokens` | 8192 | 单次回复的 token 上限 |
| `reasoning_effort` | `high` | 经 `extra_body` 传递 |
| `temperature` | 未设置 | 采用供应商默认值（待确认） |
| `tool_choice` | `auto` | |
| 工具 | `python`、`finish` | 定义见第 7 节 |
| `max_context_images` | 40 | 单次请求保留的图像上限，超出时移除最早的图像 |
| `image_max_side` | 0 | 图像不缩放 |
| `nudges` | 20 | 模型未调用工具时的提醒次数上限，用尽后结束回合 |
| `max_turns` | 100 | 每回合的工具调用次数上限 |
| `budget_s` | 5400 | 每回合墙钟时间上限（秒），仅作安全保护，不写入提示词 |
| 单次请求超时 | 900 s | 可由 `ROBODOJO_OPENAI_TIMEOUT_S` 设置 |
| 重试 | 10 次 | 针对网络错误和 5xx 响应；HTTP 429 限流单独退避等待（最长间隔 120 s），不计入重试次数 |

### 版本一致性

- 每回合的 `result.json` 记录所用模型标识、接口地址和全部推理参数，`openai_events.jsonl` 记录每次请求的 token 用量。
- 版本锁定方式：待确认。
- 评测日期：正式评测时记录。
- 供应商侧模型变更的检测方式：待确认。
- 评测期间如发现供应商侧模型版本变化，团队将及时报告组委会。

## 6. 上下文组装说明

本节说明模型在回合中接收的全部内容及其来源。来自外部的任务相关文本仅有官方 Detail Description，其余内容对所有任务相同。

### 提示词构成

提示词由 `src/robodojo/play.py` 中的 `build_prompt` 依次拼接以下四部分：

| 部分 | 来源 | 是否随任务变化 |
| --- | --- | --- |
| 1. 工具约定与交互协议 | `src/robodojo/arms.py`（`CELLS_CONTRACT`、`INTERACTION_PROTOCOL` 等常量） | 否。仅代入部署配置（图像策略、反馈模式、预算） |
| 2. `robo` API 参考 | `src/robodojo/prompt.py` 中的 `api_reference`，运行时由机器人类的函数签名和 docstring 生成 | 否 |
| 3. 通用操作知识 | `src/robodojo/knowledge/robodojo_xpl_rgb.md` | 否。内容为工具与仿真器的行为、坐标约定和进展判断方法，不含任务流程或评分细节 |
| 4. 任务卡 | `src/robodojo/prompt.py` 中的 `TaskCard.render`，由 `src/robodojo/hosts/xpolicylab_robodojo.py` 中的 `dump_card` 填充 | 是，字段见下表 |

### 任务卡字段

| 字段 | 来源 |
| --- | --- |
| 任务描述 | 官方 Detail Description（观察中的 `extra_info.detailed_instruction`），原文置于 `<<<` 与 `>>>` 之间，读取逻辑见 `src/robodojo/hosts/robodojo_native.py` 中的 `instruction_of` |
| 任务变体 | 评测客户端提供的变体信息，仅在提供时出现 |
| 双臂初始位姿与夹爪开度 | 首帧观察中的机器人本体状态 |
| 动作预算 | 评测环境的步数上限 |
| 初始图像 | 首帧观察的三路彩色图像，以图像形式附于同一条消息 |

任务卡不包含任务名称、评测 seed、layout、物体位姿或成功标志。任务名称和 seed 仅写入回合记录，不进入提示词。

### 运行时上下文

- `python` 工具的返回内容包括标准输出、异常信息、末尾表达式的值和机器人状态。相机图像按 `deploy.yml` 中的 `images: on-sim-step` 策略附加，即每个改变状态的原语执行期间收到的全部帧，按接收顺序排列。模型可通过 `image_return` 参数调整单次调用的图像返回方式。
- 单次请求最多保留 40 张图像（`max_context_images`），超出时移除最早的图像；文本历史完整保留。
- 模型回复未调用工具时，系统发送固定提醒语（`src/robodojo/openai_runtime.py` 中的 `NUDGE_TEXT`），最多 20 次。

### 回合内记忆

- 计划、总结和中间变量均由模型在本回合运行时生成，仅保存在本回合的对话历史和 Python 命名空间中。
- 每个回合新建对话和 Python 命名空间，工作目录在回合开始时清空重建（见 `src/robodojo/play.py` 中的 `play_episode`）。
- 不使用跨回合记忆、检索库或预置任务流程，任何回合的结果均不进入其他回合的上下文。

### 演示数据

不使用官方演示数据，也不使用其他演示数据。

### 核验方式

- 每回合的完整提示词保存为回合目录下的 `prompt.txt`，其字符数和 SHA-256 记录在 `result.json` 中。
- 每回合与模型往来的全部消息保存在 `messages.json` 中，图像另存为文件并以引用代替。
- `python -m robodojo prompt` 以占位任务卡输出提示词，可与各回合的 `prompt.txt` 对照。

## 7. 技能库说明和清单

技能库由一组固定的通用工具构成，与具体任务无关，在正式评测前冻结。模型在运行时调用这些工具编写本回合的程序；本回合生成的程序和函数仅存在于本回合的 Python 命名空间，不写回技能库。

### 模型可调用的工具

工具定义见 `src/robodojo/arms.py` 中的 `ArmToolkit.get_tools_spec`。

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `python` | `code`；可选 `image_return`（`all`、`final`、`none`） | 在本回合持久的 Python 命名空间中执行代码。命名空间预置 `robo`、`np`、`math`、`time` 及 `display(image)`（附加处理后的图像） |
| `finish` | `status`（`success`、`failure`、`stuck`）、`summary` | 结束本回合 |

### `robo` 接口

机器人类为 `RobodojoOfficialColourRobot`（`src/robodojo/robodojo_xpl_rgb.py`），继承自 `RobodojoRobot`（`src/robodojo/robodojo.py`）。完整签名和说明可通过 `python -m robodojo api` 查看。

**观察**

| 方法 | 说明 |
| --- | --- |
| `robo.task` | 本回合的任务描述（官方 Detail Description） |
| `robo.state(step=-1)` | 双臂状态：抓取点位置、夹爪朝向（pitch、yaw、roll）、末端位姿、夹爪开度、六个关节角，以及动作预算是否耗尽 |
| `robo.image(camera, resolution="high", step=-1)` | 读取指定相机在指定步的彩色图像，返回 RGB 数组（480×640×3） |
| `robo.sim_frames(step=-1, sim_step=None)` | 读取指定原语执行期间收到的全部帧，按接收顺序排列 |
| `robo.camera_meta(camera, step=-1)` | 相机内参与位姿，由机器人状态和固定的相机安装参数计算 |
| `robo.show(camera)` | 将指定相机的当前图像附加到本次工具返回中 |
| `robo.artifact(name, step=-1)` | 读取本回合记录的原始图像文件 |

**感知**（基于 SAM3 分割，仅使用彩色图像）

| 方法 | 说明 |
| --- | --- |
| `robo.segment(text_prompt, camera="cam_head", min_score=0.2)` | 按文本描述分割当前图像中的单个物体，返回掩码中心、面积和置信度 |
| `robo.locate(text_prompt, camera="cam_head", min_score=0.2)` | 按文本描述定位物体并进行三维测量，返回中心、顶面高度、占地长宽、朝向及建议抓取角 `grasp_yaw`；高度测量需要至少两个相机同时观察到该物体 |
| `robo.back_project(row, col, camera="cam_head")` | 返回指定像素对应的世界坐标点 |

**运动**（调用阻塞至动作完成，每个原生动作消耗一个评测步）

| 方法 | 说明 |
| --- | --- |
| `robo.move_to(xyz, arm="right", gripper=0, pitch=None, yaw=None, roll=None, path="auto")` | 将单臂抓取点移至目标位置和朝向。内部求解逆运动学，可行时沿直线运动（每步约 2.5 cm 或 8°），否则直接在关节空间运动；目标不可达或路径与桌面碰撞时不执行，并返回原因 |
| `robo.set_gripper(arm, gripper, opening=None)` | 控制单个夹爪开合，手臂保持不动；返回最终开度、是否夹持物体及夹持宽度 |
| `robo.home(arm="both")` | 手臂恢复至回合开始时的关节角 |

**常量与结果类型**

- 常量：`robo.LEFT`、`robo.RIGHT`、`robo.ARMS`、`robo.CLOSE`（1）、`robo.OPEN`（-1）、`robo.KEEP`（0）。
- 结果类型：`State`、`ArmState`、`Move`、`Gripper`、`Home`、`ObjectSight`、`Segment`、`SeenPoint`，均为不可变 dataclass。

### 内置固定参数

工具使用的参数均为机器人和默认场景的常量，对所有任务和回合相同，取自 RoboDojo 公开配置或在自建仿真场景中一次性测得：

- 头部相机的位姿和焦距、腕部相机的安装位置（`env_cfg/camera`）
- 双臂基座位姿、连杆几何和关节限位（`env_cfg/robot`、URDF）
- 桌面高度和范围（`env_cfg/scene/default.yml`）
- 夹爪开度与宽度的换算关系

### 代码执行沙箱

模型生成的代码在受限环境中执行（`src/robodojo/sandbox.py`）：

- 仅允许导入纯计算模块（如 `numpy`、`scipy`、`cv2`、`PIL`、`skimage`、`math`、`json`）及本回合工作目录中的 `.py` 文件。
- `open()` 的访问范围限定在本回合工作目录。
- 移除 `exec`、`eval`、`compile`；引用 `__globals__`、`__subclasses__` 等内省属性的代码在执行前即被拒绝。
- 每段代码均经过审计，结果记录为 `sandbox_flags`。
- 该沙箱为进程内实现，部分允许导入的模块（如 `io`、`numpy`、`cv2`）自带文件读写能力，不在 `open()` 的限制范围内。

## 8. 外部模型和服务清单

| 名称 | 用途 | 版本或来源 | 许可 |
| --- | --- | --- | --- |
| `gpt-6.2-astra` | 生成程序与决策的语言模型，通过 API 调用 | 见第 5 节 | 第三方闭源 |
| SAM3（`sam3` 包） | 按文本描述分割彩色图像，用于物体定位与测量 | `git+https://github.com/RLinf/sam3.git@c1f6b1e83967c912f675d8975d437ccdc41e17d8` | 待确认 |
| SAM3 权重 `sam3.pt` | SAM3 checkpoint（3.4 GB） | Hugging Face 或 ModelScope 上的 `facebook/sam3`，由 `download_assets.sh` 下载 | 待确认 |
| XPolicyLab | policy server 与 websocket 通信协议 | 随 RoboDojo 仓库提供，版本待确认 | 待确认 |
| RoboDojo | 仿真环境与评测客户端 | 官方提供，版本待确认 | 待确认 |
| PyRUA-Lean | 本项目代码的上游项目 | https://github.com/DAGroup-PKU/PyRUA-Lean | Apache-2.0 |
| RPent | 部分代码的上游项目（经由 PyRUA-Lean） | https://github.com/RLinf/RPent | Apache-2.0 |

除上表所列内容外，本系统不使用其他模型、服务、数据集或任务相关资源。

## 9. 评测记录

每个回合的记录保存在 `result_dir` 下的 `<task>_s<seed>-<time>/` 目录（默认为适配器目录下的 `./results/`），包含以下文件：

| 文件 | 内容 |
| --- | --- |
| `result.json` | 回合结果与状态、模型标识、推理参数、提示词字符数与 SHA-256、步数与耗时 |
| `prompt.txt` | 本回合完整提示词 |
| `card.json` | 本回合任务卡 |
| `messages.json` | 与模型往来的全部消息，图像以文件引用代替 |
| `openai_events.jsonl` | 每次请求的事件与 token 用量 |
| `request_log/requests.jsonl` | 每次请求包含的消息与图像 |
| `tool_turns.json` | 每次工具调用的代码、输出与沙箱审计结果 |
| `calls.jsonl`、`calls.live.jsonl` | `robo` 原语调用记录 |
| `robodojo.json` | 与 RoboDojo 的交互记录 |
| `steps/NNNN/` | 各原语执行期间收到的相机帧（`sim_NNN/`）、最终帧（`final/`）及索引文件 `frames.json`；`steps/0000/` 为初始观察 |

回合记录不包含 layout、物体位姿等隐藏信息，其中 layout 字段记为 -1。正式评测分数以 RoboDojo 的 `eval_result/` 为准。

## 10. 开源发布承诺

GCWM 团队承诺在成绩列入排行榜后三天内，通过 XPolicyLab 公开评测协议 "Open-Source Artifact for Verified Publication" 一节要求的全部材料，包括：

- 部署代码、harness、system prompt 与提示词模板、工具及配置文件
- 模型加载、推理、部署与评测说明
- 第三方模型的 API 披露信息（见第 5 节）
- 开发与评测日志，涵盖 Agent Track 规则第 5 节所列内容：各组件版本、通用组件变更、开发数据来源与评测流程、汇总得分与失败分析、正式评测记录与执行结果，以及最终提交版本与开发历史的对应关系

API key 等凭据不予公开。本系统不涉及训练或微调，因此无训练代码或 checkpoint 需要发布。
