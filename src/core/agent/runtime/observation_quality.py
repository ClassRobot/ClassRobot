from __future__ import annotations

import re
import json
from typing import Any

from nonebot import logger

from .schema import CommandObservation, ToolObservationStatus


class ObservationQualityGate:
    """为工具结果补齐质量判断，避免“工具成功”被误当成“任务成功”。"""

    max_summary_chars = 900
    hot_topic_terms = ("热点", "热搜", "新闻", "最新", "最近", "当前动态", "网上")
    obvious_park_mismatch_terms = (
        "park",
        "parks",
        "london",
        "visitlondon",
        "hyde park",
        "regent",
        "公园",
        "伦敦",
    )
    url_pattern = re.compile(r"https?://\S+")

    def evaluate(
        self,
        observation: CommandObservation,
        *,
        user_goal: str = "",
        query: str = "",
    ) -> CommandObservation:
        """返回补齐质量字段后的 observation。"""

        updated = observation.model_copy(deep=True)
        if user_goal and not updated.user_goal:
            updated.user_goal = user_goal
        if query and not updated.query:
            updated.query = query
        if not updated.tool_name:
            updated.tool_name = updated.command
        if updated.dispatch_type == "mcp_tool":
            updated.source_type = "mcp_tool"

        text = self.observation_text(updated)
        updated.status = self.resolve_status(updated, text)
        summary_source = self.preferred_summary_source(updated)
        updated.display_summary = self.safe_summary(updated.display_summary or summary_source)
        updated.context_summary = self.safe_summary(
            updated.context_summary or updated.display_summary or summary_source
        )

        if not updated.success:
            updated.relevance = "none"
            updated.answer_quality = "failed"
            updated.next_actions = self.merge_next_actions(updated.next_actions, ["explain_failure"])
            return updated

        if not text.strip():
            updated.relevance = "none"
            updated.answer_quality = "insufficient"
            updated.display_summary = updated.display_summary or "工具没有返回可用于回答的内容。"
            updated.context_summary = updated.context_summary or updated.display_summary
            updated.next_actions = self.merge_next_actions(updated.next_actions, ["ask_user"])
            return updated

        if self.is_obviously_irrelevant(updated, text):
            updated.relevance = "low"
            updated.answer_quality = "insufficient"
            updated.display_summary = "工具返回的结果与用户问题不匹配，不能作为可靠答案。"
            updated.context_summary = (
                f"工具 `{updated.tool_name or updated.command}` 返回内容与目标不匹配。"
                f" query={updated.query or '未记录'}"
            )
            updated.next_actions = self.merge_next_actions(updated.next_actions, ["rewrite_query", "retry_search"])
            logger.info(
                f'AutoGPT trace "{updated.trace_id}" observation marked low relevance '
                f'tool="{updated.tool_name or updated.command}" query="{self.preview(updated.query)}"'
            )
            return updated

        if updated.relevance in {"unknown", "none"}:
            updated.relevance = "high" if updated.dispatch_type == "command" else "medium"
        if updated.answer_quality == "unknown":
            updated.answer_quality = "complete" if updated.relevance in {"high", "medium"} else "partial"
        updated.next_actions = self.merge_next_actions(updated.next_actions, ["answer"])
        return updated

    def is_obviously_irrelevant(self, observation: CommandObservation, text: str) -> bool:
        """识别少数确定性的跑偏结果；语义判断仍交给回复器处理。"""

        goal_text = f"{observation.user_goal} {observation.query}".lower()
        result_text = text.lower()
        asks_hot_topics = any(term.lower() in goal_text for term in self.hot_topic_terms)
        if not asks_hot_topics:
            return False
        return sum(1 for term in self.obvious_park_mismatch_terms if term in result_text) >= 2

    @classmethod
    def observation_text(cls, observation: CommandObservation) -> str:
        """拼出用于质量判断的文本，不把 raw_result 当作优先上下文。"""

        parts = [
            observation.message,
            observation.display_summary,
            observation.context_summary,
            *observation.context_outputs,
            *observation.outputs,
        ]
        return "\n".join(part for part in parts if part).strip()

    @staticmethod
    def preferred_summary_source(observation: CommandObservation) -> str:
        """选择最适合给最终回复器看的摘要来源。"""

        if observation.context_summary:
            return observation.context_summary
        if observation.context_outputs:
            return "\n".join(observation.context_outputs)
        if observation.display_summary:
            return observation.display_summary
        if observation.outputs:
            return "\n".join(observation.outputs)
        return observation.message

    @classmethod
    def safe_summary(cls, text: str, *, limit: int | None = None) -> str:
        """生成可面向用户或上下文的短摘要。"""

        normalized = cls.normalize_text(text)
        if not normalized:
            return ""
        max_chars = limit or cls.max_summary_chars
        if len(normalized) <= max_chars:
            return normalized
        return normalized[: max_chars - 12].rstrip() + "…（已截断）"

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """压缩空白和长 URL，避免兜底回复变成 raw dump。"""

        compact = " ".join(str(text or "").split())
        return cls.url_pattern.sub("[链接]", compact)

    @staticmethod
    def resolve_status(observation: CommandObservation, text: str) -> ToolObservationStatus:
        """根据执行状态和内容有无解析统一状态。"""

        if not observation.success:
            return "failed"
        if observation.status in {"skipped", "failed"}:
            return observation.status
        return "succeeded" if text.strip() else "partial"

    @staticmethod
    def merge_next_actions(existing: list[str], additions: list[str]) -> list[str]:
        """保留原顺序合并下一步建议。"""

        merged: list[str] = []
        for action in [*existing, *additions]:
            if action and action not in merged:
                merged.append(action)
        return merged

    @staticmethod
    def extract_query_from_raw(value: Any) -> str:
        """从 MCP 参数或 raw payload 中尽量提取查询文本。"""

        if isinstance(value, dict):
            for key in ("query", "q", "keyword", "keywords", "question", "text", "prompt", "input"):
                item = value.get(key)
                if isinstance(item, str) and item.strip():
                    return item.strip()
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("{"):
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    return ObservationQualityGate.extract_query_from_raw(parsed)
            return text
        return ""

    @staticmethod
    def preview(text: str, limit: int = 120) -> str:
        """日志预览。"""

        compact = " ".join((text or "").split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 3] + "..."


