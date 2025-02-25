import json
from time import time
from typing import Annotated

from utils.helper import Helpers
from nonebot.params import Depends
from utils.llm import client_create
from utils.llm.schema import Messages
from nonebot_plugin_alconna import UniMessage
from utils.helper.depends import HelpersDepends
from utils.models.depends import UserOrCreatedDepends
from openai.types.chat.chat_completion import ChatCompletion
from utils.llm.util import json_loads, uni_message_to_contents
from utils.llm.typings import ChatCompletionToolParam, ChatCompletionMessageToolCall

from .prompt import get_prompt_system
from .exception import SessionLockError
from .schemas import ChatMessage, AutoTaskList


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
    ]

    def __init__(self, user_id: int, helpers: Helpers) -> None:
        self.update_time = time()
        self.user_id = user_id
        self.lock = False  # 聊天锁，防止一轮聊天还没结束又开始新的聊天
        self.messages = Messages()
        self.helpers = helpers
        self.messages.system_message(get_prompt_system(helpers))

    def update_helpers(self, helpers: Helpers):
        self.helpers = helpers
        self.messages[0].content = get_prompt_system(helpers)

    async def call_tools(
        self, tool_calls: list[ChatCompletionMessageToolCall]
    ) -> ChatCompletion:
        for tool in tool_calls:
            if tool.function.name == "get_command_help":
                args: list[str] = json.loads(tool.function.arguments)["commands"].split(
                    ","
                )
                self.messages.tool_message(tool.id, self.get_command_help(args))
        return await client_create(self.messages)

    def get_command_help(self, commands: list[str]):
        helpers_string = ""
        for command in set(commands):
            if helper := self.helpers.get_helper(command):
                helpers_string += f"""\n<command_helper_{helper.command}>\n{helper.json()}\n</command_helper_{helper.command}>\n"""
        return helpers_string

    async def send_message(self, message: str | UniMessage | ChatMessage):
        if self.lock:
            raise SessionLockError("聊天锁已经被锁定，无法发送消息！")
        try:
            self.lock = True
            self.messages.user_message(
                message.message
                if isinstance(message, ChatMessage)
                else uni_message_to_contents(message)
            )
            response = await client_create(self.messages)
            if response.choices[0].message.tool_calls:
                self.messages.add_tool(response.choices[0].message)
                response = await self.call_tools(response.choices[0].message.tool_calls)
            # 可能会存在```json和```这种情况，需要删除
            content = response.choices[0].message.content  # type: ignore
            if content:
                print(content)
                contents = content.split("<hr/>")
                task_data = contents[-1].strip()
                try:
                    auto_tasks = AutoTaskList.parse_obj(json_loads(task_data))
                except json.JSONDecodeError:
                    auto_tasks = AutoTaskList()
                auto_tasks.reply = "<hr/>".join(contents[:-1]).strip()
                if auto_tasks.is_violation:
                    auto_tasks.reply = "用户发送的消息包含违规内容，已被屏蔽！"

                if auto_tasks.reply:
                    self.messages.assistant_message(
                        auto_tasks.reply
                        + "\n<hr/>\n"
                        + auto_tasks.json(exclude={"reply"}, ensure_ascii=False),
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

    def get_chat_session(self, user_id: int, helpers: Helpers) -> ChatSession:
        # 检查是否有过期的session
        self.check_timeout()

        if session := self.sessions.get(user_id):
            session.update_time = time()
            session.update_helpers(helpers)
            return session
        session = ChatSession(user_id, helpers)
        self.sessions[user_id] = session
        return session


async def get_chat_session(
    user: UserOrCreatedDepends, helpers: HelpersDepends
) -> ChatSession:
    chat_session = chat_session_manager.get_chat_session(user.id, helpers)
    return chat_session


ChatSessionDepends = Annotated[ChatSession, Depends(get_chat_session)]
chat_session_manager = ChatSessionManager()
