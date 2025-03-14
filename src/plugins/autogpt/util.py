import json
from time import time
from typing import Annotated
from datetime import datetime

from nonebot import logger
from utils.helper import Helpers
from nonebot.params import Depends
from utils.llm import client_create
from utils.template import get_prompts
from nonebot_plugin_alconna import UniMessage
from utils.helper.depends import HelpersDepends
from utils.llm.schema import Role, Content, Messages
from utils.models.depends import UserOrCreatedDepends
from utils.llm.typings import ChatCompletionMessageToolCall
from openai.types.chat.chat_completion import ChatCompletion
from utils.llm.util import json_loads, uni_message_to_contents

from .functools import functools
from .exception import SessionLockError
from .schemas import ChatMessage, AutoTaskList


async def get_prompt_system(helpers: Helpers) -> str:
    prompt_system = await get_prompts(
        "autogpt.jinja", {"helpers": helpers, "info": ("当前时间:" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}
    )
    return prompt_system


class ChatSession:
    def __init__(self, user_id: int, helpers: Helpers) -> None:
        self.update_time = time()
        self.user_id = user_id
        self.lock = False  # 聊天锁，防止一轮聊天还没结束又开始新的聊天
        self.messages = Messages()
        self.helpers = helpers

    async def update_helpers(self, helpers: Helpers):
        """更新helper信息

        Args:
            helpers (Helpers): 帮助信息
        """
        self.helpers = helpers
        prompts = await get_prompt_system(helpers)
        if self.messages and self.messages[0].role == Role.system:
            self.messages[0].content = prompts
        else:
            self.messages.system_message(prompts)

    async def call_tools(self, tool_calls: list[ChatCompletionMessageToolCall]) -> ChatCompletion:
        for tool in tool_calls:
            params = json.loads(tool.function.arguments)
            if tool.function.name == "get_command_help":
                args: list[str] = params["commands"].split(",")
                self.messages.tool_message(tool.id, self.get_command_help(args))
            elif tool.function.name == "vision_model":
                response = await self.vision_model(**params)
                self.messages.tool_message(tool.id, response.choices[0].message.content)  # type: ignore
            elif tool.function.name == "file_model":
                response = await self.file_model(**params)
                self.messages.tool_message(tool.id, response.choices[0].message.content)  # type: ignore
        return await client_create(self.messages, multi_modal=False)

    async def vision_model(self, desc: str, urls: str) -> ChatCompletion:
        contents: list[Content] = [Content(type="text", value=desc)]
        if urls:
            contents.extend(Content(type="image", value=url) for url in json.loads(urls))
        messages = Messages()
        messages.extend(self.messages.get(Role.system))
        messages.user_message(contents)
        return await client_create(messages, multi_modal=True)

    async def file_model(self, desc: str, urls: str):
        ...

    def get_command_help(self, commands: list[str]):
        helpers_string = ""
        for command in set(commands):
            if helper := self.helpers.get_helper(command):
                helpers_string += helper.json(ensure_ascii=False) + "\n\n"
        return helpers_string

    async def send_message(self, message: str | UniMessage | ChatMessage) -> AutoTaskList | None:
        if self.lock:
            raise SessionLockError("聊天锁已经被锁定，无法发送消息！")
        try:
            self.lock = True
            self.messages.user_message(
                message.message if isinstance(message, ChatMessage) else uni_message_to_contents(message)
            )
            response = await client_create(self.messages, functools=functools.functools, multi_modal=False)
            # 检测是否有工具函数需要调用
            if response.choices[0].message.tool_calls:
                self.messages.add_tool(response.choices[0].message)
                # 调用工具函数
                response = await self.call_tools(response.choices[0].message.tool_calls)
            # 可能会存在```json和```这种情况，需要删除
            content = response.choices[0].message.content
            logger.info(f"`{self.user_id}` response: {content}")
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
