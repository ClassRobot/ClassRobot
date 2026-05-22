# AutoGPT Runtime 开发指南

`src.core.agent.runtime` 是 AutoGPT 的真实运行时层。`src/plugins/application/active/autogpt/__init__.py` 现在只负责 NoneBot 消息入口、会话接线和结果发送；重逻辑统一放在这里。

## 模块边界

- `pipeline.py`
  - 组织一次消息处理链路，并读取热更新后的运行时图。
- `coordination/`
  - 工作流节点和状态对象。
- `harness/`
  - 策略、上下文、可观测性装配层。
- `knowledge.py`
  - 受控知识源检索、本地聊天、文件空间、本地 RAG 和 Skill 目录。
- `workflow.py`
  - 显式工作流构建、审批语义和执行器。
- `loop.py`
  - 观察驱动循环、循环预算锁、Observation 事实化和能力目录契约。
- `orchestration_config.py`
  - 运行时图编排配置、热更新、默认图和图校验。
- `node_registry.py`
  - 编排画布可见节点目录。
- `schema.py`
  - AutoGPT Runtime 的结构化数据协议。

## 双层工作流

AutoGPT Runtime 里现在固定区分两层工作流，后续开发不要再混用名称。

| 层级 | 对象 | 控制权 | 作用 |
| --- | --- | --- | --- |
| 运行时编排图 | `RuntimeGraphConfig` | 开发者和管理端 | 决定一轮消息进入系统后依次经过哪些 Runtime 节点，以及分支条件和模型角色 |
| AI 任务执行流 | `TaskWorkflow` | AI 在系统约束内生成 | 决定本轮用户目标要执行哪些 command、skill、confirm、respond 或 schedule 步骤 |

运行时编排图是系统控制面，AI 不能修改。AI 只能在运行时图约束下生成 `TaskWorkflow`，再由执行器校验、执行、记录 observation，最后交给回复 Agent 汇总给用户。

```mermaid
flowchart TD
    User["用户消息"] --> RuntimeGraph["RuntimeGraphConfig\n开发者热更新图"]
    RuntimeGraph --> Route["场景路由"]
    Route --> Context["AI 知识路由与检索"]
    Context --> Plan["任务计划"]
    Plan --> TaskFlow["TaskWorkflow\nAI 临时任务流"]
    TaskFlow --> Loop["CognitiveAgentLoop\n选择能力 / 执行 / 观察 / 验证"]
    Loop --> Observation["CommandObservation\n写回会话上下文"]
    Observation --> Reply["ExecutionReplyAgent\n最终自然语言总结"]
```

## 观察驱动循环

`CognitiveAgentLoop` 是任务执行层的新标准，不再为某个业务场景写死“先查再建再查”的过程代码，而是用同一套通用闭环处理任务、班级、通知、课表等能力：

```text
理解目标 -> 选择能力 -> 执行一步 -> 读取观察 -> 自我修正规划 -> 验证结果 -> 总结/追问
```

循环中的核心对象：

- `CapabilityCatalog`
  - 当前用户可见且可由 Agent 调用的能力目录。第一版承接 service-style command，后续 skill、RAG、schedule 按同一契约加入。
- `ObservationFact`
  - 把 `CommandObservation` 转成结构化事实，例如 `exists=false`、`changed=true`、`verified=false`。
- `AgentLoopDecision`
  - 单轮下一步动作，只保存可审计摘要，不保存冗长推理。
- `LoopBudget`
  - 代码强制的循环锁，负责最大步数、最大验证次数、重复动作次数和运行时间上限。

已有 `TaskWorkflow.steps` 会作为候选步骤进入循环；每步执行后都会解释 observation。若 observation 显示“需要验证”或“目标不存在且可继续处理”，循环可通过 `resources/prompts/agent_loop_decision.jinja` 让监督模型基于能力目录决定下一步。模型只能选择能力目录中的能力，不能绕过权限、可见性、风险确认或循环预算。

## 循环锁配置

循环锁是启动级硬配置，写在 `.env`，不是热更新配置，也不是 prompt 建议：

```dotenv
AGENT_LOOP_MAX_STEPS=8
AGENT_LOOP_MAX_VERIFY_ATTEMPTS=3
AGENT_LOOP_MAX_REPEAT_ACTIONS=2
AGENT_LOOP_MAX_RUNTIME_SECONDS=120
```

