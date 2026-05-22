# 迁移路线图

> 核验日期：2026-04-18

## 目标

本路线图用于指导 ClassRobot 从“当前可运行机器人项目”平滑演进到“AI 原生校园能力平台”。目标不是一次性重构，而是在每一阶段都保持可运行、可验证、可继续交付。

## 迁移原则

- 先抽边界，再换骨架
- 先统一契约，再扩功能
- 先可观测，再放大智能编排
- 先只读能力标准化，再开放写能力
- 先模块化单体，再按瓶颈拆服务

## 阶段总览

| 阶段 | 目标 | 结果物 |
| --- | --- | --- |
| Phase 0 | 文档与边界统一 | 架构文档、目录规划、命名规范 |
| Phase 1 | 领域能力下沉 | Domain Services、DTO、Repository 边界 |
| Phase 2 | Tool/Skill 平台统一 | Tool Registry、权限元数据、Skill 增强 |
| Phase 3 | 工作流运行时落地 | Durable Workflow、Checkpoint、审批流 |
| Phase 4 | 知识平面独立 | Ingestion、Retrieval、Citation、知识空间 |
| Phase 5 | MCP 双向接入 | MCP Client Hub、Remote MCP Server |
| Phase 6 | 观测、评测与后台治理 | Tracing、Eval、Feedback、Admin API |

## Phase 0: 文档和边界统一

### 目标

- 确认目标架构和技术决策
- 冻结核心目录命名方式
- 避免后续在重构途中反复改概念

### 建议输出

- 本专题文档
- 新的目录规划草案
- Tool Contract 草案
- Prompt Registry 草案

### 完成标志

- 所有人对 Skill、Tool、MCP、RAG、Domain 的边界达成一致

## Phase 1: 领域能力下沉

### 目标

把稳定业务规则从插件和 AI 编排逻辑中抽出来。

### 优先拆分顺序

1. `identity and access`
2. `organization and membership`
3. `transactional orchestration`
4. `approval and governance`
5. `campus integration`
6. `communication`

### 推荐动作

- 为每个领域建立 Service、Command/Query DTO、Repository 接口
- 把权限语义从 Prompt 和插件层迁回领域层
- 插件只保留消息解析和响应格式组装

### 当前代码的迁移方向

| 当前位置 | 迁移目标 |
| --- | --- |
| `src/plugins/application/active/user/*` `src/plugins/application/active/student/*` `src/plugins/application/active/teacher/*` | `src/domain/identity_access/` |
| `src/plugins/application/active/classes/*` `src/plugins/application/active/group/*` | `src/domain/organization_membership/` |
| `src/plugins/application/active/tasks/*` `src/plugins/application/active/leave/*` | `src/domain/transactional_orchestration/` |
| `src/plugins/application/active/curriculum/*` | `src/domain/campus_integration/` |
| `src/plugins/application/active/notice/*` | `src/domain/communication/` |

### 完成标志

- 业务写操作不再依赖 LLM 执行文本回放
- 插件可以在不接入 AI 的情况下直接调用 Domain Service

## Phase 2: Tool/Skill 平台统一

### 目标

让所有 AI 可调用能力进入统一工具层。

### 推荐动作

- 新建 `application/tools/registry.py`
- 给每个 Tool 补齐 schema、权限级别、风险级别、重试策略
- 让 Skill 显式声明其绑定的 Tool 或 Runtime
- 把帮助系统从“命令说明”升级为“Tool 说明 + 使用约束”

### 先纳入 Tool Registry 的能力

- 只读领域查询
- 受控事务提交
- 身份与权限解析
- OCR
- 文档转图
- Markdown 渲染
- 结构化抽取

### 完成标志

- Agent 不再直接依赖任意 Python 函数
- Tool 可以独立测试和观测

## Phase 3: 工作流运行时落地

### 目标

把当前 `Summary -> Extract -> Rag -> AutoTask` 的链路升级为真正可恢复的工作流。

### 推荐动作

- 建立 `workflow runtime`
- 为每次请求生成 `run_id`
- 增加 checkpoint、retry、timeout、approval、resume
- 把“长流程、审批流程、定时流程”统一纳入同一工作流模型

### 第一批工作流

1. 自然语言服务编排
2. 多阶段审批与确认
3. 异步交付与回执
4. 文档解析和知识入库

### 完成标志

- 中断后可恢复
- 高风险操作可挂起审批
- 每次运行有完整 trace

## Phase 4: 知识平面独立

### 目标

让 RAG 从聊天逻辑附件，升级为平台级知识能力。

### 推荐动作

- 建立统一 `knowledge/` 模块
- 把 RAGFlow 放在 Retrieval Provider 抽象后
- 引入知识空间、文档权限、引用回溯
- 为检索结果建立评测集

### 知识源优先级

1. 制度与治理知识
2. 组织与运营知识
3. 业务沉淀文档与共享资料
4. 用户私有知识资产

### 完成标志

- 检索链路不依赖聊天历史拼接
- 回答默认带来源引用
- 不同知识空间有明确权限隔离

## Phase 5: MCP 双向接入

### 目标

把系统正式接入 MCP 生态。

### 作为 MCP Client 的优先方向

- 浏览器和网页交互
- 搜索能力
- 外部文档与知识系统
- 校园业务系统连接器

### 作为 MCP Server 的优先方向

- 只读领域查询接口
- 知识资源访问接口
- 服务目录与能力说明
- 受控事务提交接口

### 完成标志

- 外部 Agent 可通过标准协议安全读取本系统能力
- 本系统可稳定调用外部 MCP 服务

## Phase 6: 观测、评测与后台治理

### 目标

让系统真正具备生产级演进能力。

### 推荐动作

- 建立 tracing 和运行日志
- 统计模型成本与工具成本
- 维护 golden dataset 和回归评测
- 提供后台查询工作流、审批、Tool 使用情况

### 完成标志

- 每次版本变更前后都有回归结果
- 可以追踪错误发生在哪个 Prompt、Tool、Retriever 或模型版本

## 推荐的近期落地顺序

如果只看最近 2 到 4 周，建议按下面顺序推进：

1. 完成文档和目标目录设计
2. 先抽 `identity_access` 和 `transactional_orchestration` 两个 Domain Service
3. 建第一个 Tool Registry，并把 OCR、文档转图、只读领域查询接进去
4. 把当前 AutoGPT 主流程改造成可观测的工作流
5. 抽出独立的 Retrieval Provider，并继续保留 RAGFlow 作为首个实现

## 迁移中的硬性要求

- 每一阶段都保留可运行入口
- 不允许因为重构而破坏现有已可用能力
- 新增能力必须优先接入 Tool Registry
- 高风险写能力在没有审批与审计前不得开放给外部 MCP

## 迁移完成后的状态

当以下条件全部满足时，可认为 ClassRobot 已完成从机器人项目到 AI 平台的升级：

- 机器人、后台、自动化运行器、外部 Agent 共用同一套 Domain 与 Tool
- AI 流程具备 durable execution、审批、恢复和追踪能力
- RAG 独立成知识平面，默认返回引用
- 系统既能消费外部 MCP，也能对外提供 MCP
- Prompt、Tool、Workflow、Retriever 都可以独立评测
