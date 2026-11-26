from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from robodojo.play import build_prompt  # noqa: E402
from robodojo.prompt import TaskCard  # noqa: E402


card = TaskCard(
    suite="<运行时任务变体>",
    task="<运行时任务编号>",
    seed="<运行时种子>",
    task_language="<运行时任务指令>",
    object_names=[],
    images={
        "cam_head": "<初始头部相机图像>",
        "cam_left_wrist": "<初始左腕相机图像>",
        "cam_right_wrist": "<初始右腕相机图像>",
    },
    max_env_steps="<运行时环境步数>",
    robot="robodojo_xpl_rgb",
    facts={"initial arm state": "<运行时两臂状态>"},
)

prompt = build_prompt(
    card,
    budget_s=5400,
    images="on-primitive",
    feedback="pure",
    budget_mode="calls",
)

intro = """# 实际提示词快照

本文展示 XPolicyLab 当前部署配置下，每个回合拼装并发送给模型的完整提示词文本。正文由代码生成，覆盖控制约定、交互协议、机器人 API 参考、RoboDojo RGB 知识和任务卡。OpenAI 请求中的工具 JSON Schema 通过独立的 `tools` 字段传递，不属于这段提示词文本。

任务变体、任务指令、初始图像、两臂状态和环境步数会随运行变化；本文用 `<运行时...>` 标记这些字段。任务编号和种子不进入提示词（RoboDojo Agent Track 规则第 1、6 节）。其他部分按当前代码及配置展开。每次真实运行的精确提示词保存在该运行目录的 `prompt.txt` 中，因为任务卡和环境状态不能由静态文档预先确定。

当前快照使用 `integrations/xpolicylab/robodojo/deploy.yml` 中的设置：`robodojo_xpl_rgb`、`cells`、`on-primitive`、`pure`、5400 秒和 100 次工具调用预算。提示词中的任务卡使用占位数据；模型实际收到的相机图片作为同一条初始用户消息中的图像内容发送。

阅读交互协议的中文译文：[`actual-prompt.zh.md`](actual-prompt.zh.md)。

以下代码块内是完整的提示词文本。修改提示词源码后，可运行 `.venv/bin/python tools/render_actual_prompt.py` 重新生成此快照：

```text
"""

(ROOT / "doc" / "actual-prompt.md").write_text(
    intro + prompt + "\n```\n",
    encoding="utf-8",
)
