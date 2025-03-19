from time import time
from typing import Annotated
from datetime import datetime

from utils.helper import Helpers
from utils.template import Prompt
from nonebot.params import Depends
from utils.helper.agent import HelperAgent
from nonebot_plugin_alconna import UniMessage
from utils.helper.depends import HelpersDepends
from utils.llm.util import uni_message_to_contents
from utils.models.depends import UserOrCreatedDepends
from utils.llm.message import Role, Content, Context, Messages
from utils.llm.agents.tools import LLMAgent, FileAgent, VisionAgent, SummaryAgent

from .exception import SessionLockError
from .schema import ChatMessage, AutoTaskList


async def get_prompt_system(helpers: Helpers) -> str:
    prompt_system = await Prompt("autogpt").render(
        {"helpers": helpers, "info": ("当前时间:" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}
    )
    return prompt_system


class ChatSession:
    def __init__(self, user_id: int, helpers: Helpers) -> None:
        self.update_time = time()
        self.user_id = user_id
        self.lock = False  # 聊天锁，防止一轮聊天还没结束又开始新的聊天
        self.messages = Messages()
        self.helpers = helpers

    def is_last_duplicate_message(self, contents: list[Content]) -> bool:
        user_content = Context(role=Role.user, content=contents)
        user_message = self.messages.get(Role.user)
        if user_message and user_message[-1] == user_content:
            return True
        return False

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

    async def send_message(self, message: str | UniMessage | ChatMessage) -> AutoTaskList | None:
        if self.lock:
            raise SessionLockError("聊天锁已经被锁定，无法发送消息！")
        try:
            self.lock = True
            content = None
            user_content = message.message if isinstance(message, ChatMessage) else uni_message_to_contents(message)

            # 是否与上文重复，重复则直接返回机器人的上一条回复
            if not self.is_last_duplicate_message(user_content):
                self.messages.user_message(user_content)
                summary = SummaryAgent()
                llm_agent = summary.link_to(LLMAgent)
                llm_agent.link_to(VisionAgent).link_to(llm_agent)
                llm_agent.link_to(FileAgent).link_to(llm_agent)
                llm_agent.link_to(HelperAgent).link_to(llm_agent)
                await summary.invoke(self.messages)

            # 获取最后一条消息
            last_message = self.messages[-1]
            if last_message.role == Role.assistant and isinstance(last_message, Context):
                content = last_message.single_modal()

            # 将内容转成task和回复用户的消息
            if content:
                auto_tasks = AutoTaskList.parse_str(content)
                # 更新最后一条消息
                last_message.content = f'{auto_tasks.reply}"\n<hr/>\n"{auto_tasks.json(exclude={"reply", "create_at"}, ensure_ascii=False)}'
                return auto_tasks
        finally:
            self.lock = False

    def clear(self):
        chat_session_manager.sessions.pop(self.user_id, None)


class ChatSessionManager:
    timeout = 60 * 60

    def __init__(self):
        self.sessions: dict[int, ChatSession] = {}

    # 检查是否有过期的session然后删除
    def clear_timeout(self):
        """清除过期的session"""
        current_time = time()
        for session in list(self.sessions.values()):
            if current_time - session.update_time > self.timeout:
                del self.sessions[session.user_id]

    async def get_chat_session(self, user_id: int, helpers: Helpers) -> ChatSession:
        # 检查是否有过期的session
        self.clear_timeout()

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