def observation_safe_display(observation: CommandObservation) -> str:
    """返回可直接作为兜底回复片段的安全文本。"""

    gate = ObservationQualityGate()
    if not observation.success:
        text = observation.display_summary or observation.message or observation.context_summary
    elif observation.source_type == "mcp_tool" and observation.context_summary:
        text = observation.context_summary
    else:
        text = observation.display_summary or observation.context_summary
    if not text:
        context_outputs = observation.context_outputs or []
        text = "\n".join(context_outputs)
    if not text:
        text = observation.message
    return gate.safe_summary(text, limit=700)


def build_safe_execution_fallback(observations: list[CommandObservation]) -> str:
    """在最终回复器失败时生成中文、短、非 raw 的兜底说明。"""

    if not observations:
        return "这次没有拿到可用于回答的工具结果，我先不编造结论。你可以稍后让我重新尝试。"

    answerable = [
        observation
        for observation in observations
        if observation.success
        and observation.relevance in {"high", "medium", "unknown"}
        and observation.answer_quality not in {"insufficient", "failed"}
    ]
    summaries = [observation_safe_display(observation) for observation in answerable]
    summaries = [summary for summary in summaries if summary]
    if summaries:
        return "\n".join(summaries[-3:])

    low_relevance = [observation for observation in observations if observation.relevance == "low"]
    if low_relevance:
        tool_names = [
            "外部检索工具" if observation.source_type == "mcp_tool" else observation.tool_name or observation.command
            for observation in low_relevance
        ]
        tools = "、".join(dict.fromkeys(tool_names))
        return f"我调用了 {tools}，但返回结果和你的问题不匹配，所以不能可靠回答。你可以换个更明确的范围，或让我重新检索一次。"

    failed = [observation for observation in observations if not observation.success]
    if failed:
        summary = observation_safe_display(failed[-1])
        return summary or "工具调用失败了，我没有拿到可靠结果。你可以稍后让我重新尝试。"

    return "工具已返回结果，但我没能可靠整理成最终答案。你可以让我重新总结一次。"
