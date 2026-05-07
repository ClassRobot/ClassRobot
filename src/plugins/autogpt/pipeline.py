from time import perf_counter
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from typing import Literal
from dataclasses import dataclass, field

from nonebot import logger
from nonebot_plugin_alconna import UniMessage

from utils.helper import Helpers
from utils.storage import ChatHistoryStore, ChatHistorySummary, chat_history_store
from utils.template.prompts import Prompt
from utils.llm import LLMTaskType, client_create
from utils.llm.util import json_loads, uni_message_to_contents
from utils.llm.message import Content, Context, LLMRole, Messages
from utils.llm.agents.tools import RagAgent, ExtractAgent, SummaryAgent, AutoTaskAgent

from .harness import AutoGPTHarness, ProgressReporter, ProgressStage, ProgressFeedbackHarness
from .workflow import build_turn_result
from .knowledge import AgentRuntimeContext, AgentLocalKnowledgeRetriever
from .schema import Param, AutoTask, AgentPlan, ChatMessage, IntentRoute, AutoTaskList, AgentTurnResult


@dataclass(slots=True)
class LocalChatStatisticsQuery:
    """描述一次可直接命中的聊天统计请求。"""

    scope: Literal["user", "group"]
    time_label: str = "当前保存的"
    start_at: datetime | None = None
    end_at: datetime | None = None


@dataclass(slots=True)
class PipelineState:
    """承载一次消息处理流程中的中间状态。"""

    trace_id: str = ""
    user_content: list[Content] = field(default_factory=list)
    intent_route: IntentRoute | None = None
    agent_plan: AgentPlan | None = None
    extracted_context: Context | None = None
    local_knowledge: str | None = None
    retrieved_knowledge: str | None = None
    auto_tasks: AutoTaskList | None = None


class WorkflowNode(ABC):
    """定义工作流节点的统一接口。"""

    @abstractmethod
    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        """执行当前节点逻辑。"""


class SummaryHistoryNode(WorkflowNode):
    """在会话过长时先压缩历史消息。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        pipeline.messages = await SummaryAgent().execute(pipeline.messages)


class NormalizeUserInputNode(WorkflowNode):
    """把平台原始消息转换为统一内容结构。"""

    def __init__(self, message: str | UniMessage | ChatMessage) -> None:
        self.message = message

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        state.user_content = pipeline.normalize_message(self.message)


class AppendUserMessageNode(WorkflowNode):
    """把当前用户消息写入会话。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        pipeline.messages.user_message(state.user_content)


class LocalContextQueryNode(WorkflowNode):
    """优先处理不需要模型猜测的本地上下文查询。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None:
            return
        auto_tasks = pipeline.resolve_local_context_query(state.user_content)
        if auto_tasks is None:
            return
        state.intent_route = IntentRoute(
            intent="command",
            requires_command=True,
            requires_rag=False,
            need_confirm=False,
            reason="用户正在查询本地账号、班级或课表状态，直接调用项目内查询命令。",
        )
        state.auto_tasks = auto_tasks


class LocalChatStatisticsNode(WorkflowNode):
    """优先处理聊天条数这类需要精确统计的本地问题。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None:
            return
        auto_tasks = await pipeline.resolve_local_chat_statistics_query(state.user_content)
        if auto_tasks is None:
            return
        state.intent_route = IntentRoute(
            intent="knowledge",
            requires_command=False,
            requires_rag=False,
            need_confirm=False,
            reason="用户正在查询当前用户或当前系统群的聊天统计，直接读取本地归档结果。",
        )
        state.auto_tasks = auto_tasks


