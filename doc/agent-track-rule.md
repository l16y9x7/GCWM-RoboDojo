# Agent Track Rule

Source: https://robodojo-benchmark.com/leaderboard/agent-rule#official-task-specification

RoboDojo: A Unified Sim-and-Real Benchmark for Comprehensive Evaluation of Generalist Robot Manipulation Policies

Agent Track rule. The RoboDojo Agent Track is continuing to evolve, with participating teams exploring a wide range of Agent, RSI, and skill-library approaches. Some submissions may deviate from the latest evaluation requirements. An * indicates that the submission has been identified as non-conforming with one or more provisions of the latest Agent Track rules; it is a disclosure of compliance status rather than a comparative performance judgment. For such results, RoboDojo may publicly explain the specific provisions from which they deviate.

To ensure comparability, reproducibility, and transparency of evaluation results, all RoboDojo Agent Track submissions should comply with the following requirements. Agent Track average scores are calculated from Generalization, Precision, Long-Horizon, and Memory; the Open dimension is not included.

## 1. Official Task Specification

The official RoboDojo Detail Description defines each task's objective, completion criteria, operational constraints, terminal state, and randomized variants.

For official evaluation, the only externally supplied task-conditioned natural-language instruction is the official Detail Description for the current task, including the applicable randomized variant when provided. The Agent may also autonomously generate episode-local operation summaries, plans, and tool orchestration at test time from permitted data as specified in Section 2. Generic system and runtime instructions are permitted only when they are identical across tasks and contain no task-specific information.

Scoring tables, score values, and intermediate completion conditions explicitly included in the official Detail Description are permitted. These descriptions must not be supplemented with implementation-level scoring details that are not stated in the official Detail Description.

The scoring implementation remains evaluator-side. Checker code, hidden simulator state, internal evaluator interfaces, and other privileged implementation details must not be exposed to the Agent or used to construct task prompts.

Prohibited additions to task prompts include, but are not limited to:

- Reward-function or checker implementation details not explicitly stated in the official Detail Description, including exact metric definitions, numerical thresholds, geometric tolerances, formulas, or internal decision logic
- Task-specific RSI summaries, distilled knowledge, or experience prepared before testing or retained from other episodes
- Task-specific hints, examples, or workflow instructions prepared before testing; official demonstration data used under Section 2 is permitted
- Preloaded task answers, coordinates, or object identities used as a task-specific solution; this does not prohibit reading permitted demonstration data or deriving targets from current observations, but demonstration trajectories must not be replayed as the current episode's solution
- Any other information outside the official Detail Description and the permitted information and test-time summaries specified in Section 2

## 2. Permitted Information

All information-access restrictions apply to the entire submitted system, including the Agent, harness, tools, sub-agents, VLA/VLM components, memory stores, retrieval systems, and external services. Prohibited information must not influence action selection through any of these components, directly or indirectly.

All reusable components must operate without task-specific prompts, memories, or action programs prepared before testing, or task-specific scoring information beyond the official Detail Description. Episode-local operation summaries, plans, and tool orchestration autonomously generated at test time under this section are permitted. Knowledge learned in the weights of a general VLA through the training permitted below is not, by itself, prohibited precomputed task-specific memory.

Official demonstration data in this protocol means the data published in the RoboDojo-Benchmark/RoboDojo dataset under its data directory: https://huggingface.co/datasets/RoboDojo-Benchmark/RoboDojo/tree/main/data. Other public videos, evaluation replays, or execution logs do not qualify merely because they are public. This permission does not authorize access to hidden evaluator or simulator state.

A general VLA within an Agent submission may be trained or fine-tuned on official demonstration data before testing. Teams must disclose the training data sources and versions or file lists, the training or fine-tuning method, and the resulting checkpoint used for evaluation. Learning task knowledge through this training, or generating actions similar to demonstrations during normal model inference, is not by itself a violation. The checkpoint must be frozen before official evaluation and must not be switched by task. This permission does not authorize precomputed task-specific prompts, workflow scripts, retrieval answer stores, or explicit demonstration-trajectory replay.

