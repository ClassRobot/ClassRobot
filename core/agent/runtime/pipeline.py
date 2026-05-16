from __future__ import annotations

from typing import Any, Literal

from nonebot import logger
from nonebot_plugin_alconna import UniMessage

from utils.helper import Helpers
from core.llm import LLMTaskType, client_create
from core.llm.message import Content, Context, Messages
from core.llm.util import uni_message_to_contents
from utils.storage import ChatHistoryStore, ChatHistorySummary, chat_history_store
from core.agent.builtin import AutoTaskAgent, ExtractAgent, RagAgent, SummaryAgent
from core.agent.builtin.conversation import ExtractAgentConfig, SummaryAgentConfig

from .workflow import build_turn_result
from .knowledge import RuntimeContext, LocalKnowledgeRetriever
from .schema import AgentPlan, ChatMessage, RuntimeScene, IntentRoute, AutoTaskList, AgentTurnResult
from .graph_executor import RuntimeGraphExecutor
from .harness import ProgressStage, AutoGPTHarness, ProgressReporter, ProgressFeedbackHarness
from .orchestration_config import RuntimeGraphConfig, RuntimeNodeConfig, default_graph_config, get_runtime_orchestration_snapshot
from .node_registry import RUNTIME_NODE_REGISTRY
from .coordination import (
    RUNTIME_NODE_CLASS_REGISTRY,
    WorkflowNode,
    PipelineState,
    NormalizeUserInputNode,
    LocalChatStatisticsQuery,
    LocalContextQueryResolver,
)
from .coordination.nodes import (
    PlannerNode,
    PlanTasksNode,
    IntentRouteNode,
    ExtractContextNode,
    SummaryHistoryNode,
    ExecutionPolicyNode,
    AppendUserMessageNode,
    DirectVisionReplyNode,
    LocalContextQueryNode,
    RetrieveKnowledgeNode,
    ValidateAutoTasksNode,
    LocalChatStatisticsNode,
    PersistAssistantReplyNode,
    RetrieveLocalKnowledgeNode,
)


