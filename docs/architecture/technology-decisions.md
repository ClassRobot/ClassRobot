# 技术决策与工程规范

> 核验日期：2026-04-18

## 文档目标

本文件定义 ClassRobot 下一阶段 AI 平台建设中的关键技术决策。它关注“为什么这么做”，也明确“哪些流行做法不建议采用”。

## 决策总表

| 编号 | 主题 | 推荐决策 | 理由 |
| --- | --- | --- | --- |
| D1 | 总体形态 | 先做模块化单体，再按瓶颈拆服务 | 兼顾迭代速度和后续扩展 |
| D2 | 工作流 | 采用具备 durable execution 的工作流运行时 | Agent 业务不是一次模型调用 |
| D3 | 模型调用 | 以 Provider Adapter 封装模型，优先兼容 OpenAI 最新工具能力 | 避免被单一 SDK 或模型形态锁死 |
| D4 | Tool 体系 | 所有执行能力统一进 Tool Registry | 便于权限、观测、版本和复用 |
| D5 | Skill 体系 | Skill 保留为能力说明与最佳实践层，不直接替代 Tool | Skill 更适合“声明能力”，Tool 更适合“执行能力” |
| D6 | MCP 策略 | 同时做 MCP Client 与 MCP Server | 既能接入外部能力，也能对外开放本系统能力 |
| D7 | 知识体系 | RAG 独立成 Knowledge Plane，采用混合检索、重排和引用 | 知识问答必须可解释、可隔离、可评测 |
| D8 | 记忆体系 | 会话记忆、用户画像、业务状态、知识索引分别存储 | 避免把不同性质的数据塞到一个上下文里 |
| D9 | 安全策略 | 写操作必须经过 Policy Engine，可附加人工审批 | Prompt 不能替代权限系统 |
| D10 | 观测与评测 | 默认接入 tracing、cost、feedback、eval | 没有可观测性就无法稳定迭代 Agent |
| D11 | Agent 形态 | 默认单编排器 + 专家工具，多 Agent 按需引入 | 当前主流可靠实践并不鼓励无约束多 Agent |
| D12 | Prompt 管理 | Prompt 模板必须版本化、可回滚、可测试 | Prompt 也是运行时资产 |

## 详细决策

### D1. 先模块化单体，再拆服务

推荐做法：

- 先在一个仓库中完成接口层、应用编排层、领域层、知识层的清晰分层
- 模块之间只通过明确 DTO、Tool Contract、Service Interface 交互
- 当吞吐、权限域或部署边界显著变化时再拆服务

不推荐：

- 在领域边界还不清晰时直接切多个微服务

### D2. 工作流运行时必须支持 Durable Execution

推荐做法：

- 每个复杂流程都能持久化状态
- 支持节点级重试、超时、补偿和人工接管
- 支持审批流、定时继续执行和异步回调

为什么：

- 多阶段审批、异步交付、外部系统互联、知识构建都不是“单次问答”
- 官方工作流框架已经把 durable execution、human-in-the-loop、memory 作为主线能力

### D3. 模型层通过 Adapter 抽象

推荐做法：

- 在项目内提供统一的 `LLMProvider` 抽象
- 模型能力分成：文本生成、结构化输出、工具调用、多模态理解、检索辅助
- 默认优先接入支持最新工具能力的模型接口

不推荐：

- 在业务模块里直接写死某家 SDK 的调用格式

### D4. Tool Registry 是系统中枢

每个 Tool 至少应包含：

- `name`
- `description`
- `input_schema`
- `output_schema`
- `auth_scope`
- `risk_level`
- `timeout`
- `retry_policy`
- `owner`
- `observability_tags`

Tool 分类建议：

- `read`: 只读查询
- `write`: 变更业务数据
- `side_effect`: 发送消息、上传文件、触发外部动作
- `system`: 管理内部运行时

### D5. Skill 是“能力说明层”，不是唯一执行层

推荐保留当前 `skills/` 目录，并为每个 Skill 增加以下内容：

- 版本号
- 适用场景
- 输入输出说明
- 依赖的 Tool 或 Runtime
- 成功/失败案例
- 最小测试集

适合继续 skill 化的能力：

- 多模态解析
- 文档理解
- 结构化抽取
- 渲染与可视化输出
- 外部系统交互流程模板

### D6. MCP 采用双向策略

#### 作为 Client

用于接入：

- 浏览器与网页工具
- 搜索与公共信息源
- 文档库或知识库
- 校园系统适配器
- 代码与自动化环境

