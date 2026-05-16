# LLM 核心入口

`core.llm` 是模型网关、消息协议和模型配置的 canonical import。

从这一轮开始，`core.llm` 已经成为真实实现层；`utils.llm` 只保留兼容 alias。

## 主要入口

- `core.llm.client_create`
  - 统一模型调用入口。
- `core.llm.config.LLMConfig`
  - 单个模型配置。
- `core.llm.gateway.LLMGateway`
  - 模型路由与请求下发。
- `core.llm.message`
  - `Messages`、`Context`、`Content` 等消息模型。
- `core.llm.util`
  - `uni_message_to_contents()`、`json_loads()` 等上下文与解析工具。
- `core.llm.session`
  - 轻量聊天会话对象。

## 配置约定

- `.env*`
  - 放硬编码运行配置，例如 `LLM_CONFIGS`、代理、密钥。
- `config/`
  - 放运行时热更新数据，例如 Agent 编排图。
- 路径统一由 `utils.config` / `core.config` 提供。

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

## 兼容约定

- `utils.llm.*`
  - 旧路径，当前通过包级 alias 映射到 `core.llm.*`
- 新代码统一从 `core.llm.*` 导入
