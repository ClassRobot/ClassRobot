from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from utils.helper import Helpers
from core.llm.message import Content
from utils.storage import ChatHistorySummary

from .state import LocalChatStatisticsQuery
from ..harness.context import ContextHarness
from ..schema import Param, AutoTask, AutoTaskList


@dataclass(slots=True)
class LocalContextQueryResolver:
    """解析不需要模型猜测的本地确定性问题。"""

    helpers: Helpers
    context: ContextHarness

    async def resolve_local_chat_statistics_query(self, contents: list[Content]) -> AutoTaskList | None:
        """优先回答“聊了多少条消息”这类需要精确统计的问题。"""

        if self.context.runtime_context is None:
            return None

        normalized = self.normalized_text_query(contents)
        query = self.parse_local_chat_statistics_query(normalized)
        if query is None:
            return None

        if query.scope == "group":
            return await self.resolve_local_group_chat_statistics(query)
        return await self.resolve_local_user_chat_statistics(query)

    async def resolve_local_user_chat_statistics(self, query: LocalChatStatisticsQuery) -> AutoTaskList:
        """统计当前用户与机器人的聊天条数。"""

        if self.context.runtime_context is None or self.context.runtime_context.user_id is None:
            return AutoTaskList(reply="当前会话还没有可用的用户身份，暂时没法统计我们的聊天记录。")

        summary = await self.context.chat_store.summarize_user_chat_messages(
            self.context.runtime_context.user_id,
            exclude_message_id=self.context.runtime_context.message_id,
            start_at=query.start_at,
            end_at=query.end_at,
        )
        return AutoTaskList(reply=self.format_user_chat_statistics_reply(query, summary))

    async def resolve_local_group_chat_statistics(self, query: LocalChatStatisticsQuery) -> AutoTaskList:
        """统计当前系统群组的群聊消息条数。"""

        if self.context.runtime_context is None or not self.context.runtime_context.is_group:
            return AutoTaskList(reply="这个统计需要在对应的群里问我，这样我才能只读取当前群的聊天记录。")

        group_id = await self.context.local_knowledge_retriever.resolve_system_group_id(self.context.runtime_context)
        if group_id is None:
            return AutoTaskList(reply="当前群还没有绑定到系统群，暂时没法统计这里的群聊记录。")

        summary = await self.context.chat_store.summarize_group_messages(
            group_id,
            exclude_message_id=self.context.runtime_context.message_id,
            start_at=query.start_at,
            end_at=query.end_at,
        )
        return AutoTaskList(reply=self.format_group_chat_statistics_reply(query, summary))

    def resolve_local_context_query(self, contents: list[Content]) -> AutoTaskList | None:
        """把确定性的本地上下文问题路由到已有项目命令。"""

        if not self.is_self_identity_query(contents):
            if class_task := self.resolve_class_context_query(contents):
                return class_task
            if schedule_task := self.resolve_schedule_context_query(contents):
                return schedule_task
            return None
        if self.helpers.get_helper("我的信息") is None:
            return None
        return AutoTaskList(tasks=[AutoTask(command="我的信息", params=[])], need_confirm=False)

    def resolve_class_context_query(self, contents: list[Content]) -> AutoTaskList | None:
        """把高频班级状态问题路由到班级或用户信息查询命令。"""

        normalized = self.normalized_text_query(contents)
        if not normalized or self.contains_mutating_words(normalized):
            return None

        class_words = ("班级", "班", "班群")
        managed_words = ("创建", "管理", "负责", "拥有", "有创建", "有管理", "我的班级", "班级列表")
        membership_words = ("在哪个", "哪个班", "所在", "属于", "加入", "当前班级", "我的班")
        query_words = (
            "吗",
            "么",
            "是否",
            "是不是",
            "什么",
            "哪个",
            "哪些",
            "查看",
            "查询",
            "查一下",
            "告诉我",
            "当前",
            "我的",
            "列表",
            "有",
        )

        if not any(word in normalized for word in class_words):
            return None
        if not any(word in normalized for word in query_words):
            return None

        if any(word in normalized for word in managed_words) and self.helpers.get_helper("查询班级") is not None:
            return AutoTaskList(tasks=[AutoTask(command="查询班级", params=[])], need_confirm=False)
        if any(word in normalized for word in membership_words) and self.helpers.get_helper("我的信息") is not None:
            return AutoTaskList(tasks=[AutoTask(command="我的信息", params=[])], need_confirm=False)
        return None

    def resolve_schedule_context_query(self, contents: list[Content]) -> AutoTaskList | None:
        """把本人课表查询路由到查询课表命令，并尽量补上常见日期偏移。"""

        normalized = self.normalized_text_query(contents)
        if not normalized or self.contains_mutating_words(normalized):
            return None
        if self.helpers.get_helper("查询课表") is None:
            return None

        schedule_words = ("课表", "课程表", "课程", "上课", "有课", "什么课")
        query_words = (
            "吗",
            "么",
            "什么",
            "哪些",
            "查看",
            "查询",
            "查一下",
            "告诉我",
            "我的",
            "今天",
            "明天",
            "后天",
            "昨天",
        )
        if not any(word in normalized for word in schedule_words):
            return None
        if not any(word in normalized for word in query_words):
            return None

        params = []
        if "后天" in normalized:
            params.append(Param(type="text", value="2"))
        elif "明天" in normalized:
            params.append(Param(type="text", value="1"))
        elif "昨天" in normalized:
            params.append(Param(type="text", value="-1"))
        return AutoTaskList(tasks=[AutoTask(command="查询课表", params=params)], need_confirm=False)

    @staticmethod
    def is_self_identity_query(contents: list[Content]) -> bool:
        """判断用户是否在询问自己的身份、角色或管理员状态。"""

        normalized = LocalContextQueryResolver.normalized_text_query(contents)
        if not normalized:
            return False

        self_words = ("我", "我的", "自己", "本人")
        identity_words = ("身份", "角色", "权限", "管理员", "学生", "教师", "老师", "班干部")
        query_words = ("吗", "么", "是否", "是不是", "是", "什么", "哪些", "查看", "查询", "查一下", "告诉我", "当前")

        if LocalContextQueryResolver.contains_mutating_words(normalized):
            return False
        return (
            any(word in normalized for word in self_words)
            and any(word in normalized for word in identity_words)
            and any(word in normalized for word in query_words)
        )

    @staticmethod
    def normalized_text_query(contents: list[Content]) -> str:
        """提取纯文本消息并去掉空白，供本地确定性路由使用。"""

        if any(content.type != "text" for content in contents):
            return ""
        text = "".join(content.value for content in contents if content.type == "text").strip()
        return "".join(text.split())

    @classmethod
    def parse_local_chat_statistics_query(cls, text: str) -> LocalChatStatisticsQuery | None:
        """解析是否命中当前用户或当前群的聊天统计问题。"""

        if not text or cls.contains_mutating_words(text):
            return None

        conversation_words = ("聊", "聊天", "消息", "记录", "对话", "群聊")
        count_words = ("几条", "多少条", "多少", "几次", "多少次")
        blocked_words = (
            "谁",
            "别人",
            "别人的",
            "其他人",
            "其它人",
            "其他群",
            "其它群",
            "哪个群",
            "哪位",
            "他和你",
            "她和你",
            "他们",
        )
        if not any(word in text for word in conversation_words):
            return None
        if not any(word in text for word in count_words):
            return None
        if any(word in text for word in blocked_words):
            return None

        time_label, start_at, end_at = cls.resolve_chat_statistics_window(text)
        group_words = ("这个群", "当前群", "本群", "这个班群", "当前班群", "班群", "群里", "群聊")
        self_words = (
            "我们",
            "咱们",
            "我和你",
            "我跟你",
            "我与你",
            "我和机器人",
            "我跟机器人",
            "我与机器人",
            "我和助手",
            "我跟助手",
            "我与助手",
            "我和AI",
            "我跟AI",
            "我与AI",
        )
        if any(word in text for word in group_words):
            return LocalChatStatisticsQuery(scope="group", time_label=time_label, start_at=start_at, end_at=end_at)
        if any(word in text for word in self_words):
            return LocalChatStatisticsQuery(scope="user", time_label=time_label, start_at=start_at, end_at=end_at)
        return None

    @staticmethod
    def resolve_chat_statistics_window(text: str) -> tuple[str, datetime | None, datetime | None]:
        """从问题中提取受控的时间范围。"""

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if "昨天" in text:
            return "昨天", today - timedelta(days=1), today
        if "今天" in text:
            return "今天", today, today + timedelta(days=1)
        if "本周" in text or "这周" in text or "本星期" in text or "这星期" in text:
            start_at = today - timedelta(days=today.weekday())
            return "本周", start_at, start_at + timedelta(days=7)
        return "当前保存的", None, None

    @staticmethod
    def format_user_chat_statistics_reply(query: LocalChatStatisticsQuery, summary: ChatHistorySummary) -> str:
        """渲染当前用户与机器人的聊天统计回复。"""

        prefix = (
            "按当前保存的聊天记录统计" if query.time_label == "当前保存的" else f"按{query.time_label}的聊天记录统计"
        )
        if summary.total <= 0:
            return f"{prefix}，我们还没有可用的聊天记录。"
        return f"{prefix}，我们一共聊了 {summary.total} 条消息。其中你发了 {summary.inbound} 条，我回复了 {summary.outbound} 条。"

    @staticmethod
    def format_group_chat_statistics_reply(query: LocalChatStatisticsQuery, summary: ChatHistorySummary) -> str:
        """渲染当前系统群的聊天统计回复。"""

        prefix = (
            "按当前保存的群聊记录统计" if query.time_label == "当前保存的" else f"按{query.time_label}的群聊记录统计"
        )
        if summary.total <= 0:
            return f"{prefix}，这个群还没有可用的聊天记录。"

        reply = f"{prefix}，这个群一共聊了 {summary.total} 条消息。"
        if summary.distinct_user_count > 0:
            reply += f" 共有 {summary.distinct_user_count} 位成员发过言。"
        return reply

    @staticmethod
    def contains_mutating_words(text: str) -> bool:
        """识别会修改状态的词，避免本地查询规则误拦截写操作。"""

        action_words = (
            "成为",
            "设置",
            "添加",
            "修改",
            "删除",
            "注销",
            "绑定",
            "申请",
            "创建一个",
            "新建",
            "导入",
            "上传",
        )
        return any(word in text for word in action_words)
