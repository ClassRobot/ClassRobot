from __future__ import annotations

from typing import Literal

from pydantic import Field, BaseModel

UserMessageType = Literal[
    "progress_message",
    "clarification_message",
    "confirmation_message",
    "final_reply",
    "failure_reply",
]


class UserVisibleMessage(BaseModel):
    """One user-visible message emitted by the Agent Host."""

    message_type: UserMessageType
    text: str
    write_to_history: bool = False


class ReplyEnvelope(BaseModel):
    """Normalized output bundle for reply synthesis and platform delivery."""

    trace_id: str = ""
    messages: list[UserVisibleMessage] = Field(default_factory=list)
    final_reply: str = ""
    failure_reason: str = ""


class ReplyPolicy:
    """Central policy for shaping user-visible Agent messages."""

    action_claim_markers = ("我去查", "我来查", "我现在查", "联网查询", "调用工具", "马上查询")

    def build_envelope(
        self,
        *,
        trace_id: str,
        reply: str = "",
        need_confirm: bool = False,
        requires_execution: bool = False,
        failed: bool = False,
        failure_reason: str = "",
    ) -> ReplyEnvelope:
        text = (reply or "").strip()
        envelope = ReplyEnvelope(trace_id=trace_id, final_reply=text, failure_reason=failure_reason)
        if not text:
            return envelope
        if failed:
            message_type: UserMessageType = "failure_reply"
        elif need_confirm:
            message_type = "confirmation_message"
        elif requires_execution:
            message_type = "progress_message"
        else:
            message_type = "final_reply"
        envelope.messages.append(
            UserVisibleMessage(message_type=message_type, text=text, write_to_history=message_type == "final_reply")
        )
        return envelope

    def claims_future_action(self, text: str) -> bool:
        return any(marker in text for marker in self.action_claim_markers)