class MessageProcessingPipeline:
    """封装 AI 会话主链路的标准处理流水线。

    这个类只负责装配 Harness、构建运行节点和提供稳定 facade。
    具体 WorkflowNode 实现放在 ``coordination/nodes.py``，本地确定性
    查询规则放在 ``coordination/local_context.py``，避免主流程文件继续
    膨胀成 god file。
    """

    def __init__(
        self,
        helpers: Helpers | None = None,
        messages: Messages | None = None,
        trace_id: str = "",
        progress_reporter: ProgressReporter | None = None,
        runtime_context: RuntimeContext | None = None,
        local_knowledge_retriever: LocalKnowledgeRetriever | None = None,
        chat_store: ChatHistoryStore | None = None,
        harness: AutoGPTHarness | None = None,
    ) -> None:
        if harness is None:
            if helpers is None or messages is None:
                raise ValueError(
                    "MessageProcessingPipeline requires helpers and messages when harness is not provided."
                )
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
        self.local_context_queries = LocalContextQueryResolver(self.helpers, self.context)
        self.runtime_graph_config = default_graph_config()
        self.current_node_config: dict[str, Any] = {}
        self.current_node_type = ""

    async def create_llm_completion(self, messages: Messages, **kwargs: Any):
        """通过统一 LLM 网关发起一次模型调用。

        测试和后续集成只需要替换 `pipeline.client_create`，节点本身不直接
        持有 LLM 入口，避免拆分模块后出现多处 monkeypatch 边界。
        """

        model_role = kwargs.pop("model_role", None)
        if not kwargs.get("llm_name"):
            kwargs["llm_name"] = self.resolve_model_name(
                model_role=model_role,
                task_type=kwargs.get("task_type"),
            )
        return await client_create(messages, **kwargs)

    def resolve_model_name(self, *, model_role: str | None = None, task_type: Any = None) -> str | None:
        """按节点配置、模型角色和任务类型解析本次 LLM 调用使用的模型名。"""

        explicit_model = self.current_node_config.get("model") or self.current_node_config.get("llm_name")
        if explicit_model:
            return str(explicit_model)
        configured_role = self.current_node_config.get("model_profile")
        role = (
            str(configured_role)
            if configured_role
            else model_role or self.resolve_model_role_from_task_type(task_type) or self.current_node_model_role()
        )
        return self.runtime_graph_config.model_profiles.get_model_for_role(role)

    def current_node_model_role(self) -> str | None:
        """读取当前运行时节点定义的默认模型角色。"""

        definition = RUNTIME_NODE_REGISTRY.get(self.current_node_type)
        return definition.model_role if definition else None

    @staticmethod
    def resolve_model_role_from_task_type(task_type: Any) -> str | None:
        """把 LLM 任务类型映射到开发者配置的模型角色。"""

        if task_type == LLMTaskType.vision:
            return "vision"
        if task_type == LLMTaskType.summary:
            return "summary"
        if task_type in {LLMTaskType.extract}:
            return "worker"
        if task_type in {LLMTaskType.plan, LLMTaskType.reply, LLMTaskType.tool}:
            return "supervisor"
        return None

    def create_extract_agent(self) -> ExtractAgent:
        """创建上下文抽取 Agent。"""

        return ExtractAgent(
            config=ExtractAgentConfig(
                llm_name=self.resolve_model_name(model_role="worker", task_type=LLMTaskType.extract)
            )
        )

    def create_rag_agent(self) -> RagAgent:
        """创建外部知识库检索 Agent。"""

        return RagAgent()

    def create_auto_task_agent(self, **kwargs: Any) -> AutoTaskAgent:
        """创建自动任务生成 Agent。"""

        kwargs.setdefault("llm_name", self.resolve_model_name(model_role="supervisor", task_type=LLMTaskType.plan))
        return AutoTaskAgent(**kwargs)

    async def summarize_history(self, messages: Messages) -> Messages:
        """在会话过长时压缩历史消息。"""

        return await SummaryAgent(
            config=SummaryAgentConfig(
                llm_name=self.resolve_model_name(model_role="summary", task_type=LLMTaskType.summary)
            )
        ).execute(messages)

    async def report_progress(self, message: str, stage: ProgressStage = "thinking") -> None:
        """向用户发送少量有价值的处理状态，失败时只记日志不中断主流程。"""

        await self.observability.report_progress(message, stage=stage)

    def record_prompt_stage(
        self,
        stage: Literal["route", "extract", "plan", "task"],
        *,
        prompt_char_length: int,
        recalled_commands: list[str] | tuple[str, ...] = (),
        recalled_skills: list[str] | tuple[str, ...] = (),
        selected_commands: list[str] | tuple[str, ...] = (),
    ) -> None:
        """记录某个 Prompt 阶段的输入规模、召回结果与命中命令。"""

        self.observability.record_prompt_stage(
            stage,
            prompt_char_length=prompt_char_length,
            recalled_commands=recalled_commands,
            recalled_skills=recalled_skills,
            selected_commands=selected_commands,
        )

    def record_planner_candidate_commands(self, commands: list[str] | tuple[str, ...]) -> None:
        """记录 Planner 输出的候选命令。"""

        self.observability.record_planner_candidate_commands(commands)

    def record_final_hit_commands(self, commands: list[str] | tuple[str, ...]) -> None:
        """记录最终保留、可执行的命令序列。"""

        self.observability.record_final_hit_commands(commands)

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

        return await self.local_context_queries.resolve_local_chat_statistics_query(contents)

    async def resolve_local_user_chat_statistics(self, query: LocalChatStatisticsQuery) -> AutoTaskList:
        """统计当前用户与机器人的聊天条数。"""

        return await self.local_context_queries.resolve_local_user_chat_statistics(query)

    async def resolve_local_group_chat_statistics(self, query: LocalChatStatisticsQuery) -> AutoTaskList:
        """统计当前系统群组的群聊消息条数。"""

        return await self.local_context_queries.resolve_local_group_chat_statistics(query)

    def resolve_local_context_query(self, contents: list[Content]) -> AutoTaskList | None:
        """把确定性的本地上下文问题路由到已有项目命令。"""

        return self.local_context_queries.resolve_local_context_query(contents)

    def resolve_class_context_query(self, contents: list[Content]) -> AutoTaskList | None:
        """把高频班级状态问题路由到班级或用户信息查询命令。"""

        return self.local_context_queries.resolve_class_context_query(contents)

    def resolve_schedule_context_query(self, contents: list[Content]) -> AutoTaskList | None:
        """把本人课表查询路由到查询课表命令，并尽量补上常见日期偏移。"""

        return self.local_context_queries.resolve_schedule_context_query(contents)

    @staticmethod
    def is_self_identity_query(contents: list[Content]) -> bool:
        """判断用户是否在询问自己的身份、角色或管理员状态。"""

        return LocalContextQueryResolver.is_self_identity_query(contents)

    @staticmethod
    def normalized_text_query(contents: list[Content]) -> str:
        """提取纯文本消息并去掉空白，供本地确定性路由使用。"""

        return LocalContextQueryResolver.normalized_text_query(contents)

    @classmethod
    def parse_local_chat_statistics_query(cls, text: str) -> LocalChatStatisticsQuery | None:
        """解析是否命中当前用户或当前群的聊天统计问题。"""

        return LocalContextQueryResolver.parse_local_chat_statistics_query(text)

    @staticmethod
    def resolve_chat_statistics_window(text: str) -> tuple[str, Any, Any]:
        """从问题中提取受控的时间范围。"""

        return LocalContextQueryResolver.resolve_chat_statistics_window(text)

    @staticmethod
    def format_user_chat_statistics_reply(query: LocalChatStatisticsQuery, summary: ChatHistorySummary) -> str:
        """渲染当前用户与机器人的聊天统计回复。"""

        return LocalContextQueryResolver.format_user_chat_statistics_reply(query, summary)

    @staticmethod
    def format_group_chat_statistics_reply(query: LocalChatStatisticsQuery, summary: ChatHistorySummary) -> str:
        """渲染当前系统群的聊天统计回复。"""

        return LocalContextQueryResolver.format_group_chat_statistics_reply(query, summary)

    @staticmethod
    def contains_mutating_words(text: str) -> bool:
        """识别会修改状态的词，避免本地查询规则误拦截写操作。"""

        return LocalContextQueryResolver.contains_mutating_words(text)

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

    def render_command_tools_prompt_from_tools(self, tools) -> str:
        """把已选中的命令工具渲染为 Prompt 片段。"""

        return self.policy.render_command_tools_prompt_from_tools(tools)

    def render_skill_catalog_prompt_from_summaries(self, summaries) -> str:
        """把已选中的 Skill 摘要渲染为 Prompt 片段。"""

        return self.policy.render_skill_catalog_prompt_from_summaries(summaries)

    def select_route_command_tools(self, contents: list[Content]):
        """选择入口路由阶段需要暴露给模型的命令子集。"""

        return self.policy.select_command_tools(query=self.text_query_from_contents(contents), limit=8)

    def select_route_skill_summaries(self, contents: list[Content]):
        """选择入口路由阶段需要暴露给模型的 Skill 子集。"""

        return self.policy.select_skill_summaries(query=self.text_query_from_contents(contents), limit=4)

    def select_plan_command_tools(self, context: Context):
        """选择规划阶段需要暴露给模型的命令子集。"""

        return self.policy.select_command_tools(query=context.single_modal(), limit=14)

    def select_plan_skill_summaries(self, context: Context):
        """选择规划阶段需要暴露给模型的 Skill 子集。"""

        return self.policy.select_skill_summaries(query=context.single_modal(), limit=5)

    def select_task_command_tools(self, context: Context, *, plan: AgentPlan | None = None):
        """选择任务生成阶段需要暴露给模型的命令子集。"""

        return self.policy.select_command_tools(
            query=context.single_modal(),
            limit=12,
            candidate_commands=plan.candidate_commands if plan is not None else None,
        )

    def select_task_skill_summaries(self, context: Context, *, plan: AgentPlan | None = None):
        """选择任务生成阶段需要暴露给模型的 Skill 子集。"""

        return self.policy.select_skill_summaries(
            query=context.single_modal(),
            limit=5,
            skill_names=plan.candidate_skills if plan is not None else None,
        )

    def render_route_command_tools_prompt(self, contents: list[Content]) -> str:
        """为入口路由阶段生成较小的命令目录子集。"""

        return self.render_command_tools_prompt_from_tools(self.select_route_command_tools(contents))

    def render_route_skill_catalog_prompt(self, contents: list[Content]) -> str:
        """为入口路由阶段生成较小的 Skill 目录子集。"""

        return self.render_skill_catalog_prompt_from_summaries(self.select_route_skill_summaries(contents))

    def render_plan_command_tools_prompt(self, context: Context) -> str:
        """为规划阶段生成较完整但仍受控的命令目录子集。"""

        return self.render_command_tools_prompt_from_tools(self.select_plan_command_tools(context))

    def render_plan_skill_catalog_prompt(self, context: Context) -> str:
        """为规划阶段生成较完整但仍受控的 Skill 目录子集。"""

        return self.render_skill_catalog_prompt_from_summaries(self.select_plan_skill_summaries(context))

    def render_task_command_tools_prompt(self, context: Context, *, plan: AgentPlan | None = None) -> str:
        """为任务生成阶段输出最相关的命令目录。"""

        return self.render_command_tools_prompt_from_tools(self.select_task_command_tools(context, plan=plan))

    def render_task_skill_catalog_prompt(self, context: Context, *, plan: AgentPlan | None = None) -> str:
        """为任务生成阶段输出最相关的 Skill 目录。"""

        return self.render_skill_catalog_prompt_from_summaries(self.select_task_skill_summaries(context, plan=plan))

    def resolve_candidate_commands(self, plan: AgentPlan | None) -> set[str]:
        """将 Planner 候选命令解析成当前 Helper 中真实存在的命令名。"""

        if plan is None or not plan.candidate_commands:
            return set()
        return self.policy.resolve_candidate_commands(plan.candidate_commands)

    def build_nodes(self, message: str | UniMessage | ChatMessage) -> list[WorkflowNode]:
        """构建当前轮次要执行的工作流节点列表。"""

        config = self.resolve_runtime_graph_config()
        return self.build_nodes_from_config(config, message)

    def resolve_runtime_graph_config(self) -> RuntimeGraphConfig:
        """读取热更新运行时图，失败时回退默认图。"""

        snapshot = get_runtime_orchestration_snapshot()
        try:
            self.runtime_graph_config = snapshot.config
            return snapshot.config
        except Exception as error:
            logger.warning(
                f'AutoGPT trace "{self.trace_id}" failed to build runtime graph, '
                f"fallback default orchestration graph: {error}"
            )
            self.runtime_graph_config = default_graph_config()
            return self.runtime_graph_config

    def build_nodes_from_config(
        self,
        config: RuntimeGraphConfig,
        message: str | UniMessage | ChatMessage,
    ) -> list[WorkflowNode]:
        """按运行时编排图构造节点列表。"""

        node_configs = {node.node_type: node.config for node in config.nodes if node.enabled}
        return [
            self.build_node_by_type(node_type, message, node_configs.get(node_type, {}))
            for node_type in config.node_order
        ]

    def build_node_from_config(
        self,
        node_config: RuntimeNodeConfig,
        message: str | UniMessage | ChatMessage,
    ) -> WorkflowNode:
        """根据运行时节点配置构造具体节点实例。"""

        return self.build_node_by_type(node_config.node_type, message, node_config.config)

    @staticmethod
    def build_node_by_type(
        node_type: str,
        message: str | UniMessage | ChatMessage,
        node_config: dict[str, Any] | None = None,
    ) -> WorkflowNode:
        """根据运行时节点类型构造具体 Pipeline 节点。"""

        _ = node_config
        if node_type == "normalize_input":
            return NormalizeUserInputNode(message)
        node_class = RUNTIME_NODE_CLASS_REGISTRY.get(node_type)
        if node_class is not None:
            return node_class()
        raise ValueError(f"Unknown AutoGPT runtime node type: {node_type}")

    async def process(self, message: str | UniMessage | ChatMessage) -> AgentTurnResult:
        """执行完整消息处理流水线。"""

        state = PipelineState(trace_id=self.trace_id)
        config = self.resolve_runtime_graph_config()
        await RuntimeGraphExecutor(config).run(self, state, message)
        return build_turn_result(
            trace_id=self.trace_id,
            route=state.intent_route,
            plan=state.agent_plan,
            auto_tasks=state.auto_tasks,
            command_tools=self.command_tools,
            observability=self.observability.build_metrics(),
        )

    def resolve_runtime_scene(self, state: PipelineState) -> RuntimeScene:
        """根据当前状态推断运行时场景。"""

        if state.runtime_scene != "chat":
            return state.runtime_scene
        if state.auto_tasks and state.auto_tasks.is_violation:
            return "violation"
        route = state.intent_route
        if route is None:
            return "chat"
        if route.intent == "violation":
            return "violation"
        if route.intent == "vision_file" or self.has_visual_input(state.user_content):
            return "vision"
        if route.intent == "complex_task":
            return "task"
        if route.requires_command or route.intent == "command":
            return "command"
        if route.requires_rag or route.intent == "knowledge":
            return "knowledge"
        return "chat"
