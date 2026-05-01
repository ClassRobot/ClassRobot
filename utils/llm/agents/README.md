# 智能体模块

`utils.llm.agents` 是项目内置的轻量智能体模块，底层复用 `utils.llm` 的模型路由和 OpenAI 兼容接口。它不强绑定 LangChain，调用方式尽量短，但仍支持多轮记忆、工具调用、结构化参数、多模型路由和国内模型配置模板。

这个模块的目标是作为项目内 AI 编排底座：机器人运行在自己的项目里，接入 QQ/NoneBot，调用项目内工具与命令，模型可以换成火山方舟、DeepSeek、通义千问、Kimi、智谱等国内 OpenAI 兼容服务。

更完整的项目接入边界见 [docs/guides/agent-module.md](../../../docs/guides/agent-module.md)。

## 使用前提

在 NoneBot 插件里可以直接使用。独立脚本调试时需要先执行 `nonebot.init()`，因为项目的 `utils` 包会读取 NoneBot 配置。

如果要使用工具调用，对应模型配置需要开启：

```dotenv
LLM_CONFIGS='[{"name":"volcengine_ark","key":"你的 key","url":"https://ark.cn-beijing.volces.com/api/v3","model":"你的模型","supports_functools":true}]'
```

## 底层入口

如果要在插件内部创建一个项目默认智能体，可以使用 `create_classbot_agent()`。当前用户侧主入口仍然是 `src.plugins.autogpt` 的对话链路。

```python
from utils.llm.agents import create_classbot_agent

agent = create_classbot_agent(llm_name="volcengine_ark")
reply = await agent.run("帮我规划一下今天班级事务的处理顺序")
print(reply.content)
```

它内置了面向班级机器人场景的中文任务提示词，适合给 `autogpt` 或后续专业插件复用。

## 能力边界

- 深度分析: `autogpt` 会先压缩历史、抽取上下文、检索知识，再结合命令清单规划回复与任务。
- 工具调用: `Agent.tool` 支持普通函数和 async 函数，也支持单个 Pydantic 参数的复杂工具。
- 系统命令调用: `autogpt` 规划出的 `AutoTask` 调用的是本项目机器人命令，例如 `创建任务`、`校园地图`、`添加班级`，不是 Windows/Linux 命令；参数沿用 `utils.schemas.auto_task.Param`，可表达文本、图片和独立投递参数。
- 定时任务: 定时通知、任务提醒等能力应优先通过项目已有命令完成，例如通知插件的定时能力。
- 聊天内容压缩: `AgentSession.compact()` 会在上下文过长时压缩历史消息，保留系统提示、最近消息和摘要。

`autogpt` 自身已经通过 `SummaryAgent` 进行长会话压缩；`AgentSession.compact()` 主要留给后续插件内部复用。

## 最简单用法

```python
from utils.llm.agents import Agent

agent = Agent(
    "class_assistant",
    instructions="你是班级机器人助手，回答要简洁、准确。",
)

reply = await agent.run("帮我总结一下明天班会需要准备什么")
print(reply.content)
```

## 给智能体加工具

工具就是普通 Python 函数。函数名会作为工具名，类型标注会自动转成模型可理解的参数结构。

```python
from utils.llm.agents import Agent

agent = Agent(
    "school_agent",
    instructions="你可以根据需要调用工具完成学校、教师、学生、班级相关任务。",
)


@agent.tool
async def get_student(name: str) -> dict:
    """根据学生姓名查询学生信息。"""
    return {"name": name, "class": "一班"}


result = await agent.run("查一下张三在哪个班")
print(result.content)
```

## 多轮对话

同一个 `AgentSession` 会保存历史消息，适合接入 NoneBot 的单个用户会话。

```python
from utils.llm.agents import Agent, AgentSession

agent = Agent("chat_agent")
session = AgentSession()

await agent.run("记住：今天下午三点开班会", session=session)
reply = await agent.run("我刚才说什么时候开会？", session=session)
print(reply.content)
```