class IntentRouteNode(WorkflowNode):
    """先判断消息类型，避免所有请求都进入重型规划链路。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None:
            return
        route_messages = Messages()
        route_messages.extend(pipeline.messages.get(LLMRole.system))
        route_messages.system_message(
            await Prompt("intent_route").render(
                {
                    "helpers": pipeline.helpers,
                    "command_tools": pipeline.command_tools,
                    "skill_catalog": pipeline.skill_catalog_prompt,
                    "history": pipeline.serialize_recent_history(),
                }
            )
        )
        # 当本轮消息包含图片时，额外把当前用户消息作为真正的多模态输入交给路由器，
        # 避免模型只能看到一个图片 URL 文本，从而错过视觉理解入口。
        route_messages.user_message(state.user_content)
        multi_modal = pipeline.has_visual_input(state.user_content)
        response = await client_create(
            route_messages,
            multi_modal=multi_modal,
            max_tokens=1024,
            task_type=LLMTaskType.vision if multi_modal else LLMTaskType.plan,
        )
        text = response.choices[0].message.content or "{}"
        try:
            state.intent_route = IntentRoute.parse_obj(json_loads(text))
        except Exception as error:
            logger.exception(f'AutoGPT trace "{state.trace_id}" intent route parse failed: {error}')
            state.intent_route = IntentRoute(
                intent="complex_task",
                requires_command=True,
                reason="意图路由解析失败，降级到自动任务规划。",
            )
        logger.info(
            'AutoGPT trace "{}" routed intent="{}" requires_command={} requires_rag={}'.format(
                state.trace_id,
                state.intent_route.intent,
                state.intent_route.requires_command,
                state.intent_route.requires_rag,
            )
        )
        progress_message = ""
        if not pipeline.should_direct_reply_from_vision(state.intent_route, state.user_content):
            progress_message = pipeline.build_user_progress_message(state.intent_route)
            if not progress_message and multi_modal:
                progress_message = "我先看一下图片或文件内容，请稍等~"
        await pipeline.report_progress(progress_message, stage="route")

        if state.intent_route.intent == "violation":
            state.auto_tasks = AutoTaskList(
                reply=state.intent_route.reply or "用户发送的消息包含违规内容，已被屏蔽！",
                is_violation=True,
            )
        elif (
            not state.intent_route.requires_command
            and not state.intent_route.requires_rag
            and not pipeline.has_visual_input(state.user_content)
            and not pipeline.can_retrieve_local_knowledge(state.user_content)
        ):
            state.auto_tasks = AutoTaskList(
                reply=state.intent_route.reply or "我在，有什么需要我帮你处理的吗？",
                need_confirm=state.intent_route.need_confirm,
            )


class DirectVisionReplyNode(WorkflowNode):
    """对无需命令和检索的简单图片问答直接给出最终回复。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None or state.intent_route is None:
            return
        if not pipeline.should_direct_reply_from_vision(state.intent_route, state.user_content):
            return

        reply_messages = Messages()
        reply_messages.extend(pipeline.messages.get(LLMRole.system))
        reply_messages.system_message(await Prompt("vision_reply").render())
        reply_messages.extend(pipeline.messages.get(LLMRole.user, LLMRole.assistant))

        response = await client_create(
            reply_messages,
            multi_modal=True,
            max_tokens=2048,
            task_type=LLMTaskType.vision,
        )
        reply = (response.choices[0].message.content or "").strip()
        state.auto_tasks = AutoTaskList(
            reply=reply
            or "我看到了这张图片，但还不能可靠判断具体内容，你可以发更清晰一点的图片或补一句你想让我看什么。",
            need_confirm=False,
        )


class RetrieveLocalKnowledgeNode(WorkflowNode):
    """按需检索聊天记录、文件空间和其他本地上下文。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None:
            return
        if not pipeline.can_retrieve_local_knowledge(state.user_content):
            return
        await pipeline.report_progress("我正在检索当前可用的聊天记录和文件上下文。", stage="memory")
        query = pipeline.text_query_from_contents(state.user_content)
        state.local_knowledge = await pipeline.local_knowledge_retriever.retrieve(query, pipeline.runtime_context)
        if state.local_knowledge:
            logger.info(f'AutoGPT trace "{state.trace_id}" loaded local knowledge context')


class ExtractContextNode(WorkflowNode):
    """从当前会话中抽取结构化上下文。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None:
            return
        await pipeline.report_progress("我正在提取这轮对话里的目标、约束和关键信息。", stage="extract")
        state.extracted_context = await ExtractAgent().execute(pipeline.messages)


