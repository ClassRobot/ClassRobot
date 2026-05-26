from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, BaseModel
from src.core.llm.message import LLMRole, Messages

ContextLayer = Literal[
    "turn_context",
    "session_context",
    "workflow_context",
    "user_memory",
    "agent_memory",
    "knowledge_context",
    "tool_state_context",
]


class ContextPack(BaseModel):
    """Minimal, layered context view passed through the Agent Host."""

    trace_id: str = ""
    turn_context: dict[str, Any] = Field(default_factory=dict)
    session_context: dict[str, Any] = Field(default_factory=dict)
    workflow_context: dict[str, Any] = Field(default_factory=dict)
    user_memory: dict[str, Any] = Field(default_factory=dict)
    agent_memory: dict[str, Any] = Field(default_factory=dict)
    knowledge_context: dict[str, Any] = Field(default_factory=dict)
    tool_state_context: dict[str, Any] = Field(default_factory=dict)

    def slice_for(self, requirements: list[ContextLayer]) -> dict[str, Any]:
        """Return only the context layers a specialized agent requested."""

        return {layer: getattr(self, layer) for layer in requirements}

    def compact_summary(self) -> str:
        """Build a short audit summary without exposing full prompt context."""

        parts = [
            f"turn={self.turn_context.get('message_preview', '')}",
            f"messages={self.session_context.get('message_count', 0)}",
        ]
        if self.workflow_context:
            parts.append(f"workflow={self.workflow_context.get('status', '')}")
        if self.tool_state_context:
            parts.append(f"tools={self.tool_state_context.get('observation_count', 0)}")
        return " | ".join(part for part in parts if part.strip(" |"))


class ContextEngine:
    """Assemble the layered context contract used by Host-controlled agents."""

    max_recent_items = 5

    def build_pack(
        self,
        *,
        trace_id: str,
        user_id: int | None,
        message_preview: str,
        messages: Messages,
        pending_workflow: Any = None,
        last_workflow: Any = None,
        last_turn_result: Any = None,
    ) -> ContextPack:
        workflow = pending_workflow or last_workflow
        observations = self.extract_recent_observation_summaries(messages)
        if last_turn_result is not None and getattr(last_turn_result, "workflow", None) is not None:
            observations.extend(
                self.workflow_step_summaries(list(getattr(last_turn_result.workflow, "steps", []) or []))
            )
        reply_records = self.extract_recent_reply_records(messages)

        workflow_context: dict[str, Any] = {}
        if workflow is not None:
            workflow_context = {
                "trace_id": getattr(workflow, "trace_id", ""),
                "kind": getattr(workflow, "kind", ""),
                "status": getattr(workflow, "status", ""),
                "goal": getattr(workflow, "goal", ""),
                "need_confirm": bool(getattr(workflow, "need_confirm", False)),
                "step_count": len(getattr(workflow, "steps", []) or []),
            }

        return ContextPack(
            trace_id=trace_id,
            turn_context={
                "trace_id": trace_id,
                "user_id": user_id,
                "message_preview": message_preview,
            },
            session_context={
                "message_count": len(getattr(messages, "messages", [])),
                "has_system_prompt": bool(messages and getattr(messages[0], "role", None)),
                "recent_final_replies": reply_records[-self.max_recent_items :],
            },
            workflow_context=workflow_context,
            tool_state_context={
                "observation_count": len(observations),
                "recent_observations": observations[-self.max_recent_items :],
            },
        )

    @classmethod
    def extract_recent_reply_records(cls, messages: Messages) -> list[dict[str, Any]]:
        """Read compact final replies already written into the conversation memory."""

        records: list[dict[str, Any]] = []
        for message in getattr(messages, "messages", []):
            if getattr(message, "role", None) != LLMRole.assistant:
                continue
            text = cls.message_text(message)
            marker = "# 系统最终回复记录"
            if marker not in text:
                continue
            json_start = text.find("{")
            if json_start < 0:
                continue
            try:
                payload = json.loads(text[json_start:])
            except json.JSONDecodeError:
                continue
            records.append(
                {
                    "trace_id": str(payload.get("trace_id") or ""),
                    "summary": str(payload.get("summary") or payload.get("reply") or "")[:500],
                    "source_observations": list(payload.get("source_observations") or [])[:10],
                    "language": str(payload.get("language") or "zh-CN"),
                }
            )
        return records

    @classmethod
    def extract_recent_observation_summaries(cls, messages: Messages) -> list[dict[str, Any]]:
        """Read compact tool observations from session memory without exposing raw output."""

        observations: list[dict[str, Any]] = []
        for message in getattr(messages, "messages", []):
            if getattr(message, "role", None) != LLMRole.assistant:
                continue
            text = cls.message_text(message)
            if "# 系统命令执行观察" not in text:
                continue
            json_start = text.find("[")
            if json_start < 0:
                continue
            try:
                payload = json.loads(text[json_start:])
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, list):
                continue
            for item in payload:
                if not isinstance(item, dict):
                    continue
                observations.append(
                    {
                        "source_type": str(item.get("source_type") or item.get("dispatch_type") or "unknown"),
                        "tool_name": str(item.get("tool_name") or item.get("command") or ""),
                        "status": str(item.get("status") or ""),
                        "relevance": str(item.get("relevance") or ""),
                        "answer_quality": str(item.get("answer_quality") or ""),
                        "summary": str(
                            item.get("context_summary") or item.get("display_summary") or item.get("message") or ""
                        )[:500],
                    }
                )
        return observations

    @staticmethod
    def message_text(message: Any) -> str:
        """Flatten a stored message if it is one of the project's Context objects."""

        if hasattr(message, "single_modal"):
            return str(message.single_modal())
        content = getattr(message, "content", "")
        return content if isinstance(content, str) else str(content or "")

    @staticmethod
    def workflow_step_summaries(steps: list[Any]) -> list[dict[str, Any]]:
        """Convert workflow steps into compact observation-like state summaries."""

        summaries: list[dict[str, Any]] = []
        for step in steps:
            message = str(getattr(step, "observation_message", "") or "")
            if not message:
                continue
            summaries.append(
                {
                    "source_type": str(getattr(step, "step_type", "") or "workflow"),
                    "tool_name": str(getattr(step, "command", "") or ""),
                    "status": str(getattr(step, "status", "") or ""),
                    "summary": message[:500],
                }
            )
        return summaries