含义：

- `AGENT_LOOP_MAX_STEPS`
  - 单轮最多执行多少次 act-observe 动作。
- `AGENT_LOOP_MAX_VERIFY_ATTEMPTS`
  - 同一验证目标最多验证多少次。
- `AGENT_LOOP_MAX_REPEAT_ACTIONS`
  - 同一命令和同一参数最多重复多少次。
- `AGENT_LOOP_MAX_RUNTIME_SECONDS`
  - 单轮循环最长运行秒数。

达到上限后，循环必须停止，并基于已有 observation 说明已经尝试了哪些步骤、为什么停止、用户可以怎样继续。不能静默失败，也不能编造成已经成功。

## AI 知识路由

本地历史和文件检索不再由关键词触发。入口路由器会在 `IntentRoute.knowledge_sources` 中声明本轮需要哪些受控知识源，运行时只负责校验权限、执行检索和写回 observation。

可选知识源：

- `user_chat_history`
  - 当前用户与机器人的历史聊天。
- `group_chat_history`
  - 当前绑定系统群的群聊采集消息。
- `user_file_space`
  - 当前用户自己的文件空间。
- `group_file_space`
  - 当前绑定系统群的文件空间。
- `external_rag`
  - 外部知识库，例如校规、制度、学校资料或公共知识库。

关键边界：

- AI 负责判断“用户目标需要查哪里”，不要再把“刚才、文件、聊天记录”等关键词作为主决策规则。
- 代码负责判断“当前用户能不能查”，不能读取其它用户私聊，也不能把平台 `channel_id` 当成系统群 ID 直接读取。
- 每个来源都会生成结构化 observation，包含 `source`、`query`、`status`、`confidence`、`items_count` 和摘要。
- `status=miss`、`status=skipped` 或检索失败时，后续 Planner 和回复不能编造成已查到。

```mermaid
flowchart TD
    User["用户消息"] --> Route["IntentRouteNode"]
    Route --> Sources["knowledge_sources\nAI 选择受控知识源"]
    Sources --> Guard["代码权限校验\n用户 / 群 / 文件空间"]
    Guard --> Local["LocalKnowledgeRetriever"]
    Guard --> External["RagAgent / external_rag"]
    Local --> Obs["KnowledgeSourceObservation"]
    External --> Obs
    Obs --> Plan["Planner / TaskWorkflow"]
```

## Agent 决策层不做关键词预路由

默认运行时图已经移除 `local_context`、`local_chat_statistics` 这类抢跑节点。身份、班级、课表、聊天统计等需求都应通过 `IntentRoute -> Planner -> service command` 的统一链路处理：

- Runtime 暴露当前用户可见的完整 service command catalog 和 Skill catalog。
- Route / Planner 依据用户目标和能力描述做语义选择。
- 代码只做权限、参数、风险、执行入口和 observation 回填校验。
- 聊天统计作为“统计聊天记录” service-style command 暴露给 Agent，而不是在路由前用字符串规则拦截。
- RAG、文件搜索、后台筛选中的关键词检索属于工具内部实现，不参与 Agent 路径决策。

## 调用链

```mermaid
flowchart TD
    A["src/plugins/application/active/autogpt/__init__.py<br/>NoneBot 入口"] --> B["ChatSession"]
    B --> C["MessageProcessingPipeline"]
    C --> X["RuntimeGraphExecutor<br/>条件边执行器"]
    X --> D["WorkflowNode"]
    D --> E["BaseAgent 子类"]
    E --> F["Command / Skill / RAG / Local Memory"]
    F --> G["Observation 写回 Messages"]
    G --> H["WorkflowBuilder / CognitiveAgentLoop"]
    H --> I["ExecutionReplyAgent"]
```

## 默认编排图

系统默认编排链路就是外部最初的 AutoGPT 主流程，现在由 `default_graph_config()` 显式生成，而不是藏在一串硬编码 `if/else` 里。

节点目录由 `node_registry.py` 定义，运行时编排由 `orchestration_config.py` 加载和热更新。

每个节点要区分三种概念：

- `node_type`
  - 画布上的运行时节点类型。
- `agent_name`
  - 节点内部最终要实例化的 Agent 类型。