class PlannerNode(WorkflowNode):
    """把上下文转换成显式计划，再交给后续节点执行。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None or state.extracted_context is None:
            return
        await pipeline.report_progress("我正在把目标拆成可执行步骤，并确认需要哪些命令或技能。", stage="plan")

        plan_messages = Messages()
        plan_messages.extend(pipeline.messages.get(LLMRole.system))
        plan_messages.system_message(
            await Prompt("agent_plan").render(
                {
                    "helpers": pipeline.helpers,
                    "command_tools": pipeline.command_tools,
                    "skill_catalog": pipeline.skill_catalog_prompt,
                    "route": state.intent_route.json(ensure_ascii=False) if state.intent_route else "{}",
                    "context": state.extracted_context.single_modal(),
                    "local_knowledge": state.local_knowledge,
                    "history": pipeline.serialize_recent_history(),
                }
            )
        )
        response = await client_create(
            plan_messages,
            multi_modal=False,
            max_tokens=2048,
            task_type=LLMTaskType.plan,
        )
        text = response.choices[0].message.content or "{}"
        try:
            state.agent_plan = AgentPlan.parse_obj(json_loads(text))
        except Exception as error:
            logger.exception(f'AutoGPT trace "{state.trace_id}" planner parse failed: {error}')
            state.agent_plan = AgentPlan(
                goal=state.extracted_context.single_modal(),
                requires_command=bool(state.intent_route and state.intent_route.requires_command),
                requires_rag=bool(state.intent_route and state.intent_route.requires_rag),
                reason="计划解析失败，使用上下文和入口路由降级。",
            )
        logger.info(
            'AutoGPT trace "{}" planned requires_command={} should_execute={} risk_level="{}" candidates={}'.format(
                state.trace_id,
                state.agent_plan.requires_command,
                state.agent_plan.should_execute,
                state.agent_plan.risk_level,
                state.agent_plan.candidate_commands,
            )
        )

        if state.agent_plan.confirmation_question or state.agent_plan.missing_info:
            state.auto_tasks = AutoTaskList(
                reply=state.agent_plan.confirmation_question
                or "还需要补充一些信息后才能继续：" + "、".join(state.agent_plan.missing_info),
                need_confirm=True,
            )


class ExecutionPolicyNode(WorkflowNode):
    """使用代码规则校验 Planner 输出，避免模型直接越权执行。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None or state.agent_plan is None:
            return

        plan = state.agent_plan
        if plan.risk_level == "high" and plan.requires_command:
            state.auto_tasks = AutoTaskList(
                reply=plan.confirmation_question or "这个操作风险较高，请确认是否继续执行。",
                need_confirm=True,
            )
            return

        if plan.requires_command and not plan.should_execute:
            state.auto_tasks = AutoTaskList(
                reply=plan.confirmation_question
                or "我还需要你确认执行条件后才能调用系统命令。"
                + (f" 缺少信息：{'、'.join(plan.missing_info)}" if plan.missing_info else ""),
                need_confirm=True,
            )
            return

        if plan.requires_command and not pipeline.resolve_candidate_commands(plan):
            state.auto_tasks = AutoTaskList(
                reply="我还不能确定要调用哪个项目命令，请再说明一下要执行的具体功能。",
                need_confirm=True,
            )


class RetrieveKnowledgeNode(WorkflowNode):
    """根据抽取上下文获取补充知识。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None or not pipeline.should_retrieve(state.intent_route, state.agent_plan):
            return
        if state.extracted_context is None:
            return
        await pipeline.report_progress("我正在补充相关知识和上下文，用来支撑后续处理。", stage="rag")
        state.retrieved_knowledge = await RagAgent().execute(state.extracted_context)


class PlanTasksNode(WorkflowNode):
    """结合上下文、补充知识和命令清单生成最终规划。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None:
            return
        if state.extracted_context is None:
            return
        state.auto_tasks = await AutoTaskAgent(
            helpers=pipeline.helpers,
            messages=pipeline.messages,
            command_tools_prompt=pipeline.command_tools.to_prompt(),
            skill_catalog_prompt=pipeline.skill_catalog_prompt,
        ).execute(
            state.extracted_context,
            pipeline.combine_knowledge(state.local_knowledge, state.retrieved_knowledge),
            plan=state.agent_plan.json(ensure_ascii=False) if state.agent_plan else None,
        )


