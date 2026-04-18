import re
from time import time
from asyncio import gather
from typing import Annotated
from datetime import datetime

from utils.helper import Helpers
from utils.template import Prompt
from nonebot.params import Depends
from nonebot_plugin_alconna import UniMessage
from utils.helper.depends import HelpersDepends
from utils.llm.util import uni_message_to_contents
from utils.models.depends import UserOrCreatedDepends
from utils.llm.message import Content, Context, LLMRole, Messages
from utils.llm.agents.tools import RagAgent, ExtractAgent, SummaryAgent, AutoTaskAgent

from .exception import SessionLockError
from .schema import ChatMessage, AutoTaskList

pattern = r"!\[image\]\(([^)]+)\)"


async def get_prompt_system(helpers: Helpers) -> str:
    """根据当前可用命令生成 AutoGPT 系统提示词。

    参数:
        helpers (Helpers): 当前用户可见的帮助信息集合。

    返回:
        str: 渲染后的系统提示词文本。
    """
    prompt_system = await Prompt("autogpt").render(
        {"helpers": helpers, "info": ("当前时间:" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}
    )
    return prompt_system


def markdown_to_message(text: str):
    # 正则表达式查找Markdown图片格式
    """将 Markdown 文本转换为 `UniMessage` 消息对象。

    参数:
        text (str): 包含文本和 Markdown 图片语法的原始内容。

    返回:
        UniMessage: 适合直接发送的统一消息对象。
    """
    parts = []
    last_idx = 0
    matches = list(re.finditer(pattern, text))

    # 处理找到的每个匹配项
    for match in matches:
        # 添加匹配前的文本
        if match.start() > last_idx:
            parts.append(text[last_idx : match.start()])
        # 添加图片URL
        parts.append(match.group(1))
        last_idx = match.end()

    # 添加最后一个匹配后的剩余文本
    if last_idx < len(text):
        parts.append(text[last_idx:])

    # 如果没有找到任何匹配项，直接使用原始文本
    if not matches:
        parts = [text]

    # 过滤空字符串
    parts = [part for part in parts if part]

    reply_message = UniMessage()
    for part in parts:
        if part.startswith("http://") or part.startswith("https://"):
            reply_message += UniMessage.image(url=part)
        else:
            reply_message += part.replace(".", "⋅")
    return reply_message


class ChatSession:
    """封装聊天会话状态与行为。"""
    def __init__(self, user_id: int, helpers: Helpers) -> None:
        """初始化实例。

        参数:
            user_id (int): 用户标识。
            helpers (Helpers): 帮助信息集合。
        """
        self.update_time = time()
        self.user_id = user_id
        self.lock = False  # 聊天锁，防止一轮聊天还没结束又开始新的聊天
        self.messages = Messages()
        self.helpers = helpers

    def is_last_duplicate_message(self, contents: list[Content]) -> bool:
        """检查即将发送的用户消息是否与上一条重复。

        参数:
            contents (list[Content]): 当前待发送的消息内容列表。

        返回:
            bool: 如果与最后一条用户消息一致则返回 `True`。
        """
        user_content = Context(role=LLMRole.user, content=contents)
        user_message = self.messages.get(LLMRole.user)
        if user_message and user_message[-1] == user_content:
            return True
        return False

    async def update_helpers(self, helpers: Helpers):
        """更新会话可用的帮助信息并刷新系统提示词。

        参数:
            helpers (Helpers): 当前用户可见的帮助信息集合。
        """
        self.helpers = helpers
        # The system prompt is assembled from the helpers visible to the current user,
        # so role changes and newly loaded commands must refresh the first message.
        prompts = await get_prompt_system(helpers)
        if self.messages and self.messages[0].role == LLMRole.system:
            self.messages[0].content = prompts
        else:
            self.messages.system_message(prompts)

    async def send_message(self, message: str | UniMessage | ChatMessage) -> AutoTaskList | None:
        """处理用户消息并执行 AutoGPT 主流程。

        参数:
            message (str | UniMessage | ChatMessage): 用户输入的原始消息。

        返回:
            AutoTaskList | None: 解析出的自动任务结果，不可生成时返回 `None`。
        """
        if self.lock:
            raise SessionLockError("聊天锁已经被锁定，无法发送消息！")
        try:
            self.lock = True
            content = None
            user_content = message.message if isinstance(message, ChatMessage) else uni_message_to_contents(message)

            # The chat pipeline is: trim long history, append the latest user turn,
            # extract a compact structured context, then run retrieval and command
            # planning in parallel against that reduced context.
            self.messages = await SummaryAgent().execute(self.messages)
            self.messages.user_message(user_content)
            extract = await ExtractAgent().execute(self.messages)
            tasks = (
                RagAgent().execute(extract),
                AutoTaskAgent(helpers=self.helpers, messages=self.messages).execute(extract),
            )
            results = tuple(i for i in await gather(*tasks) if i is not None)
            if results:
                print("send", results[0])
                self.messages.assistant_message(results[0])

            # 获取最后一条消息
            last_message = self.messages[-1]
            if last_message.role == LLMRole.assistant and isinstance(last_message, Context):
                content = last_message.single_modal()

            # 将内容转成task和回复用户的消息
            if content:
                auto_tasks = AutoTaskList.parse_str(content)
                # Persist the human-readable reply together with the generated task
                # payload so later turns can see what the planner already decided.
                last_message.content = f'{auto_tasks.reply}"\n<hr/>\n"{auto_tasks.json(exclude={"reply", "create_at"}, ensure_ascii=False)}'
                return auto_tasks
        finally:
            self.lock = False

    def clear(self):
        """从会话管理器中移除当前会话。"""
        chat_session_manager.sessions.pop(self.user_id, None)


class ChatSessionManager:
    """管理聊天会话的生命周期、缓存与超时清理。"""
    timeout = 60 * 60

    def __init__(self):
        """初始化实例。"""
        self.sessions: dict[int, ChatSession] = {}

    # 检查是否有过期的session然后删除
    def clear_timeout(self):
        """清理长时间未活动的会话。"""
        current_time = time()
        for session in list(self.sessions.values()):
            if current_time - session.update_time > self.timeout:
                del self.sessions[session.user_id]

    async def get_chat_session(self, user_id: int, helpers: Helpers) -> ChatSession:
        # 检查是否有过期的session
        """获取用户会话，不存在则创建并刷新帮助上下文。

        参数:
            user_id (int): 当前用户标识。
            helpers (Helpers): 当前用户可见的帮助信息集合。

        返回:
            ChatSession: 已准备好系统提示词的聊天会话对象。
        """
        self.clear_timeout()

        if session := self.sessions.get(user_id):
            session.update_time = time()
        else:
            session = ChatSession(user_id, helpers)
        await session.update_helpers(helpers)
        self.sessions[user_id] = session
        return session


async def get_chat_session(user: UserOrCreatedDepends, helpers: HelpersDepends) -> ChatSession:
    """获取当前用户对应的聊天会话依赖对象。"""
    chat_session = await chat_session_manager.get_chat_session(user.id, helpers)
    return chat_session


ChatSessionDepends = Annotated[ChatSession, Depends(get_chat_session)]
chat_session_manager = ChatSessionManager()
