# robodojo

RoboDojo Agent Track 的打榜 agent。包名、命令和 XPolicyLab 适配器都叫 `robodojo`。代码派生自 PyRUA-Lean，来源和许可见 [`NOTICE`](NOTICE)。

语言模型在回合进行中写 Python，调用 `robo`。这个包把动作解成双臂关节目标，通过 XPolicyLab 的 websocket 交给 RoboDojo 自己的 evaluation client。评测用的机器人是 `robodojo_xpl_rgb`：三路彩色图和关节状态，没有深度图，没有 VLA。agent 收到的任务相关文本只有官方 Detail Description（`extra_info.detailed_instruction`），原样传入。

## 布局

- `src/robodojo/`：agent 循环（OpenAI 兼容接口）、`robo` API、IK、SAM3 测距、评测 host。
- `integrations/xpolicylab/robodojo/`：交给 XPolicyLab 的适配器。`deploy.yml` 的 `policy_name` 与目录名一致。

## 安装

策略环境里需要已经装好的 CUDA 版 `torch` 和对应的 `torchvision`。适配器要放在 XPolicyLab 的 `policy/` 下再执行 `install.sh`（脚本用 `../..` 找 XPolicyLab）：

```bash
ln -s <本仓库>/integrations/xpolicylab/robodojo \
    <RoboDojo>/XPolicyLab/policy/robodojo
bash <RoboDojo>/XPolicyLab/policy/robodojo/install.sh
bash <RoboDojo>/XPolicyLab/policy/robodojo/download_assets.sh
```

模型端：

```bash
export OPENAI_BASE_URL=https://YOUR_API_HOST/v1
export OPENAI_API_KEY=...
export ROBODOJO_MODEL=<模型名>
```

环境变量前缀是 `ROBODOJO_`（`ROBODOJO_MODEL`、`ROBODOJO_BASE_URL`、`ROBODOJO_API_KEY_ENV`、`ROBODOJO_RESULT_DIR`）。

## 跑一局

从 RoboDojo 根目录，`--policy-dir` 指向适配器。`action_type` 必须是 `joint`。

```bash
bash scripts/robodojo.sh eval --policy-dir XPolicyLab/policy/robodojo \
    --task stack_blocks --ckpt no-checkpoint --policy-env <policy_env> \
    --eval-env <eval_env> --env-cfg arx_x5 --action-type joint --seed 0
```

不接仿真时看 API 和提示词：

```bash
cd <本仓库>
python -m robodojo api
python -m robodojo prompt
```

## 协议名

观察和动作的协议键是 `robodojo`（`additional_info["robodojo"]`，以及 `get_action` 的 `wait`）。

Agent 的动作闭环和图片上下文保留策略见 [`doc/agent-interaction.md`](doc/agent-interaction.md)。
