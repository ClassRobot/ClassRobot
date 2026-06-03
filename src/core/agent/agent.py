from __future__ import annotations

from dataclasses import field, dataclass

from src.core.llm.message import Context, LLMRole, Messages


@dataclass
class AgentSession:
    """保存一个智能体的多轮对话上下文。

    调用方可以把它按用户、群聊或业务对象缓存起来；同一个 session
    传给 `Agent.run()` 时，历史消息会继续参与下一轮模型调用。
    """

    messages: Messages = field(default_factory=Messages)

    def clear(self) -> None:
        self.messages.clear()

    def char_length(self) -> int:
        """返回当前会话中用户与助手文本的大致长度。"""

        return self.messages.char_length(LLMRole.user, LLMRole.assistant)

    async def compact(self, *, max_chars: int = 16000, keep_recent: int = 6) -> bool:
        """当会话过长时压缩历史内容。

        压缩会保留 system 消息和最近若干条消息，把更早的用户/助手对话
        折叠为一条摘要，避免长会话持续占用上下文。
        """

        from src.core.llm import LLMTaskType, client_create

        if self.char_length() <= max_chars or len(self.messages.messages) <= keep_recent + 1:
            return False

        system_messages = self.messages.get(LLMRole.system)
        recent_messages = self.messages.messages[-keep_recent:]
        history_messages = Messages(
            messages=[
                message
                for message in self.messages.messages[:-keep_recent]
                if isinstance(message, Context) and message.role in {LLMRole.user, LLMRole.assistant}
            ]
        )
        history_messages.user_message(
            "请压缩以上对话历史，保留用户目标、已确认事实、已调用过的系统命令、待办事项和重要约束。"
        )
        response = await client_create(
            history_messages,
            max_tokens=2048,
            task_type=LLMTaskType.summary,
        )
        summary = response.choices[0].message.content or "暂无可用摘要。"

        self.messages.clear()
        self.messages.extend(system_messages)
        self.messages.assistant_message("# 会话历史压缩摘要\n" + summary)
        self.messages.extend(recent_messages)
        return True
