from __future__ import annotations

import re
import asyncio
from pathlib import Path
from dataclasses import dataclass
from collections.abc import Iterable

from nonebot import logger
from core.skills import skill_registry
from src.features.chat_context.resolvers import resolve_bound_group_id

from utils.session import BaseSession
from core.storage import (
    FileSpace,
    StorageManager,
    LocalRagService,
    ChatHistoryStore,
    MessageOwnerKind,
    LocalRagSearchResult,
    storage_manager,
    chat_history_store,
)

from .schema import KnowledgeSourceRequest, KnowledgeSourceObservation
TEXT_FILE_SUFFIXES = {
    ".cfg",
    ".csv",
    ".ini",
    ".json",
    ".log",
    ".md",
    ".py",
    ".text",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


@dataclass(slots=True)
class RuntimeContext:
    """描述 AutoGPT 本轮可用于检索本地上下文的运行时信息。"""

    user_id: int | None = None
    group_id: str | None = None
    platform: str = ""
    platform_name: str = ""
    channel_id: str | None = None
    guild_id: str | None = None
    message_id: str | None = None

    @property
    def is_group(self) -> bool:
        """判断当前上下文是否来自群聊或频道。"""

        return self.channel_id is not None


class SkillCatalog:
    """把项目内 Skill 注册表转换为 Runtime 可读能力目录。"""

    def summaries(self) -> list[dict[str, str]]:
        """返回排序后的 Skill 摘要列表。"""

        return sorted(skill_registry.summaries(), key=lambda item: item["name"])

    def select_summaries(
        self,
        *,
        limit: int | None = None,
        skill_names: Iterable[str] | None = None,
    ) -> list[dict[str, str]]:
        """按显式技能名挑选 Skill 子集，否则返回完整 Skill 目录。"""

        summaries = self.summaries()
        if skill_names:
            selected = self.select_named_summaries(summaries, skill_names)
            if selected:
                return selected[:limit] if limit is not None else selected

        selected = summaries
        if limit is not None:
            selected = selected[:limit]
        return selected

    def to_prompt(
        self,
        *,
        limit: int | None = None,
        skill_names: Iterable[str] | None = None,
    ) -> str:
        """渲染完整或裁剪后的 Skill 摘要，供路由器和 Planner 选择能力。"""

        summaries = self.select_summaries(limit=limit, skill_names=skill_names)
        if not summaries:
            return "暂无可用 Skill。"
        return "\n".join(f"- {item['name']}: {item['description']}" for item in summaries)

    @staticmethod
    def select_named_summaries(
        summaries: list[dict[str, str]],
        skill_names: Iterable[str],
    ) -> list[dict[str, str]]:
        """按显式技能名称挑选 Skill 摘要。"""

        summary_index = {summary["name"]: summary for summary in summaries}
        selected: list[dict[str, str]] = []
        seen: set[str] = set()
        for skill_name in skill_names:
            summary = summary_index.get(skill_name)
            if summary is None or skill_name in seen:
                continue
            selected.append(summary)
            seen.add(skill_name)
        return selected

class LocalKnowledgeRetriever:
    """按需检索用户聊天记录、群聊采集消息和隔离文件空间。"""

    def __init__(
        self,
        *,
        manager: StorageManager | None = None,
        chat_store: ChatHistoryStore | None = None,
        rag_service: LocalRagService | None = None,
    ) -> None:
        """初始化本地知识检索器。"""

        self.manager = manager or storage_manager
        self.chat_store = chat_store or chat_history_store
        self.rag_service = rag_service or LocalRagService(manager=self.manager, chat_store=self.chat_store)

    async def retrieve_sources(
        self,
        requests: Iterable[KnowledgeSourceRequest],
        context: RuntimeContext | None,
    ) -> str | None:
        """按模型选择的受控知识来源检索，并返回结构化 observation 文本。"""

        observations: list[KnowledgeSourceObservation] = []
        for request in requests:
            if request.source == "external_rag":
                continue
            observations.append(await self.retrieve_source(request, context))

        if not observations:
            return None
        return self.format_observations(observations)

    async def retrieve_source(
        self,
        request: KnowledgeSourceRequest,
        context: RuntimeContext | None,
    ) -> KnowledgeSourceObservation:
        """检索单个本地知识来源，所有权限和范围在代码层强制校验。"""

        query = extract_search_query(request.query)
        if not query:
            query = extract_search_query(request.reason)

        if context is None:
            return self.skipped_observation(request, query, "当前没有可用运行时上下文，无法读取本地知识。")

        unavailable_reason = self.source_unavailable_reason(request.source, context)
        if unavailable_reason:
            return self.skipped_observation(request, query, unavailable_reason)
        if request.source in {"group_chat_history", "group_file_space"}:
            group_id = await self.resolve_system_group_id(context)
            if group_id is None:
                return self.skipped_observation(
                    request,
                    query,
                    "当前群聊未绑定系统群或无法解析系统群 ID，已跳过群知识源检索。",
                )

        try:
            content = await self.retrieve_allowed_source(request.source, query, context)
        except Exception as error:
            logger.warning(f"AutoGPT local knowledge source `{request.source}` failed: {error}")
            return KnowledgeSourceObservation(
                source=request.source,
                query=query,
                status="error",
                summary=f"检索 {request.source} 时发生错误：{error}",
                confidence="none",
                required=request.required,
            )

        if content is None:
            return KnowledgeSourceObservation(
                source=request.source,
                query=query,
                status="miss",
                summary="未检索到相关内容。",
                confidence="none",
                required=request.required,
            )

        return KnowledgeSourceObservation(
            source=request.source,
            query=query,
            status="hit",
            summary=content,
            confidence="medium",
            items_count=estimate_context_items(content),
            required=request.required,
        )

    @staticmethod
    def source_unavailable_reason(source: str, context: RuntimeContext) -> str:
        """返回当前上下文无法访问某知识源的原因，空字符串表示可尝试检索。"""

        if source in {"user_chat_history", "user_file_space"} and context.user_id is None:
            return "当前没有可用用户 ID，已跳过用户私有知识源检索。"
        if source in {"group_chat_history", "group_file_space"} and not context.is_group:
            return "当前不是群聊或频道上下文，已跳过群知识源检索。"
        return ""

    async def retrieve_allowed_source(
        self,
        source: str,
        query: str,
        context: RuntimeContext,
    ) -> str | None:
        """根据受控 source 调用对应检索实现，不让模型直接决定存储范围。"""

        if source == "user_chat_history":
            if context.user_id is None:
                return None
            return await self.retrieve_user_chat_history(query, context)
        if source == "group_chat_history":
            if not context.is_group:
                return None
            return await self.retrieve_group_chat_history(query, context)
        if source == "user_file_space":
            if context.user_id is None:
                return None
            return await self.retrieve_user_files(query, context)
        if source == "group_file_space":
            if not context.is_group:
                return None
            return await self.retrieve_group_files(query, context)
        return None

    @staticmethod
    def skipped_observation(
        request: KnowledgeSourceRequest,
        query: str,
        summary: str,
    ) -> KnowledgeSourceObservation:
        """构造因权限或上下文不足而跳过的检索观察。"""

        return KnowledgeSourceObservation(
            source=request.source,
            query=query,
            status="skipped",
            summary=summary,
            confidence="none",
            required=request.required,
        )

    @staticmethod
    def format_observations(observations: Iterable[KnowledgeSourceObservation]) -> str:
        """把结构化检索 observation 渲染成可进入 Planner 的紧凑上下文。"""

        lines = ["# 本地知识源检索观察"]
        for observation in observations:
            lines.extend(
                [
                    f"## {observation.source}",
                    f"- query: {observation.query or '未提供'}",
                    f"- status: {observation.status}",
                    f"- required: {str(observation.required).lower()}",
                    f"- confidence: {observation.confidence}",
                    f"- items_count: {observation.items_count}",
                    observation.summary.strip() or "未检索到相关内容。",
                ]
            )
        return "\n".join(lines)

    async def retrieve_user_chat_history(self, query: str, context: RuntimeContext) -> str | None:
        """检索当前用户私聊历史，禁止读取其它用户记录。"""

        if context.user_id is None:
            return None
        user_context = await self.retrieve_user_chat_rag(query, context)
        if user_context:
            return user_context
        records = await self.chat_store.search_user_chat_messages(
            context.user_id,
            query,
            limit=8,
            search_window=120,
            exclude_message_id=context.message_id,
        )
        if not records:
            return None
        return format_chat_records("用户人机聊天记录检索", query, records)

    async def retrieve_group_chat_history(self, query: str, context: RuntimeContext) -> str | None:
        """检索当前绑定系统群的群聊历史，不直接信任平台 channel id。"""

        group_id = await self.resolve_system_group_id(context)
        if group_id is None:
            return None
        group_context = await self.retrieve_group_chat_rag(group_id, query, context)
        if group_context:
            return group_context
        records = await self.chat_store.search_group_messages(
            group_id,
            query,
            limit=8,
            search_window=160,
            exclude_message_id=context.message_id,
        )
        if not records:
            return None
        return format_chat_records("系统群近期消息检索", query, records)

    async def retrieve_user_chat_rag(self, query: str, context: RuntimeContext) -> str | None:
        """通过本地 RAG 索引检索用户人机聊天记录。"""

        if context.user_id is None:
            return None
        try:
            await self.rag_service.refresh_user_chat(context.user_id)
            results = await self.rag_service.search_owner(
                MessageOwnerKind.user,
                context.user_id,
                query,
                source_types={"chat"},
                limit=10,
            )
            results = filter_current_message(results, context.message_id)
            return self.rag_service.build_context("用户人机聊天记录检索（本地 RAG）", query, results)
        except Exception as error:
            logger.warning(f"AutoGPT local RAG failed to retrieve user chat: {error}")
            return None

    async def retrieve_group_chat_rag(
        self,
        group_id: str,
        query: str,
        context: RuntimeContext,
    ) -> str | None:
        """通过本地 RAG 索引检索系统群采集消息。"""

        try:
            await self.rag_service.refresh_group_collect(group_id)
            results = await self.rag_service.search_owner(
                MessageOwnerKind.group,
                group_id,
                query,
                source_types={"chat"},
                limit=10,
            )
            results = filter_current_message(results, context.message_id)
            return self.rag_service.build_context("系统群近期消息检索（本地 RAG）", query, results)
        except Exception as error:
            logger.warning(f"AutoGPT local RAG failed to retrieve group chat: {error}")
            return None

    async def retrieve_user_files(self, query: str, context: RuntimeContext) -> str | None:
        """检索当前用户隔离文件空间。"""

        if context.user_id is None:
            return None
        return await self.retrieve_file_space(query, self.manager.user_space(context.user_id), "用户文件空间检索")

    async def retrieve_group_files(self, query: str, context: RuntimeContext) -> str | None:
        """检索当前绑定系统群文件空间，不直接使用平台 channel id。"""

        group_id = await self.resolve_system_group_id(context)
        if group_id is None:
            return None
        return await self.retrieve_file_space(query, self.manager.group_space(group_id), "群文件空间检索")

    async def retrieve_file_space(self, query: str, space: FileSpace, title: str) -> str | None:
        """检索指定隔离文件空间。"""

        rag_context = await self.retrieve_file_rag(query, space, title)
        if rag_context:
            return rag_context

        entries = await asyncio.to_thread(search_file_space_sync, space, query)
        if not entries:
            return None
        lines = [f"## {title}", f"查询: {query or '最近文件'}"]
        lines.extend(entries)
        return "\n".join(lines)

    async def retrieve_file_rag(self, query: str, space: FileSpace, title: str) -> str | None:
        """通过本地 RAG 索引检索文件空间文本内容。"""

        try:
            await self.rag_service.refresh_file_space(space)
            results = await self.rag_service.search_owner(
                MessageOwnerKind(space.kind),
                space.owner_id,
                query,
                source_types={"file"},
                limit=10,
            )
            return self.rag_service.build_context(f"{title}（本地 RAG）", query, results)
        except Exception as error:
            logger.warning(f"AutoGPT local RAG failed to retrieve file space: {error}")
            return None

    @staticmethod
    async def resolve_system_group_id(context: RuntimeContext) -> str | None:
        """把平台群聊上下文解析为系统内 Group ID。"""

        if context.group_id:
            return str(context.group_id)
        if not context.platform or not context.channel_id:
            return None
        try:
            group_id = await resolve_bound_group_id(
                BaseSession(
                    user_id=str(context.user_id or ""),
                    platform=context.platform,
                    platform_name=context.platform_name,
                    channel_id=context.channel_id,
                    guild_id=context.guild_id,
                )
            )
        except Exception as error:
            logger.warning(f"AutoGPT local knowledge failed to resolve group id: {error}")
            return None
        return str(group_id) if group_id is not None else None


def extract_search_query(text: str) -> str:
    """清理路由器生成的检索问题，保留语义由 AI 路由器负责。"""

    return normalize_query_text(text)


def normalize_query_text(text: str | None) -> str:
    """清理检索问题中的空白和常见标点。"""

    text = str(text or "")
    text = re.sub(r"[，。！？!?；;：:、,.()\[\]{}<>《》\"'“”‘’`~～]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def format_chat_records(title: str, query: str, records) -> str:
    """把聊天记录渲染成适合进入 LLM 上下文的文本。"""

    lines = [f"## {title}", f"查询: {query or '最近消息'}"]
    for record in records:
        text = record.display_text
        if len(text) > 160:
            text = text[:157] + "..."
        lines.append(f"- [{record.created_at.strftime('%Y-%m-%d %H:%M')}] {record.user_name}: {text}")
    return "\n".join(lines)


def filter_current_message(
    results: list[LocalRagSearchResult],
    message_id: str | None,
) -> list[LocalRagSearchResult]:
    """避免把用户当前这条提问本身当成历史记忆召回。"""

    if not message_id:
        return results
    return [result for result in results if str(result.metadata.get("message_id") or "") != str(message_id)]


def estimate_context_items(context: str) -> int:
    """粗略估算检索上下文中的命中条数，用于 observation 可读性。"""

    return sum(1 for line in context.splitlines() if line.startswith("- ") or line.startswith("### "))


def search_file_space_sync(space: FileSpace, query: str, *, limit: int = 8, max_scan: int = 160) -> list[str]:
    """同步检索文件空间中的文件名和小型文本文件内容。"""

    terms = [term.lower() for term in query.split() if term.strip()]
    selected: list[str] = []
    scanned = 0
    for path in sorted(space.home_dir.rglob("*"), key=lambda item: item.relative_to(space.home_dir).as_posix()):
        if scanned >= max_scan or len(selected) >= limit:
            break
        if any(part.startswith(".") for part in path.relative_to(space.home_dir).parts):
            continue
        scanned += 1
        line = render_file_match(space, path, terms)
        if line:
            selected.append(line)
    return selected


def render_file_match(space: FileSpace, path: Path, terms: list[str]) -> str | None:
    """渲染单个文件或目录的命中结果。"""

    relative = path.relative_to(space.home_dir)
    display = "~" if not relative.parts else "~/" + relative.as_posix()
    name_text = " ".join(relative.parts).lower()
    text = ""
    if path.is_file() and path.suffix.lower() in TEXT_FILE_SUFFIXES and path.stat().st_size <= 128 * 1024:
        try:
            text = path.read_text("utf-8", errors="ignore")
        except OSError:
            text = ""

    haystack = f"{name_text} {text}".lower()
    if terms and not all(term in haystack for term in terms):
        return None
    if path.is_dir():
        return f"- {display}/"

    suffix = ""
    if text:
        snippet = build_text_snippet(text, terms)
        if snippet:
            suffix = f" | 片段: {snippet}"
    return f"- {display}{suffix}"


def build_text_snippet(text: str, terms: list[str]) -> str:
    """从文本中提取短片段。"""

    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return ""
    start = 0
    for term in terms:
        index = compact.lower().find(term)
        if index >= 0:
            start = max(index - 40, 0)
            break
    snippet = compact[start : start + 180]
    if start > 0:
        snippet = "..." + snippet
    if start + 180 < len(compact):
        snippet += "..."
    return snippet
