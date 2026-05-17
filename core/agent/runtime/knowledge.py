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

from .prompt_selection import score_prompt_relevance

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
CHAT_QUERY_WORDS = (
    "刚才",
    "之前",
    "最近",
    "聊天",
    "群聊",
    "记录",
    "说过",
    "谁说",
    "回顾",
    "总结群",
)
FILE_QUERY_WORDS = (
    "文件",
    "文档",
    "目录",
    "资料",
    "文件夹",
    "上传",
    "笔记",
    "内容",
    "搜索",
    "检索",
)
QUERY_STOP_PHRASES = (
    "帮我",
    "请",
    "一下",
    "查一下",
    "查",
    "查询",
    "检索",
    "搜索",
    "找一下",
    "看看",
    "刚才",
    "之前",
    "最近",
    "聊天记录",
    "聊天",
    "群聊记录",
    "群聊",
    "记录",
    "文件夹",
    "文件",
    "文档",
    "目录",
    "资料",
    "里面",
    "里",
    "内容",
    "关于",
    "有关",
    "的",
    "什么",
    "哪些",
    "谁说过",
    "说过",
    "回顾",
    "总结",
)


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

    KEYWORD_HINTS = {
        "document-to-image": ("文档", "文件", "pdf", "ppt", "word", "预览", "转图片", "转成图片"),
        "image-generation": ("生成图片", "画图", "海报", "插画", "配图", "风格图", "图片生成"),
        "markdown-to-image": ("markdown", "md", "渲染", "长文", "长回复", "截图", "转图片"),
        "ocr": ("文字", "识别", "提取文字", "图片文字", "验证码", "截图文字", "读图"),
        "qr-code": ("二维码", "扫码", "扫码识别", "生成二维码", "解码二维码"),
    }

    def summaries(self) -> list[dict[str, str]]:
        """返回排序后的 Skill 摘要列表。"""

        return sorted(skill_registry.summaries(), key=lambda item: item["name"])

    def select_summaries(
        self,
        *,
        query: str | None = None,
        limit: int | None = None,
        skill_names: Iterable[str] | None = None,
    ) -> list[dict[str, str]]:
        """按显式技能名或自然语言查询挑选最相关的 Skill 子集。"""

        summaries = self.summaries()
        if skill_names:
            selected = self.select_named_summaries(summaries, skill_names)
            if selected:
                return selected[:limit] if limit is not None else selected

        selected = summaries
        if query:
            selected = self.select_relevant_summaries(summaries, query, limit=limit)

        if limit is not None:
            selected = selected[:limit]
        return selected

    def to_prompt(
        self,
        *,
        query: str | None = None,
        limit: int | None = None,
        skill_names: Iterable[str] | None = None,
    ) -> str:
        """渲染完整或裁剪后的 Skill 摘要，供路由器和 Planner 选择能力。"""

        summaries = self.select_summaries(query=query, limit=limit, skill_names=skill_names)
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

    @staticmethod
    def select_relevant_summaries(
        summaries: list[dict[str, str]],
        query: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, str]]:
        """按自然语言问题挑选最相关的 Skill 摘要。"""

        scored: list[tuple[int, int, dict[str, str]]] = []
        for index, summary in enumerate(summaries):
            score = score_prompt_relevance(
                query,
                names=(summary["name"],),
                texts=(
                    summary["description"],
                    *SkillCatalog.KEYWORD_HINTS.get(summary["name"], ()),
                ),
            )
            if score > 0:
                scored.append((score, index, summary))

        scored.sort(key=lambda item: (-item[0], item[1]))
        selected = [summary for _, _, summary in scored]
        if limit is None or len(selected) >= limit:
            return selected

        seen = {summary["name"] for summary in selected}
        for summary in summaries:
            if summary["name"] in seen:
                continue
            selected.append(summary)
            seen.add(summary["name"])
            if len(selected) >= limit:
                break
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

    async def retrieve(self, query: str, context: RuntimeContext | None) -> str | None:
        """根据用户问题和运行时上下文检索本地知识。"""

        if context is None:
            return None

        sections: list[str] = []
        search_query = extract_search_query(query)
        if should_search_chat_history(query):
            chat_context = await self.retrieve_chat_history(search_query, context)
            if chat_context:
                sections.append(chat_context)

        if should_search_files(query):
            file_context = await self.retrieve_files(search_query, context)
            if file_context:
                sections.append(file_context)

        if not sections:
            return None
        return "\n\n".join(sections)

    async def retrieve_chat_history(self, query: str, context: RuntimeContext) -> str | None:
        """检索用户聊天流和已绑定系统群的采集消息。"""

        sections: list[str] = []
        if context.user_id is not None:
            user_context = await self.retrieve_user_chat_rag(query, context)
            if user_context:
                sections.append(user_context)
            else:
                records = await self.chat_store.search_user_chat_messages(
                    context.user_id,
                    query,
                    limit=8,
                    search_window=120,
                    exclude_message_id=context.message_id,
                )
                if records:
                    sections.append(format_chat_records("用户人机聊天记录检索", query, records))

        if context.is_group:
            group_id = await self.resolve_system_group_id(context)
            if group_id is not None:
                group_context = await self.retrieve_group_chat_rag(group_id, query, context)
                if group_context:
                    sections.append(group_context)
                else:
                    records = await self.chat_store.search_group_messages(
                        group_id,
                        query,
                        limit=8,
                        search_window=160,
                        exclude_message_id=context.message_id,
                    )
                    if records:
                        sections.append(format_chat_records("系统群近期消息检索", query, records))

        return "\n\n".join(sections) if sections else None

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

    async def retrieve_files(self, query: str, context: RuntimeContext) -> str | None:
        """检索当前用户或群组隔离文件空间。"""

        if context.is_group:
            group_id = await self.resolve_system_group_id(context)
            if group_id is None:
                return None
            space = self.manager.group_space(group_id)
            title = "群文件空间检索"
        elif context.user_id is not None:
            space = self.manager.user_space(context.user_id)
            title = "用户文件空间检索"
        else:
            return None

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


def should_search_chat_history(text: str) -> bool:
    """判断用户是否在询问聊天记录或近期对话。"""

    normalized = normalize_query_text(text)
    return any(word in normalized for word in CHAT_QUERY_WORDS)


def should_search_files(text: str) -> bool:
    """判断用户是否在询问本地文件空间。"""

    normalized = normalize_query_text(text)
    return any(word in normalized for word in FILE_QUERY_WORDS)


def extract_search_query(text: str) -> str:
    """从自然语言问题中提取基础检索关键词。"""

    query = normalize_query_text(text)
    for phrase in QUERY_STOP_PHRASES:
        query = query.replace(phrase, " ")
    query = re.sub(r"\s+", " ", query).strip()
    return query


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
