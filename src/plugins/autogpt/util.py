import re
import json
from uuid import uuid4
from time import time
from typing import Awaitable, Callable, Annotated
from datetime import datetime

from utils.helper import Helpers
from nonebot import logger
from utils.template import Prompt
from nonebot.params import Depends
from nonebot_plugin_alconna import UniMessage
from utils.helper.depends import HelpersDepends
from utils.models.depends import UserOrCreatedDepends
from utils.llm.message import Content, Context, LLMRole, Messages

from .exception import SessionLockError
from .pipeline import MessageProcessingPipeline
from .schema import ChatMessage, AutoTaskList, CommandObservation

pattern = r"!\[image\]\(([^)]+)\)"
ProgressReporter = Callable[[str], Awaitable[None]]


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


def markdown_to_message(text: str) -> UniMessage:
    """将 Markdown 文本转换为 `UniMessage` 消息对象。

    参数:
        text (str): 包含文本和 Markdown 图片语法的原始内容。

    返回:
        UniMessage: 适合直接发送的统一消息对象。
    """
    parts: list[str] = []
    last_idx = 0
    matches = list(re.finditer(pattern, text))

    # 按顺序拆分文本片段和 Markdown 图片地址。
    for match in matches:
        if match.start() > last_idx:
            parts.append(text[last_idx : match.start()])
        parts.append(match.group(1))
        last_idx = match.end()

    if last_idx < len(text):
        parts.append(text[last_idx:])

    if not matches:
        parts = [text]

    parts = [part for part in parts if part]

    reply_message = UniMessage()
    for part in parts:
        if part.startswith("http://") or part.startswith("https://"):
            reply_message += UniMessage.image(url=part)
        else:
            reply_message += part.replace(".", "⋅")
    return reply_message


class ChatSession:
    """封装单个用户的聊天会话状态与消息处理行为。

    该类负责维护用户会话上下文、系统提示词、会话锁以及
    AutoGPT 主流程调用入口。
    """

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
        self.last_trace_id = ""

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

    async def update_helpers(self, helpers: Helpers) -> None:
        """更新会话可用的帮助信息并刷新系统提示词。

        参数:
            helpers (Helpers): 当前用户可见的帮助信息集合。
        """
        self.helpers = helpers
        # 系统提示词依赖当前用户可见的命令集合，
        # 因此角色变化或 skill 热加载后都需要刷新首条 system 消息。
        prompts = await get_prompt_system(helpers)
        if self.messages and self.messages[0].role == LLMRole.system:
            self.messages[0].content = prompts
        else:
            self.messages.system_message(prompts)

    async def send_message(
        self,
        message: str | UniMessage | ChatMessage,
        progress_reporter: ProgressReporter | None = None,
    ) -> AutoTaskList | None:
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
            self.last_trace_id = f"autogpt-{uuid4().hex[:12]}"
            logger.info(f'AutoGPT trace "{self.last_trace_id}" started for user {self.user_id}')
            pipeline = MessageProcessingPipeline(
                helpers=self.helpers,
                messages=self.messages,
                trace_id=self.last_trace_id,
                progress_reporter=progress_reporter,
            )
            auto_tasks = await pipeline.process(message)
            self.messages = pipeline.messages
            logger.info(f'AutoGPT trace "{self.last_trace_id}" finished for user {self.user_id}')
            return auto_tasks
        except Exception as error:
            logger.exception(f'AutoGPT trace "{self.last_trace_id}" failed for user {self.user_id}: {error}')
            raise
        finally:
            self.lock = False

    def record_observations(self, observations: list[CommandObservation], trace_id: str = "") -> None:
        """把命令执行观察写回会话，供下一轮规划参考。

        这里记录的是“事件是否成功投递到项目命令系统”，不是业务命令
        最终是否完成。真正的业务结果仍由对应 matcher 回复用户。
        """
        if not observations:
            return
        payload = [observation.dict() for observation in observations]
        content = json.dumps(payload, ensure_ascii=False, default=str)
        self.messages.assistant_message(f"# 系统命令执行观察\ntrace_id: {trace_id or self.last_trace_id}\n{content}")

    def clear(self) -> None:
        """从会话管理器中移除当前会话。"""
        chat_session_manager.sessions.pop(self.user_id, None)


class ChatSessionManager:
    """管理聊天会话的生命周期、缓存与超时清理。"""

    timeout = 60 * 60

    def __init__(self) -> None:
        """初始化实例。"""
        self.sessions: dict[int, ChatSession] = {}

    def clear_timeout(self) -> None:
        """清理长时间未活动的会话。"""
        current_time = time()
        for session in list(self.sessions.values()):
            if current_time - session.update_time > self.timeout:
                del self.sessions[session.user_id]

    async def get_chat_session(self, user_id: int, helpers: Helpers) -> ChatSession:
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