## 使用独立工具对象

如果工具要在多个智能体之间复用，可以用 `@tool` 先声明。

```python
from utils.llm.agents import Agent, tool


@tool
def add(a: int, b: int) -> int:
    """计算两个整数的和。"""
    return a + b


agent = Agent("math_agent", tools=[add])
reply = await agent.run("12 加 30 等于多少？")
print(reply.content)
```

## 复杂参数

复杂参数可以使用 Pydantic 模型。函数只有一个 Pydantic 参数时，模块会直接使用该模型的 JSON Schema。

```python
from pydantic import BaseModel, Field
from utils.llm.agents import Agent


class NoticeInput(BaseModel):
    title: str = Field(description="通知标题")
    content: str = Field(description="通知正文")
    class_name: str = Field(description="接收班级")


agent = Agent("notice_agent")


@agent.tool
async def create_notice(data: NoticeInput) -> dict:
    """创建班级通知。"""
    return {"created": True, "title": data.title}


reply = await agent.run("给一班创建一个明天交作业的通知")
print(reply.content)
```

## 常用参数

- `instructions`: 智能体系统提示词。
- `tools`: 传入可复用的 `AgentTool` 列表。
- `llm_name`: 指定 `.env` 里的模型配置名称；不填时使用项目模型路由自动选择。
- `max_steps`: 一轮任务最多允许几次工具调用，默认 `6`。
- `max_tokens`: 单次模型输出上限，默认 `2048`。
- `temperature`: 模型温度，默认 `0.1`。

## 接入 AutoGPT

用户侧入口由 `src.plugins.autogpt` 承担。它监听对机器人说的话，按当前用户可见的 Helper 命令清单规划回复和自动任务：

```text
@机器人 帮我规划一下本周班级事务
@机器人 明天 09:00 提醒我收一班作业
@机器人 帮我查询校园地图 图书馆
```

`autogpt` 的执行顺序是：会话压缩、消息归一化、意图路由、上下文抽取、显式计划、按需知识检索、任务规划、`handle_event()` 重新投递项目命令、写回命令 observation。处理过程中会通过进度回调给用户发送少量等待提示，例如正在查资料或正在处理；内部路由、规划和校验细节只写日志，不直接发给用户。

当前 AutoGPT 还会把 Helper 命令转换成内部 `CommandToolCatalog`。这个目录用于让路由器和 Planner 看到更稳定的命令名、参数约束、风险等级和 function calling 安全工具名，但业务执行仍然由原有 NoneBot 命令体系负责。

要扩展用户侧能力，优先给现有插件补充 `__helpers__` 和命令实现，让 `autogpt` 能通过 Helper 注册表发现并调用它。

## 国内模型配置模板

可以用 `build_llm_config()` 生成 `.env` 里 `LLM_CONFIGS` 的 JSON 项，减少手写字段出错。

```python
from utils.llm.agents import build_llm_config, dumps_llm_configs

configs = [
    build_llm_config(
        "volcengine_ark",
        name="volcengine_ark",
        key="你的火山方舟 key",
        model="你的火山方舟推理接入点 ID",
    ),
    build_llm_config(
        "deepseek",
        name="deepseek",
        key="你的 DeepSeek key",
        model="deepseek-v4-flash",
        priority=80,
    ),
]

print(dumps_llm_configs(configs))
```

当前内置供应商 key：

- `volcengine_ark`: 火山方舟，`https://ark.cn-beijing.volces.com/api/v3`
- `deepseek`: DeepSeek，`https://api.deepseek.com`
- `dashscope_qwen`: 阿里云百炼/通义千问，`https://dashscope.aliyuncs.com/compatible-mode/v1`
- `moonshot_kimi`: Moonshot/Kimi，`https://api.moonshot.ai/v1`
- `zhipu_glm`: 智谱 GLM，`https://open.bigmodel.cn/api/paas/v4`