#### 作为 Server

用于对外暴露：

- 只读领域查询接口
- 知识资源访问接口
- 服务目录与能力说明
- 受控事务提交入口
- 审批与确认接口

MCP Server 的写能力开放顺序建议：

1. 先开放只读 Tool
2. 再开放低风险写 Tool
3. 最后开放高风险写 Tool，并强制审批和审计

### D7. Knowledge Plane 独立建设

推荐结构：

- `ingestion`: 文档接入、解析、清洗、抽取元数据
- `index`: chunk、embedding、倒排索引、向量索引
- `retrieval`: hybrid search、metadata filter、rerank
- `citation`: 引用回溯、片段定位、权限过滤

知识空间建议至少分为：

- `institutional knowledge`
- `operational knowledge`
- `tenant-isolated domain knowledge`
- `user-private knowledge`
- `system runtime knowledge`

### D8. 记忆分层

不要把所有“记忆”都当作聊天上下文。

推荐拆成：

- `session memory`: 当前对话短期状态，适合放 Redis
- `profile memory`: 用户画像和偏好，适合放 Postgres
- `task memory`: 工作流中间状态和审批上下文
- `knowledge memory`: 文档索引与可检索知识

### D9. 权限和审批不是 Prompt 问题

必须由代码控制的内容：

- 谁可以读哪类知识
- 谁可以发起或确认哪类业务事务
- 哪些 Tool 需要审批
- 哪些外部 Agent 可以调用哪些 MCP Tool

建议将审批级别分为：

- `auto`: 低风险自动执行
- `confirm`: 用户确认后执行
- `human_review`: 需要管理员或教师审批

### D10. 观测与评测默认开启

每次流程至少记录：

- 请求入口
- 使用的模型和版本
- Prompt 版本
- Tool 调用链
- 检索结果与引用
- Token 和成本
- 错误、重试和超时

至少维护三类评测集：

- 服务编排评测
- 检索问答评测
- 高风险事务安全评测

### D11. 默认不是多 Agent

推荐策略：

- 在线主链路默认使用单编排器 Agent
- 专家能力优先以 Tool 或 Skill 形式存在
- 只有在“可并行、可独立、可审计”的子任务中再引入多 Agent

不推荐：

- 把每个功能都包装成一个会互相调用的 Agent
- 用多 Agent 掩盖领域建模不足

### D12. Prompt 资产要版本化

推荐做法：

- 所有系统 Prompt 放入 Prompt Registry
- 每次变更带版本号、用途和评测结果
- Prompt 与 Tool 描述分开维护
- Prompt 模板避免写入真实权限判断

## 推荐技术栈

以下是当前阶段兼顾前沿性和稳定性的推荐组合：

| 模块 | 推荐基线 |
| --- | --- |
| Bot / API 接入 | `NoneBot` + `FastAPI` |
| 工作流运行时 | `LangGraph` 或具备同等级 Durable/HITL 能力的自研运行时 |
| 模型接入 | Provider Adapter，优先兼容 `OpenAI Responses API` |
| Tool 契约 | `Pydantic` + JSON Schema |
| MCP | Remote MCP Server + MCP Client Hub |
| 数据库 | `Postgres` |
| 缓存/锁 | `Redis` |
| 文件对象 | `COS` 或兼容 `S3` 的对象存储 |
| 向量检索 | `pgvector` 起步，规模增长后再独立向量库 |
| 知识引擎 | `RAGFlow` 作为首个 Provider，挂在统一 Retrieval 抽象后 |
| 观测 | `OpenTelemetry` 风格 tracing + 成本与反馈统计 |

## 不推荐清单

- 让 LLM 直接输出命令文本并回放执行，缺少结构化校验
- 会话状态只保存在 Python 进程内存中
- 把 RAG 检索结果直接拼成超长 Prompt，不做引用治理
- 依靠 Prompt 去限制高风险操作
- 在没有 Tool Registry 的情况下直接把各种函数暴露给 Agent
- 尚未建立评测和追踪时大规模增加模型和 Agent 数量

## 与当前仓库直接相关的结论

- 现有 `skills/` 应该保留并增强，而不是回退
- 现有 `utils/llm/agents/` 更适合演进为工作流节点和工具适配层
- 现有 `src/plugins/autogpt/` 不应继续承担未来总编排入口的全部职责
- 现有 `helper` 能力适合升级为 Tool 说明和命令知识层