- `agent_config`
  - 传给 Agent 的运行配置。

默认图是一张受限 DAG，会按内置条件选择下一跳：

- `has_auto_tasks`
  - 上游已经产生直接回复、确定性命令或待确认任务时，直接进入持久化节点。
- `needs_local_knowledge`
  - `IntentRoute.knowledge_sources` 中包含本地知识源时，进入本地 RAG；不再用关键词判断。
- `direct_vision_reply`
  - 简单图片问答不需要命令或检索时，直接走视觉回复。
- `needs_external_rag`
  - `knowledge_sources` 包含 `external_rag`、路由 `requires_rag=true` 或 Planner 明确需要外部知识库时，进入外部 RAG。
- `always`
  - 作为同源节点的兜底边，必须放在更具体条件之后。

热更新配置写入 `resources/agent/agent_orchestration_runtime.json`，实际目录由 `src.platform.config.agent_resources_dir` 决定。配置非法时运行时会回退默认图，并在快照中记录 warning。

## 模型角色

`RuntimeGraphConfig.model_profiles` 支持开发者给不同职责绑定模型：

- `supervisor_model`
  - 路由、任务流设计、风险监督和最终回复。
- `worker_model`
  - 抽取、检索摘要、低成本中间整理。
- `vision_model`
  - 图片和文件理解。
- `summary_model`
  - 长上下文压缩。

节点可以在 `node.config` 中写 `model` 或 `llm_name` 直接指定模型，也可以写 `model_profile` 指向上面的角色。没有显式配置时，运行时按节点定义和 LLM 任务类型自动选择角色，再回退到全局默认 LLM 配置。

## 执行后最终回复

AI 代替用户执行命令后，不能只把命令原始输出丢给用户。标准链路是：

1. `CognitiveAgentLoop` 执行 `TaskWorkflow` 步骤，并在每步后读取 observation 和循环预算。
2. 每个命令返回 `CommandObservation`。
3. `ChatSession.record_observations()` 把紧凑结果写回会话上下文。
4. `ExecutionReplyAgent` 基于 workflow、observation 和短原始输出生成最终自然语言回复。

这让行为更接近 Claude Code / Codex 的“执行工具后总结结果”体验，同时保留命令输出作为可审计 observation。

## 如何增加一个新节点

1. 在 `coordination/nodes.py` 或新的节点模块里新增 `WorkflowNode` 子类。
2. 在 `node_registry.py` 注册对应 `RuntimeNodeDefinition`。
3. 如果节点内部会调用 Agent，优先通过 `BaseAgent.create(agent_name, config=...)` 实例化。
4. 如果节点需要写入管理端草稿配置，把字段同步到管理端 schema。
5. 补 `tests/autogpt/test_orchestration_config.py` 和相关行为测试。

## 如何让节点调用 Agent

推荐模式：

```python
agent = BaseAgent.create(
    "extract_agent",
    config={"some_flag": True},
    messages=pipeline.messages,
)
result = await agent.execute(pipeline.messages)
```

不要把 `RuntimeContext`、`WorkflowNode` 或 `Retriever` 直接命名成 Agent。

## 热更新规则

- Agent 运行时编排图保存到 `resources/agent/agent_orchestration_runtime.json`，路径由 `src.platform.config.agent_resources_dir` 统一提供。
- 运行时通过 `mtime` 检测自动重载。
- 图无效时退回默认编排图，并记录 warning。
- 管理端看到的是 `WorkflowGraph` 和 `RuntimeNodeDefinition`，不是随意拼出来的匿名步骤。

## Prompt-first 规则

在这里做 Agent Runtime 开发时，先问自己：

- 是不是 Prompt 不够清晰？
- 是不是 observation 回填不够好？
- 是不是 command / skill 描述太弱？
- 是不是上下文召回策略需要改？

如果答案是“是”，先改 Prompt、目录描述、上下文契约；不要急着把问题硬编码成分支。

## 测试入口

- `tests/autogpt/test_harness.py`
- `tests/autogpt/test_knowledge.py`
- `tests/autogpt/test_orchestration_config.py`
- `tests/autogpt/test_agent_loop.py`
- `tests/autogpt/test_workflow.py`
- `tests/autogpt/test_session.py`