class ValidateAutoTasksNode(WorkflowNode):
    """校验 AutoTask 输出，确保任务仍在 Planner 和 Helper 允许范围内。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is None or not state.auto_tasks.tasks:
            return

        allowed_commands = pipeline.resolve_candidate_commands(state.agent_plan)
        valid_tasks = []
        invalid_commands = []
        for task in state.auto_tasks.tasks:
            helper = pipeline.helpers.get_helper(task.command)
            if helper is None:
                invalid_commands.append(task.command)
                continue
            if allowed_commands and helper.command not in allowed_commands:
                invalid_commands.append(task.command)
                continue
            valid_tasks.append(task)

        state.auto_tasks.tasks = valid_tasks
        if invalid_commands and not valid_tasks:
            state.auto_tasks.reply = "计划中的命令不在当前可用能力范围内，请换一种说法或补充更明确的信息。"
            state.auto_tasks.need_confirm = True
        elif invalid_commands:
            state.auto_tasks.reply = (state.auto_tasks.reply or "") + "\n部分命令因不在当前计划或权限范围内，已跳过。"

        state.auto_tasks.reply = pipeline.normalize_auto_task_reply(
            state.intent_route,
            state.agent_plan,
            state.auto_tasks,
        )


class PersistAssistantReplyNode(WorkflowNode):
    """将结构化规划回写到会话历史，便于后续轮次继续引用。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is None:
            return
        pipeline.messages.assistant_message(pipeline.serialize_auto_task_result(state.auto_tasks))