In this protocol, test time begins only after the official evaluation system starts the current episode; starting a service or entering an evaluation period does not itself start that episode. Task-related summaries, plans, and tool orchestration may be generated only after that point. During testing, the Agent may use official demonstration data, including videos and action information, to autonomously generate operation summaries, plans, and tool orchestration for use only within the current evaluation episode. This permission is not limited to observations generated by the current episode. It does not permit explicitly reading or retrieving a demonstration action sequence and replaying it as the current episode's solution. Actions generated by normal inference of a VLA trained as permitted above must not be classified as replay solely because they resemble demonstration actions. Interpolation, time scaling, or coordinate transformations of a demonstration trajectory do not circumvent this prohibition; these transformations alone do not constitute replanning actions from current observations.

Except for the general VLA training expressly permitted above, neither humans nor automated systems may prepare task-specific operation summaries, workflow instructions, or derived skills from such data before testing, or preload or cache those results in prompts, memory, retrieval stores, code, or skill libraries. The training permission does not extend to producing such artifacts for the Agent to use. Each episode must autonomously generate its own summaries, plans, and tool orchestration at test time; these outputs must not be reused across episodes or used to update model weights or other frozen submission components.

Subject to these restrictions, the following information, capabilities, and interfaces are permitted:

- Official detailed description of the current task (obs["extra_info"]["detailed_instruction"])
- Standard runtime observations from the current episode, including RGB images, robot proprioceptive state, camera intrinsics and extrinsics, action execution results, and official control signals
- Official demonstration videos and action information, and episode-local operation summaries autonomously generated from permitted data at test time
- General model knowledge and general-purpose control capabilities
- A general skill library that is reusable across multiple tasks
- A general-purpose harness for orchestration, memory, tool use, and control
- General VLA and VLM components for perception, language grounding, planning, and action generation
- Officially provided runtime interfaces

## 3. No Iterative Optimization from Layout Rollout Feedback

All tracks, including the Agent Track, prohibit iterative optimization of submissions using feedback from rollouts on RoboDojo layouts. Before and during official evaluation, whether runs are local or official, their rewards, scores, failures, trajectories, or execution records must not be used for reinforcement learning, parameter tuning, model or version selection, or improvements to prompts, harnesses, tools, or skill libraries. Aggregating feedback across multiple tasks or layouts does not create an exception. Training a general VLA on the published official demonstration dataset under Section 2 is permitted; it does not authorize using feedback from local or official evaluation rollouts to train, tune, or select the model.

Subject to the rollout-feedback prohibition above, teams may develop and improve a fixed, task-agnostic harness, general skills, VLA/VLM components, and model configurations before evaluation, provided that they do not prepare prohibited task-specific prompts, workflow scripts, retrieval answers, or replay trajectories. General VLA training under Section 2 may learn task knowledge in model weights. The same submitted components must be used across tasks, without task-specific checkpoint switching or selection of precomputed task solutions.

Normal closed-loop control within a single episode is permitted: an Agent may observe the current episode, generate summaries, plans, and tool orchestration from the data permitted in Section 2, update its episode-local state and plan, and choose subsequent actions through the official interface. These runtime outputs do not modify the frozen system. They must not change model weights, the submitted prompt policy, harness or tool implementations, or the shared skill library, or influence other episodes.

Evaluation and reproduction of a fixed system, including officially prescribed repeated runs, are permitted, but their results must not be used to iteratively optimize the submission or select preferred outcomes. Adjusting local state and plans using permitted observations and action execution results within the current episode is normal closed-loop control; it does not authorize updates to frozen components, resets or additional episodes for trial-and-error optimization, or influence on other episodes.

Each evaluation episode must begin from the same frozen submitted system state, with fresh episode-local memory. Information generated during one episode must not influence action selection in any other episode, including concurrently running episodes.

The final submission must be frozen before official evaluation. The same submitted prompt policy, harness, model, code, configuration, and general skill library must be used for every evaluated task.

Prohibited forms of task-specific iteration or optimization include, but are not limited to:

- Re-running an individual task to improve its score or select a preferred result
- Modifying the frozen prompt policy, harness, VLA, VLM, model configuration, or shared skill library based on evaluation results; permitted episode-local context and plan updates are not such modifications
- Using task-specific failures, scores, trajectories, or execution records from one episode to construct behavior in another episode
- Routing another episode through task-specific feedback, summaries, or accumulated experience from a previous episode
- Applying a seed-specific or environment-specific exception to the prohibition above

## 4. General Skill Library, Harness, VLA, and VLM Use

The Agent Track encourages general-purpose agent systems rather than task-specific programs. Participating teams may develop and use reusable components across the full task set.

A general component may respond to the current Detail Description, runtime observations, and the demonstration data and test-time summaries permitted in Section 2. It must not use task identity to select prewritten action-output code, precomputed task-specific memory, or a prewritten workflow.

The governing principle is: task identity may determine which official Detail Description and permitted demonstration data are supplied, but it must not select a workflow, memory, code path, or action trajectory prepared before testing. Operation summaries, plans, and tool orchestration must be generated autonomously at test time under Section 2.

Renaming, combining, parameterizing, or changing the storage format of a task-specific solution prepared before testing does not make it a general-purpose capability. This applies to prohibited precomputed solutions represented as text, code, retrieval vectors, skill-library entries, or a model wrapper that merely forwards or copies such solutions. Knowledge learned in a general VLA through the training permitted in Section 2 is not by itself a prohibited precomputed solution, and similar model-generated actions alone are not evidence of a violation. A plan or tool orchestration autonomously generated at test time remains episode-local even if called a skill; it must not be added to the frozen shared skill library.

The following examples illustrate permitted uses of general components and non-compliant practices:

- A general skill library for visual perception, target localization, spatial reasoning, grasping, placing, pushing, inserting, pouring, recovery, and cross-task control
- A general-purpose harness for orchestration, memory management, tool use, state tracking, and action execution
- VLA components for mapping visual and language observations to reusable action representations
- VLM components for visual understanding, language grounding, scene interpretation, and task-agnostic planning
- Reusable interfaces that allow these components to work across the full task set
- Preparing a complete operating procedure for a single task before testing is not compliant
- Preparing a task-specific action sequence, waypoint set, or trajectory for explicit replay is not compliant; explicitly reading or retrieving and replaying demonstration actions as the current episode's solution is prohibited, but similarity of actions generated by normal VLA inference is not by itself a violation
- A task-specific action script or controller prepared before testing is not compliant. A plan or tool orchestration autonomously generated during the current episode may invoke the frozen general-purpose tools under Section 2
- Selecting prewritten task-specific action-output code using the task name, task_id, seed, layout, or object identity is not compliant
- Switching VLA policies or checkpoints by task, including selecting a checkpoint trained specifically for each task, is not compliant
- Wrapping a prewritten single-task trajectory program with an LLM, VLA, VLM, or harness is not compliant
- Packaging a single-task workflow prepared before testing as a skill, lesson, recipe, memory, or knowledge artifact is not compliant
- Feeding task-specific scores, failures, summaries, plans, or trajectories from one episode into another episode is not compliant

## 5. Open Development and Evaluation Logs

Participating teams must publicly release development and evaluation logs associated with the final submitted system.

Open logs are for transparency and reproducibility. Logs from development or other episodes must not provide task-specific prompt content, memory, summaries, or action guidance during evaluation. The current episode may use its own permitted observations, action execution records, and runtime outputs under Sections 2 and 3.

Failure to provide open-source logs associated with the final submission may affect the submission's eligibility for official verification and leaderboard endorsement.

Public logs must not disclose hidden simulator ground truth, hidden scene states, privileged metadata, internal evaluator states, hidden evaluation answers, or information obtained through privileged simulation interfaces. Logs may record permitted demonstration inputs, episode-local summaries, plans, tool calls, and actually executed actions and trajectories for review. Recording these artifacts does not authorize using them as precomputed solutions or reusing them in other episodes.

The public logs should cover the following:

