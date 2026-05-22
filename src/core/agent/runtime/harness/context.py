from __future__ import annotations

from dataclasses import field, dataclass

from src.core.llm.message import LLMRole, Messages
from src.core.storage import ChatHistoryStore, chat_history_store

from ..knowledge import RuntimeContext, LocalKnowledgeRetriever


@dataclass(slots=True)
class ContextHarness:
    """聚合 AutoGPT 的上下文层依赖。"""

    messages: Messages
    runtime_context: RuntimeContext | None = None
    local_knowledge_retriever: LocalKnowledgeRetriever = field(default_factory=LocalKnowledgeRetriever)
    chat_store: ChatHistoryStore = field(default_factory=lambda: chat_history_store)

    def serialize_recent_history(self, keep_recent: int = 8) -> str:
        """序列化最近若干轮消息，供轻量路由和规划使用。"""

        recent_messages = Messages(messages=self.messages.messages[-keep_recent:])
        return recent_messages.get(LLMRole.user, LLMRole.assistant).json(ensure_ascii=False)