class MessageProcessingPipeline:
    """封装 AI 会话主链路的标准处理流水线。"""

    def __init__(
        self,
        helpers: Helpers | None = None,
        messages: Messages | None = None,
        trace_id: str = "",
        progress_reporter: ProgressReporter | None = None,
        runtime_context: AgentRuntimeContext | None = None,
        local_knowledge_retriever: AgentLocalKnowledgeRetriever | None = None,
        chat_store: ChatHistoryStore | None = None,
        harness: AutoGPTHarness | None = None,
    ) -> None:
        if harness is None:
            if helpers is None or messages is None:
                raise ValueError("MessageProcessingPipeline requires helpers and messages when harness is not provided.")
            harness = AutoGPTHarness.build(
                helpers=helpers,
                messages=messages,
                trace_id=trace_id,
                progress_reporter=progress_reporter,
                runtime_context=runtime_context,
                local_knowledge_retriever=local_knowledge_retriever,
                chat_store=chat_store or chat_history_store,
            )
        self.harness = harness
        self.policy = harness.policy
        self.context = harness.context
        self.observability = harness.observability
        self.helpers = harness.helpers
        self.command_tools = harness.command_tools
        self.skill_catalog_prompt = harness.skill_catalog_prompt
        self.messages = harness.messages
        self.trace_id = harness.trace_id
        self.runtime_context = harness.runtime_context
        self.local_knowledge_retriever = harness.local_knowledge_retriever
        self.chat_store = harness.chat_store

    async def report_progress(self, message: str, stage: ProgressStage = "thinking") -> None:
        """向用户发送少量有价值的处理状态，失败时只记日志不中断主流程。"""

        await self.observability.report_progress(message, stage=stage)

    @staticmethod
    def format_progress_message(message: str, stage: ProgressStage = "thinking") -> str:
        """为思考型进度消息添加统一阶段前缀。"""

        return ProgressFeedbackHarness.format_progress_message(message, stage=stage)

    @staticmethod
    def build_user_progress_message(route: IntentRoute | None) -> str:
        """根据入口路由生成用户能理解的单条状态提示。"""

        if route is None or route.intent in {"chat", "violation"}:
            return ""
        if route.intent == "vision_file":
            return "我会先理解图片或文件内容，再根据你的问题给出可直接使用的结论。"
        if route.requires_rag and route.requires_command:
            return "我会先检索相关上下文，再把能执行的系统命令串起来处理。"
        if route.requires_rag:
            return "我会先检索相关资料，把命中的内容压缩成可用上下文后再回答。"
        if route.requires_command:
            return "我会把你的需求转换成系统内命令，确认参数后调用现有功能返回结果。"
        return ""

    @staticmethod
    def has_visual_input(contents: list[Content]) -> bool:
        """判断当前消息是否包含需要视觉理解的内容。"""

        return any(content.type in {"image", "file"} for content in contents)

    @staticmethod
    def text_query_from_contents(contents: list[Content]) -> str:
        """提取当前用户消息中的文本查询。"""

        return " ".join(content.value for content in contents if content.type == "text").strip()

    @staticmethod
    def should_retrieve_local_knowledge(contents: list[Content]) -> bool:
        """判断是否需要检索聊天记录或文件空间。"""

        from .knowledge import should_search_files, should_search_chat_history

        query = MessageProcessingPipeline.text_query_from_contents(contents)
        return bool(query and (should_search_chat_history(query) or should_search_files(query)))

    def can_retrieve_local_knowledge(self, contents: list[Content]) -> bool:
        """判断当前轮次是否具备本地知识检索条件。"""

        return self.context.can_retrieve_local_knowledge(contents, self.should_retrieve_local_knowledge)

    async def resolve_local_chat_statistics_query(self, contents: list[Content]) -> AutoTaskList | None:
        """优先回答“聊了多少条消息”这类需要精确统计的问题。"""

        if self.runtime_context is None:
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

        normalized = MessageProcessingPipeline.normalized_text_query(contents)
        if not normalized:
            return False

        self_words = ("我", "我的", "自己", "本人")
        identity_words = ("身份", "角色", "权限", "管理员", "学生", "教师", "老师", "班干部")
        query_words = ("吗", "么", "是否", "是不是", "是", "什么", "哪些", "查看", "查询", "查一下", "告诉我", "当前")

        if MessageProcessingPipeline.contains_mutating_words(normalized):
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
            "按当前保存的聊天记录统计"
            if query.time_label == "当前保存的"
            else f"按{query.time_label}的聊天记录统计"
        )
        if summary.total <= 0:
            return f"{prefix}，我们还没有可用的聊天记录。"
        return f"{prefix}，我们一共聊了 {summary.total} 条消息。其中你发了 {summary.inbound} 条，我回复了 {summary.outbound} 条。"

    @staticmethod
    def format_group_chat_statistics_reply(query: LocalChatStatisticsQuery, summary: ChatHistorySummary) -> str:
        """渲染当前系统群的聊天统计回复。"""

        prefix = (
            "按当前保存的群聊记录统计"
            if query.time_label == "当前保存的"
            else f"按{query.time_label}的群聊记录统计"
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

    @staticmethod
    def should_direct_reply_from_vision(route: IntentRoute | None, contents: list[Content]) -> bool:
        """判断当前图片消息是否应走直接视觉回复快路径。"""

        if route is None:
            return False
        if route.requires_command or route.requires_rag or route.need_confirm:
            return False
        if route.intent not in {"chat", "vision_file"}:
            return False
        return any(content.type == "image" for content in contents)

    def normalize_message(self, message: str | UniMessage | ChatMessage) -> list[Content]:
        """将输入消息统一转换为内部内容结构。"""
        if isinstance(message, ChatMessage):
            return message.message
        return uni_message_to_contents(message)

    @staticmethod
    def serialize_auto_task_result(auto_tasks: AutoTaskList) -> str:
        """将自动任务结果序列化为会话中可追溯的统一格式。"""
        reply = (auto_tasks.reply or "").strip()
        task_json = auto_tasks.json(exclude={"reply", "create_at"}, ensure_ascii=False)
        if reply:
            return f"{reply}\n<hr/>\n{task_json}"
        return f"<hr/>\n{task_json}"

    def serialize_recent_history(self, keep_recent: int = 8) -> str:
        """序列化最近消息，供轻量意图路由使用。"""

        return self.context.serialize_recent_history(keep_recent=keep_recent)

    @staticmethod
    def normalize_auto_task_reply(
        route: IntentRoute | None,
        plan: AgentPlan | None,
        auto_tasks: AutoTaskList,
    ) -> str:
        """保证命令型任务至少有一条自然的用户可读说明。"""

        reply = (auto_tasks.reply or "").strip()
        if reply:
            return reply
        return MessageProcessingPipeline.build_auto_task_reply(route, plan, auto_tasks)

    @staticmethod
    def build_auto_task_reply(
        route: IntentRoute | None,
        plan: AgentPlan | None,
        auto_tasks: AutoTaskList,
    ) -> str:
        """为命令执行和确认场景构造简洁的阶段性说明。"""

        if auto_tasks.need_confirm:
            if plan and plan.missing_info:
                missing = "、".join(plan.missing_info)
                return f"我已经整理出执行思路，但还缺少 {missing}，补齐后我就能继续往下处理。"
            return "我已经整理出接下来的处理步骤，但还需要你确认后我再继续执行。"

        if auto_tasks.tasks:
            command_names = [f"“{task.command}”" for task in auto_tasks.tasks]
            if len(command_names) == 1:
                if plan and plan.requires_rag:
                    return f"我已经理解你的目标，接下来会先结合检索到的上下文，再调用{command_names[0]}处理。"
                return f"我已经理解你的目标，接下来会调用{command_names[0]}来处理。"
            commands = "、".join(command_names[:-1]) + f" 和 {command_names[-1]}"
            if plan and plan.requires_rag:
                return f"我会先整理相关上下文，再按顺序调用 {commands} 来完成这件事。"
            return f"我已经拆好了这次要做的步骤，接下来会按顺序调用 {commands} 来处理。"

        if route and route.requires_rag:
            return "我已经整理好相关上下文，接下来会把可用信息压缩成结论回复给你。"
        return ""

    @staticmethod
    def should_retrieve(route: IntentRoute | None, plan: AgentPlan | None) -> bool:
        """只有明确需要知识检索时才调用 RAG。"""

        return bool((route and route.requires_rag) or (plan and plan.requires_rag))

    @staticmethod
    def combine_knowledge(local_knowledge: str | None, rag_knowledge: str | None) -> str | None:
        """合并本地检索结果和外部 RAG 结果。"""

        sections = []
        if local_knowledge:
            sections.append("# 本地上下文检索结果\n" + local_knowledge)
        if rag_knowledge:
            sections.append("# 外部知识库检索结果\n" + rag_knowledge)
        return "\n\n".join(sections) if sections else None

    def resolve_candidate_commands(self, plan: AgentPlan | None) -> set[str]:
        """将 Planner 候选命令解析成当前 Helper 中真实存在的命令名。"""

        if plan is None or not plan.candidate_commands:
            return set()
        return self.policy.resolve_candidate_commands(plan.candidate_commands)

    def build_nodes(self, message: str | UniMessage | ChatMessage) -> list[WorkflowNode]:
        """构建当前轮次要执行的工作流节点列表。"""
        return [
            SummaryHistoryNode(),
            NormalizeUserInputNode(message),
            AppendUserMessageNode(),
            LocalChatStatisticsNode(),
            LocalContextQueryNode(),
            IntentRouteNode(),
            RetrieveLocalKnowledgeNode(),
            DirectVisionReplyNode(),
            ExtractContextNode(),
            PlannerNode(),
            ExecutionPolicyNode(),
            RetrieveKnowledgeNode(),
            PlanTasksNode(),
            ValidateAutoTasksNode(),
            PersistAssistantReplyNode(),
        ]

    async def process(self, message: str | UniMessage | ChatMessage) -> AgentTurnResult:
        """执行完整消息处理流水线。"""
        state = PipelineState(trace_id=self.trace_id)
        for node in self.build_nodes(message):
            node_name = node.__class__.__name__
            started_at = perf_counter()
            logger.debug(f'AutoGPT trace "{self.trace_id}" node "{node_name}" started')
            try:
                await node.run(self, state)
            except Exception as error:
                duration_ms = (perf_counter() - started_at) * 1000
                logger.exception(
                    f'AutoGPT trace "{self.trace_id}" node "{node_name}" failed in {duration_ms:.2f}ms: {error}'
                )
                raise
            duration_ms = (perf_counter() - started_at) * 1000
            logger.debug(f'AutoGPT trace "{self.trace_id}" node "{node_name}" finished in {duration_ms:.2f}ms')
        return build_turn_result(
            trace_id=self.trace_id,
            route=state.intent_route,
            plan=state.agent_plan,
            auto_tasks=state.auto_tasks,
            command_tools=self.command_tools,
        )