- Versions of the harness, VLA, VLM, model, API, code, and configuration
- Changes to the general skill library and task-agnostic components
- Development data sources and general evaluation procedures
- Aggregate observations, scores, and failure analyses
- Official evaluation records and execution results
- The relationship between the final submitted version and the recorded development history

## 6. Observation and Execution Boundaries

The Agent may use only the official Detail Description supplied for the current task, official observations provided during the current episode, the official demonstration data and episode-local test-time summaries, plans, and tool orchestration permitted in Section 2, computations derived from permitted inputs, officially permitted standard interfaces, runtime action execution results available through the official interface, and compliant general skills or other task-agnostic components.

The fact that the evaluation infrastructure reads seeds, layouts, or internal state for scheduling, logging, or reproducibility does not authorize the Agent to use that information to select actions.

Actions must be executed through the official interface and must consume evaluation steps normally. No human may provide task-conditioned guidance, select actions, or modify decision-making components during an official evaluation run.

Prohibited information sources and actions include, but are not limited to:

- Additional task-specific prompt text or memory prepared before testing or retained from other episodes; episode-local test-time summaries, plans, and tool orchestration under Section 2 are permitted
- Internal simulator ground truth
- Undisclosed object positions, poses, or states
- Hidden metadata
- Internal evaluator or checker states
- Evaluation answers
- Information obtained through privileged simulation interfaces
- Resetting the environment independently
- Restoring or expanding the action budget
- Modifying the environment, evaluator, or checker
- Fabricating success
- Selectively reporting successful retries
- Bypassing official termination conditions
- Writing test answers or trajectories back into shared knowledge in a way that affects subsequent episodes

## 7. Submission and Disclosure Requirements

Unless otherwise agreed, official evaluation will use a default concurrency configuration of 3 × 8 × 1.

The three-day testing limit applies to all tracks, including the Agent Track, and is measured by the submission’s cumulative actual evaluation runtime. If actual runtime exceeds three days, the RoboDojo Committee reserves the right to decline further evaluation, as prolonged testing can severely block the evaluation queue.

Third-party closed-source foundation-model APIs are permitted under the protocol’s Open-Source Artifact for Verified Publication exception. Disclose the provider, model identifier, fixed version where available and inference parameters; if version pinning is unavailable, disclose the limitation and explain and document evaluation consistency. The exception does not cover the team’s own harness, prompts, tools, configurations, required logs, or its own training or fine-tuning artifacts.

Participating teams must provide the following materials for official evaluation and review:

- An API that remains continuously and reliably callable during official evaluation
- The corresponding model identifier, version information, or checkpoint
- Source code and configuration files
- The dependency environment and reproducible execution instructions
- The fixed harness, tools, memory, and context-assembly procedures, demonstrating that task-conditioned instructions come only from the official Detail Description and compliant episode-local summaries, plans, and tool orchestration generated at test time, including the demonstration data sources and when these runtime outputs are generated
- A description and inventory of the general skill library
- For a general VLA trained on official demonstrations: training data sources and versions or file lists, the training or fine-tuning method, and the exact checkpoint used for evaluation; publication follows the protocol requirements for open-source artifacts
- Open development and evaluation logs
- External models, services, and task-related resources
- Execution records and supporting materials corresponding to the official evaluation

## 8. Leaderboard Display and Official Endorsement

The RoboDojo leaderboard is intended to provide a platform for fair side-by-side comparison and reference. The Committee reserves the right to add an * to submissions, including previously published results, that are found upon review not to comply with the applicable rules, and to explain the specific deviations. This marker discloses compliance and comparability limitations; it does not mean that the approach lacks research or practical value.

The RoboDojo Committee reserves the right to review submitted code, configurations, runtime logs, APIs, and evaluation records, and to determine the display and official recognition of evaluation results based on compliance with this protocol. The Committee reserves the right to take the following actions:

- Mark the leaderboard entry with an *
- Publicly explain the specific provisions from which the submission deviates
- Display the evaluation result separately
- Decline to treat the result as a fully compliant official Agent Track result

## 9. Protocol Updates

