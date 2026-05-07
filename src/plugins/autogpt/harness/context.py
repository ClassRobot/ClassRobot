from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from utils.llm.message import Content, LLMRole, Messages
from utils.storage import ChatHistoryStore, chat_history_store

from ..knowledge import AgentLocalKnowledgeRetriever, AgentRuntimeContext


@dataclass(slots=True)
class AgentContextHarness:
    """聚合 AutoGPT 的上下文层依赖。"""

    messages: Messages
    runtime_context: AgentRuntimeContext | None = None
    local_knowledge_retriever: AgentLocalKnowledgeRetriever = field(default_factory=AgentLocalKnowledgeRetriever)
    chat_store: ChatHistoryStore = field(default_factory=lambda: chat_history_store)

    def serialize_recent_history(self, keep_recent: int = 8) -> str:
        """序列化最近若干轮消息，供轻量路由和规划使用。"""

        recent_messages = Messages(messages=self.messages.messages[-keep_recent:])
        return recent_messages.get(LLMRole.user, LLMRole.assistant).json(ensure_ascii=False)

    def can_retrieve_local_knowledge(
        self,
        contents: list[Content],
        should_retrieve: Callable[[list[Content]], bool],
    ) -> bool:
        """判断当前轮次是否具备本地上下文检索条件。"""

        return self.runtime_context is not None and should_retrieve(contents)
