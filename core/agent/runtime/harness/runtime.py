from __future__ import annotations

from dataclasses import dataclass

from utils.helper import Helpers
from core.llm.message import Messages
from utils.storage import ChatHistoryStore, chat_history_store

from .policy import PolicyHarness
from .context import ContextHarness
from ..knowledge import RuntimeContext, LocalKnowledgeRetriever
from .observability import ProgressReporter, ProgressFeedbackHarness


@dataclass(slots=True)
class AutoGPTHarness:
    """把 AutoGPT 运行时依赖整理成清晰的 Harness 分层入口。"""

    policy: PolicyHarness
    context: ContextHarness
    observability: ProgressFeedbackHarness

    @classmethod
    def build(
        cls,
        *,
        helpers: Helpers,
        messages: Messages,
        trace_id: str = "",
        progress_reporter: ProgressReporter | None = None,
        runtime_context: RuntimeContext | None = None,
        local_knowledge_retriever: LocalKnowledgeRetriever | None = None,
        chat_store: ChatHistoryStore | None = None,
    ) -> "AutoGPTHarness":
        """使用当前会话依赖构建标准 Harness。"""

        return cls(
            policy=PolicyHarness(helpers=helpers),
            context=ContextHarness(
                messages=messages,
                runtime_context=runtime_context,
                local_knowledge_retriever=local_knowledge_retriever or LocalKnowledgeRetriever(),
                chat_store=chat_store or chat_history_store,
            ),
            observability=ProgressFeedbackHarness(
                trace_id=trace_id,
                progress_reporter=progress_reporter,
            ),
        )

    @property
    def helpers(self) -> Helpers:
        return self.policy.helpers

    @property
    def command_tools(self):
        return self.policy.command_tools

    @property
    def skill_catalog_prompt(self) -> str:
        return self.policy.skill_catalog_prompt

    @property
    def messages(self) -> Messages:
        return self.context.messages

    @property
    def runtime_context(self) -> RuntimeContext | None:
        return self.context.runtime_context

    @property
    def local_knowledge_retriever(self) -> LocalKnowledgeRetriever:
        return self.context.local_knowledge_retriever

    @property
    def chat_store(self) -> ChatHistoryStore:
        return self.context.chat_store

    @property
    def trace_id(self) -> str:
        return self.observability.trace_id