This protocol is maintained and versioned by the RoboDojo Committee.

If a published leaderboard entry is found, upon review, to be inconsistent with the latest version, the RoboDojo Committee reserves the right to update its status under the current protocol and publicly explain the specific deviations.

The RoboDojo Committee reserves the right to update this protocol based on evaluation practice, community feedback, and developments in the field, and retains final authority to interpret this protocol. All updates will be published through official channels, and the latest version will take precedence.

The RoboDojo Committee reserves the right to continually improve and update the evaluation rules and will publish changes through official channels. Teams whose official evaluation has not yet started, including teams already in the queue, must adapt their submissions to the latest published rules before evaluation begins. Submitting materials or joining the queue does not lock in an earlier version of the rules. If rules change after a team’s official evaluation has started, the Committee will notify the team whether to continue, adjust its submission, or undergo re-evaluation. Teams must neither assume an automatic exemption nor modify the frozen system on their own. Any required adjustment and re-evaluation must follow the Committee’s instructions.

Read the RoboDojo Detail Description, the canonical task specification for every task.


## 附录：违规行为汇总

官方列出的违规行为主要有以下几类。

### 1. 往任务提示里加官方 Detail Description 以外的内容（第 1 节）

- 加入 checker 或奖励函数的实现细节，例如精确指标定义、数值阈值、几何容差、公式、内部判定逻辑。
- 加入测试前准备好的、或从其他 episode 留下来的任务专属 RSI 总结和经验知识。
- 加入测试前写好的任务专属提示、示例或流程说明。
- 预置任务答案、坐标、物体身份，或者把演示轨迹当作当前 episode 的解直接回放。

### 2. 越权使用信息（第 2、6 节）

- 读取模拟器内部真值、未公开的物体位姿或状态、隐藏元数据、评测器或 checker 的内部状态、评测答案，或通过特权仿真接口拿信息。
- 用评测基础设施读到的 seed、layout、内部状态来选择动作。
- 测试开始前由人或自动系统从演示数据里提炼任务专属的操作总结、流程或技能，再缓存进 prompt、记忆、检索库、代码或技能库。
- 显式读取演示动作序列后回放。做插值、时间缩放或坐标变换的回放同样算违规。正常 VLA 推理生成的动作即使与演示相似，也不算违规。

### 3. 用 rollout 反馈迭代优化（第 3 节）

- 用本地或官方评测的奖励、分数、失败记录、轨迹去做强化学习、调参、选模型或版本，或者改进 prompt、harness、工具、技能库。跨多个任务汇总这些反馈也不行。
- 重跑单个任务刷分，或挑选更好的那次结果。
- 根据评测结果修改已冻结的组件。
- 把一个 episode 的失败、分数、轨迹、总结带进另一个 episode，包括并发运行的 episode。
- 针对特定 seed 或环境开例外。

### 4. 把任务专属程序伪装成通用组件（第 4 节）

- 测试前为单个任务写好完整操作流程、动作序列、路点、轨迹，或者专用的控制脚本。
- 按 task name、task_id、seed、layout 或物体身份选择预写的动作代码。
- 按任务切换 VLA 策略或 checkpoint。
- 用 LLM、VLA、VLM 或 harness 包一层预写的单任务轨迹程序。
- 把单任务流程包装成 skill、lesson、recipe、memory 或知识文件。官方明确说，改名、组合、参数化或换存储格式都不能让它变成通用能力。

### 5. 执行和汇报层面的作弊（第 6 节）

- 自行重置环境，恢复或扩大动作预算。
- 修改环境、评测器或 checker。
- 伪造成功，只汇报成功的那次重试，绕过官方终止条件。
- 把测试答案或轨迹写回共享知识，影响后续 episode。
- 正式评测过程中由人提供任务相关指导、替它选动作或修改决策组件。

### 6. 其他（第 5、7 节）

- 不公开与最终提交对应的开发和评测日志，可能失去官方认证资格。
- 公开日志里泄露隐藏真值或特权信息。
- 实际评测时长超过 3 天，委员会可以拒绝继续评测。
