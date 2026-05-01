# 智能体模块

`utils.llm.agents` 是项目内置的轻量智能体模块，底层复用 `utils.llm` 的模型路由和 OpenAI 兼容接口。它不强绑定 LangChain，调用方式尽量短，但仍支持多轮记忆、工具调用、结构化参数和多模型路由。

## 使用前提

在 NoneBot 插件里可以直接使用。独立脚本调试时需要先执行 `nonebot.init()`，因为项目的 `utils` 包会读取 NoneBot 配置。

如果要使用工具调用，对应模型配置需要开启：

```dotenv
LLM_CONFIGS='[{"name":"volcengine_ark","key":"你的 key","url":"https://ark.cn-beijing.volces.com/api/v3","model":"你的模型","supports_functools":true}]'
```

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

## 接入 NoneBot 插件

```python
from nonebot import on_command
from nonebot.matcher import Matcher
from utils.llm.agents import Agent, AgentSession

ask_agent = on_command("agent", priority=5, block=True)
agent = Agent("class_agent")
sessions: dict[str, AgentSession] = {}


@ask_agent.handle()
async def _(matcher: Matcher):
    session = sessions.setdefault("default", AgentSession())
    result = await agent.run("用户输入内容", session=session)
    await matcher.finish(result.content)
```

实际接入时把 `"用户输入内容"` 换成 matcher 收到的消息文本即可。
