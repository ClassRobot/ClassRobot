import json
from time import time
from typing import Annotated

from utils.helper import Helpers
from nonebot.params import Depends
from utils.llm import client_create
from utils.template import get_prompts
from nonebot_plugin_alconna import UniMessage
from utils.helper.depends import HelpersDepends
from utils.llm.schema import Role, Content, Messages
from utils.models.depends import UserOrCreatedDepends
from openai.types.chat.chat_completion import ChatCompletion
from utils.llm.util import json_loads, uni_message_to_contents
from utils.llm.typings import ChatCompletionToolParam, ChatCompletionMessageToolCall

from .exception import SessionLockError
from .schemas import ChatMessage, AutoTaskList


async def get_prompt_system(helpers: Helpers) -> str:
    prompt_system = await get_prompts("autogpt.jinja", {"helpers": helpers})

    print("help len", helpers.to_string().__len__())
    return prompt_system


class ChatSession:
    functools: list[ChatCompletionToolParam] = [
        {
            "type": "function",
            "function": {
                "name": "get_command_help",
                "description": "获取命令的详细帮助信息来辅助机器人更好的执行命令,该函数是机器人的功能函数,不要告知用户.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "commands": {
                            "type": "string",
                            "description": "一个或多个需要查询的命令,多个命令使用逗号分隔,例如: 命令1,命令2.",
                        }
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "vision_model",
                "description": "分析上下文中，用户想要理解的哪些图片内容,该函数是机器人的功能函数,不要告知用户.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "urls": {
                            "type": "string",
                            "description": '格式如下: ["url1", "url2"]',
                        },
                        "desc": {
                            "type": "string",
                            "description": "详细说明想从图片中识别的内容",
                        },
                    },
                },
            },
        },
    ]

    def __init__(self, user_id: int, helpers: Helpers) -> None:
        self.update_time = time()
        self.user_id = user_id
        self.lock = False  # 聊天锁，防止一轮聊天还没结束又开始新的聊天
        self.messages = Messages()
        self.helpers = helpers

    async def update_helpers(self, helpers: Helpers):
        self.helpers = helpers
        prompts = await get_prompt_system(helpers)
        if self.messages and self.messages[0].role == Role.system:
            self.messages[0].content = prompts
        else:
            self.messages.system_message(prompts)

    async def call_tools(self, tool_calls: list[ChatCompletionMessageToolCall]) -> ChatCompletion:
        for tool in tool_calls:
            if tool.function.name == "get_command_help":
                args: list[str] = json.loads(tool.function.arguments)["commands"].split(",")
                self.messages.tool_message(tool.id, self.get_command_help(args))
            elif tool.function.name == "vision_model":
                contents: list[Content] = []
                data: dict = json.loads(tool.function.arguments)
                if desc := data.get("desc"):
                    contents.append(Content(type="text", value=desc))
                if urls := data.get("urls"):
                    urls = json.loads(urls)
                    for url in urls:
                        contents.append(Content(type="image", value=url))
                await self.vision_model(contents)

        return await client_create(self.messages, functools=self.functools, multi_modal=False)

    async def vision_model(self, contents: list[Content]):
        messages = Messages()
        messages.extend(self.messages.get(Role.system))
        messages.user_message(contents)
        response = await client_create(messages, multi_modal=True)
        self.messages.tool_message(response.choices[0].message.content)  # type: ignore

    def get_command_help(self, commands: list[str]):
        helpers_string = ""
        for command in set(commands):
            if helper := self.helpers.get_helper(command):
                helpers_string += (
                    f"""\n<command_helper_{helper.command}>\n{helper.json()}\n</command_helper_{helper.command}>\n"""
                )
        return helpers_string

    async def send_message(self, message: str | UniMessage | ChatMessage):
        if self.lock:
            raise SessionLockError("聊天锁已经被锁定，无法发送消息！")
        try:
            self.lock = True
            self.messages.user_message(
                message.message if isinstance(message, ChatMessage) else uni_message_to_contents(message)
            )
            response = await client_create(self.messages, functools=self.functools, multi_modal=False)
            # 检测是否有工具函数需要调用
            if response.choices[0].message.tool_calls:
                self.messages.add_tool(response.choices[0].message)
                # 调用工具函数
                response = await self.call_tools(response.choices[0].message.tool_calls)
            # 可能会存在```json和```这种情况，需要删除
            content = response.choices[0].message.content  # type: ignore
            if content:
                contents = content.split("<hr/>")
                task_data = contents[-1].strip()
                try:
                    auto_tasks = AutoTaskList.parse_obj(json_loads(task_data))
                    contents = contents[:-1]
                except json.JSONDecodeError:
                    auto_tasks = AutoTaskList()
                auto_tasks.reply = "<hr/>".join(contents).strip()
                if auto_tasks.is_violation:
                    auto_tasks.reply = "用户发送的消息包含违规内容，已被屏蔽！"

                if auto_tasks.reply:
                    self.messages.assistant_message(
                        auto_tasks.reply + "\n<hr/>\n" + auto_tasks.json(exclude={"reply"}, ensure_ascii=False),
                    )
                return auto_tasks
            return content
        finally:
            self.lock = False

    def clear(self):
        chat_session_manager.sessions.pop(self.user_id, None)


class ChatSessionManager:
    timeout = 60 * 60 * 24  # 24小时

    def __init__(self):
        self.sessions: dict[int, ChatSession] = {}

    # 检查是否有过期的session然后删除
    def check_timeout(self):
        current_time = time()
        for session in self.sessions.values():
            if current_time - session.update_time > self.timeout:
                del self.sessions[session.user_id]

    async def get_chat_session(self, user_id: int, helpers: Helpers) -> ChatSession:
        # 检查是否有过期的session
        self.check_timeout()

        if session := self.sessions.get(user_id):
            session.update_time = time()
        else:
            session = ChatSession(user_id, helpers)
        await session.update_helpers(helpers)
        self.sessions[user_id] = session
        return session


async def get_chat_session(user: UserOrCreatedDepends, helpers: HelpersDepends) -> ChatSession:
    chat_session = await chat_session_manager.get_chat_session(user.id, helpers)
    return chat_session


ChatSessionDepends = Annotated[ChatSession, Depends(get_chat_session)]
chat_session_manager = ChatSessionManager()
