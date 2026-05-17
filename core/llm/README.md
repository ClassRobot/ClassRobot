# LLM 核心入口

`core.llm` 是项目统一的大模型接入层，负责模型配置、消息协议、网关路由和请求下发。

后续代码如果需要接入模型，请直接从这里导入；不要在业务模块里再各自包一层“私有 LLM 工具”。

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
  - 放启动前就需要确定的模型接入配置，例如 `LLM_CONFIGS`、代理、密钥。
- `config/`
  - 放运行时热更新数据，例如 Agent 编排图或本地动态配置。
- 路径统一由 `utils.config` 提供，不在业务代码里手写绝对路径。

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

## 导入约定

- 新代码统一从 `core.llm.*` 导入。
- 不要在业务代码中重新建立 LLM 门面或兼容 alias。
