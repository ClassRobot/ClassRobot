# LLM 核心入口

`src.core.llm` 是项目统一的大模型接入层，负责模型配置、消息协议、网关路由和请求下发。

后续代码如果需要接入模型，请直接从这里导入；不要在业务模块里再各自包一层“私有 LLM 工具”。

## 主要入口

- `src.core.llm.client_create`
  - 统一模型调用入口。
- `src.core.llm.config.LLMConfig`
  - 单个模型配置。
- `src.core.llm.gateway.LLMGateway`
  - 模型路由与请求下发。
- `src.core.llm.message`
  - `Messages`、`Context`、`Content` 等消息模型。
- `src.core.llm.util`
  - `uni_message_to_contents()`、`json_loads()` 等上下文与解析工具。
- `src.core.llm.session`
  - 轻量聊天会话对象。

## 配置约定

- `.env*`
  - 放启动前就需要确定的模型接入配置和硬限制，例如 `LLM_CONFIGS`、代理、密钥、Agent 循环锁。
- `config/`
  - 放管理端或系统运行期的普通热更新数据。
- `resources/agent/`
  - 放 Agent 运行时编排图，例如 `agent_orchestration_runtime.json`。
- 路径统一由 `src.platform.config` 提供，不在业务代码里手写绝对路径。

## 模型配置示例

```dotenv
LLM_CONFIGS='[
  {
    "name": "gemini-3-flash-preview",
    "key": "your-key",
    "url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "model": "gemini-2.5-flash-preview-05-20",
    "proxy": "",
    "multi_modal": true,
    "supports_functools": true
  }
]'
```

## 代理规则

- 每个模型可单独设置 `proxy`。
- 默认不设置代理。
- Agent 和 Runtime 不直接拼接 HTTP 客户端，统一走 `LLMConfig.build_async_openai_client()`。

## Agent 循环锁

这些配置同样写在 `.env`，因为它们是启动级安全边界，不属于运行时热更新数据：

```dotenv
AGENT_LOOP_MAX_STEPS=8
AGENT_LOOP_MAX_VERIFY_ATTEMPTS=3
AGENT_LOOP_MAX_REPEAT_ACTIONS=2
AGENT_LOOP_MAX_RUNTIME_SECONDS=120
```

`src.core.agent.runtime.LoopBudget` 会强制执行这些上限，避免 Agent 反复验证或重复调用命令导致 token 和命令资源持续消耗。

## 导入约定

- 新代码统一从 `src.core.llm.*` 导入。
- 不要在业务代码中重新建立 LLM 门面或兼容 alias。
