from __future__ import annotations

import json
from time import perf_counter
from typing import Any, Literal

from nonebot import logger
from src.platform.helper import Helpers
from src.core.llm.gateway import LLMRequest
from nonebot_plugin_alconna import UniMessage
from src.core.llm.util import uni_message_to_contents
from src.core.llm.message import Content, Context, Messages
from src.core.llm import LLMTaskType, llm_gateway, client_create
from src.core.storage import ChatHistoryStore, chat_history_store
from src.core.agent.builtin import RagAgent, ExtractAgent, SummaryAgent, AutoTaskAgent
from src.core.agent.builtin.conversation import ExtractAgentConfig, SummaryAgentConfig

from .auto_task import Param, AutoTask
from .workflow import build_turn_result
from .capabilities import CapabilityRequirement
from .graph_executor import RuntimeGraphExecutor
from .node_registry import RUNTIME_NODE_REGISTRY
from .live_trace import agent_live_trace_registry
from .knowledge import RuntimeContext, LocalKnowledgeRetriever
from .harness import ProgressStage, AutoGPTHarness, ProgressReporter, ProgressFeedbackHarness
from .coordination import RUNTIME_NODE_CLASS_REGISTRY, WorkflowNode, PipelineState, NormalizeUserInputNode
from .orchestration_config import (
    RuntimeNodeConfig,
    RuntimeGraphConfig,
    default_graph_config,
    get_runtime_orchestration_snapshot,
)
from .schema import (
    AgentPlan,
    ChatMessage,
    IntentRoute,
    AutoTaskList,
    RuntimeScene,
    AgentTurnResult,
    KnowledgeSourceRequest,
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
    RetrieveKnowledgeNode,
    ValidateAutoTasksNode,
    PersistAssistantReplyNode,
    RetrieveLocalKnowledgeNode,
)


class MessageProcessingPipeline:
    """封装 AI 会话主链路的标准处理流水线。

    这个类只负责装配 Harness、构建运行节点和提供稳定 facade。
    具体 WorkflowNode 实现放在 ``coordination/nodes.py``，避免主流程
    文件继续膨胀成 god file。
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
        self.mcp_tools = harness.mcp_tools
        self.skill_catalog_prompt = harness.skill_catalog_prompt
        self.messages = harness.messages
        self.trace_id = harness.trace_id
        self.runtime_context = harness.runtime_context
        self.local_knowledge_retriever = harness.local_knowledge_retriever
        self.chat_store = harness.chat_store
        self.runtime_graph_config = default_graph_config()
        self.current_node_config: dict[str, Any] = {}
        self.current_node_type = ""
        self.blocked_llm_names: set[str] = set()

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
                multi_modal=kwargs.get("multi_modal"),
            )
        llm_name = str(kwargs.get("llm_name") or "")
        task_type = kwargs.get("task_type")
        started = perf_counter()
        agent_live_trace_registry.emit(
            self.trace_id,
            event_type="llm_started",
            stage=self.stage_from_node_type(self.current_node_type) or "plan",
            node_type=self.current_node_type,
            node_label=self.current_node_type,
            status="running",
            model_name=llm_name,
            params_preview={
                "task_type": str(task_type or ""),
                "multi_modal": kwargs.get("multi_modal"),
                "message_count": len(getattr(messages, "messages", [])),
                "excluded_models": sorted(self.blocked_llm_names),
            },
        )
        llm_gateway.clear_last_attempt_errors()
        try:
            response = await client_create(
                messages,
                exclude_llm_names=tuple(sorted(self.blocked_llm_names)),
                **kwargs,
            )
            agent_live_trace_registry.emit(
                self.trace_id,
                event_type="llm_completed",
                stage=self.stage_from_node_type(self.current_node_type) or "plan",
                node_type=self.current_node_type,
                node_label=self.current_node_type,
                status="completed",
                model_name=llm_name,
                duration_ms=(perf_counter() - started) * 1000,
            )
            return response
        except Exception as error:
            agent_live_trace_registry.emit(
                self.trace_id,
                event_type="llm_failed",
                stage=self.stage_from_node_type(self.current_node_type) or "plan",
                node_type=self.current_node_type,
                node_label=self.current_node_type,
                status="failed",
                model_name=llm_name,
                error=error,
                duration_ms=(perf_counter() - started) * 1000,
            )
            raise
        finally:
            self.record_quota_limited_models()

    def resolve_model_name(
        self,
        *,
        model_role: str | None = None,
        task_type: Any = None,
        multi_modal: bool | None = None,
    ) -> str | None:
        """按节点配置、模型角色和任务类型解析本次 LLM 调用使用的模型名。"""

        explicit_model = self.current_node_config.get("model") or self.current_node_config.get("llm_name")
        if explicit_model:
            explicit_name = str(explicit_model)
            if explicit_name not in self.blocked_llm_names:
                return explicit_name
            fallback_name = self.resolve_fallback_model_name(task_type=task_type, multi_modal=multi_modal)
            if fallback_name:
                logger.info(
                    f'AutoGPT trace "{self.trace_id}" skipped blocked model "{explicit_name}" '
                    f'and selected fallback "{fallback_name}"'
                )
            return fallback_name
        configured_role = self.current_node_config.get("model_profile")
        role = (
            str(configured_role)
            if configured_role
            else model_role or self.resolve_model_role_from_task_type(task_type) or self.current_node_model_role()
        )
        preferred_name = self.runtime_graph_config.model_profiles.get_model_for_role(role)
        if preferred_name and preferred_name not in self.blocked_llm_names:
            return preferred_name
        if preferred_name and preferred_name in self.blocked_llm_names:
            fallback_name = self.resolve_fallback_model_name(task_type=task_type, multi_modal=multi_modal)
            if fallback_name:
                logger.info(
                    f'AutoGPT trace "{self.trace_id}" skipped blocked model "{preferred_name}" '
                    f'and selected fallback "{fallback_name}"'
                )
            return fallback_name
        if self.blocked_llm_names:
            return self.resolve_fallback_model_name(task_type=task_type, multi_modal=multi_modal)
        return preferred_name

    def resolve_fallback_model_name(self, *, task_type: Any = None, multi_modal: bool | None = None) -> str | None:
        """在当前轮次屏蔽部分模型后，选出一个可用后备模型。"""

        if not self.blocked_llm_names:
            return None

        candidates = llm_gateway.router.select(
            LLMRequest(
                messages="",
                llm_name=None,
                multi_modal=multi_modal,
                task_type=task_type or LLMTaskType.chat,
                exclude_llm_names=tuple(sorted(self.blocked_llm_names)),
            )
        )
        if not candidates:
            return None
        return candidates[0].name

    def record_quota_limited_models(self) -> None:
        """把本轮触发配额限制的模型加入 AutoGPT 局部冷却名单。"""

        for llm_name, error_text in llm_gateway.get_last_attempt_errors():
            if llm_name in self.blocked_llm_names:
                continue
            if not self.is_quota_limited_error(error_text):
                continue
            self.blocked_llm_names.add(llm_name)
            logger.warning(
                f'AutoGPT trace "{self.trace_id}" temporarily blocked model "{llm_name}" '
                "for the current turn due to quota exhaustion"
            )

    @staticmethod
    def is_quota_limited_error(error_text: str) -> bool:
        """判断错误文本是否表示模型配额耗尽。"""

        lowered = error_text.lower()
        return "429" in lowered or "resource_exhausted" in lowered or "quota exceeded" in lowered

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
    def local_knowledge_source_requests(route: IntentRoute | None) -> list[KnowledgeSourceRequest]:
        """从入口路由中提取需要本地检索的知识源。"""

        if route is None:
            return []
        return [
            request
            for request in route.knowledge_sources
            if request.source
            in {
                "user_chat_history",
                "group_chat_history",
                "user_file_space",
                "group_file_space",
            }
        ]

    @staticmethod
    def external_knowledge_source_requests(route: IntentRoute | None) -> list[KnowledgeSourceRequest]:
        """从入口路由中提取需要外部知识库检索的知识源。"""

        if route is None:
            return []
        return [request for request in route.knowledge_sources if request.source == "external_rag"]

    @classmethod
    def needs_local_knowledge(cls, route: IntentRoute | None) -> bool:
        """判断当前路由是否显式请求本地知识源。"""

        return bool(cls.local_knowledge_source_requests(route))

    @classmethod
    def needs_external_knowledge(cls, route: IntentRoute | None) -> bool:
        """判断当前路由是否显式请求外部知识库。"""

        return bool(cls.external_knowledge_source_requests(route) or (route and route.requires_rag))

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

    @staticmethod
    def normalize_capability_requirements(
        raw_requirements: object,
        fallback_requirements: list[CapabilityRequirement] | None = None,
    ) -> list[CapabilityRequirement]:
        """标准化 capability_requirements，异常时回退到受控默认值。"""

        fallback = list(fallback_requirements or [])
        if raw_requirements is None:
            return fallback
        if not isinstance(raw_requirements, list):
            return fallback
        normalized: list[CapabilityRequirement] = []
        for item in raw_requirements:
            if isinstance(item, CapabilityRequirement):
                normalized.append(item)
                continue
            if not isinstance(item, dict):
                return fallback
            try:
                normalized.append(CapabilityRequirement.parse_obj(item))
            except Exception:
                return fallback
        return normalized

    @staticmethod
    def route_requires_realtime_external_lookup(route: IntentRoute | None) -> bool:
        """判断当前路由是否需要实时公共外部检索能力。"""

        if route is None:
            return False
        return any(requirement.needs_realtime_public_external for requirement in route.capability_requirements)

    @classmethod
    def should_generate_direct_chat_reply(cls, route: IntentRoute | None, contents: list[Content]) -> bool:
        """判断当前轮次是否应直接生成最终 chat 回复。"""

        if route is None:
            return False
        if route.unavailable_reason == "realtime_source_missing":
            return True
        if route.intent != "chat":
            return False
        if route.requires_command or route.requires_rag or route.need_confirm:
            return False
        if cls.has_visual_input(contents):
            return False
        if cls.needs_local_knowledge(route) or cls.needs_external_knowledge(route):
            return False
        if any(
            requirement.required and (requirement.kind != "direct_chat" or requirement.execution_mode != "answer")
            for requirement in route.capability_requirements
        ):
            return False
        return True

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
            if all(task.task_type == "mcp_tool" for task in auto_tasks.tasks):
                if len(auto_tasks.tasks) == 1:
                    return "我先调用联网检索工具查询公开信息，整理好结果后马上告诉你。"
                return "我会按顺序调用外部工具检索公开信息，再把结果整理给你。"

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

        return bool(MessageProcessingPipeline.needs_external_knowledge(route) or (plan and plan.requires_rag))

    @staticmethod
    def combine_knowledge(local_knowledge: str | None, rag_knowledge: str | None) -> str | None:
        """合并本地检索结果和外部 RAG 结果。"""

        sections = []
        if local_knowledge:
            sections.append("# 本地上下文检索结果\n" + local_knowledge)
        if rag_knowledge:
            sections.append("# 外部知识库检索结果\n" + rag_knowledge)
        return "\n\n".join(sections) if sections else None

    @classmethod
    def format_external_knowledge_observation(
        cls,
        knowledge: str | None,
        *,
        route: IntentRoute | None,
        fallback_query: str,
    ) -> str:
        """把外部 RAG 结果包装成与本地检索一致的 observation 文本。"""

        requests = cls.external_knowledge_source_requests(route)
        query = requests[0].query if requests and requests[0].query else fallback_query
        required = requests[0].required if requests else bool(route and route.requires_rag)
        content = (knowledge or "").strip()
        status = "hit" if content else "miss"
        summary = content or "未检索到相关内容。"
        return "\n".join(
            [
                "# 外部知识源检索观察",
                "## external_rag",
                f"- query: {query or '未提供'}",
                f"- status: {status}",
                f"- required: {str(required).lower()}",
                f"- confidence: {'medium' if content else 'none'}",
                summary,
            ]
        )

    def render_command_tools_prompt_from_tools(self, tools) -> str:
        """把已选中的命令工具渲染为 Prompt 片段。"""

        return self.policy.render_command_tools_prompt_from_tools(tools)

    def render_skill_catalog_prompt_from_summaries(self, summaries) -> str:
        """把已选中的 Skill 摘要渲染为 Prompt 片段。"""

        return self.policy.render_skill_catalog_prompt_from_summaries(summaries)

    async def ensure_mcp_tools(self) -> None:
        """刷新 MCP 工具目录，并同步到 Pipeline facade。"""

        started = perf_counter()
        agent_live_trace_registry.emit(
            self.trace_id,
            event_type="mcp_list_tools_started",
            stage="tool_call",
            status="running",
            tool_name="tools/list",
            params_preview={"cached": self.policy.mcp_tools_loaded},
        )
        await self.policy.refresh_mcp_tools()
        self.mcp_tools = self.policy.mcp_tools
        status = "failed" if self.mcp_tools.last_error else "completed"
        agent_live_trace_registry.emit(
            self.trace_id,
            event_type="mcp_list_tools_completed",
            stage="tool_call",
            status=status,
            tool_name="tools/list",
            params_preview={
                "tool_count": len(self.mcp_tools.tools),
                "cached": self.policy.mcp_tools_loaded,
            },
            error=self.mcp_tools.last_error,
            duration_ms=(perf_counter() - started) * 1000,
        )

    def render_mcp_tools_prompt(self, *, tool_names=None) -> str:
        """把 MCP tool 目录渲染为 Prompt 片段。"""

        return self.policy.render_mcp_tools_prompt(tool_names=tool_names)

    def render_capability_catalog_prompt(self) -> str:
        """渲染当前 Agent 可见能力目录。"""

        return self.policy.render_capability_catalog_prompt()

    def has_realtime_external_lookup(self) -> bool:
        """判断当前是否存在实时公共外部检索能力。"""

        return self.policy.has_realtime_external_lookup()

    def unavailable_realtime_reply(self) -> str:
        """实时外部信息能力缺失时的自然收束回复。"""

        return "我这边目前没有可用的实时新闻或网页检索工具，所以不能可靠告诉你现在网上的最新热点。" "接入支持实时搜索的 MCP 工具后，我就可以直接帮你查。"

    def route_requires_unavailable_realtime_lookup(self, route: IntentRoute | None) -> bool:
        """判断路由是否要求实时公共外部能力但当前不可用。"""

        if route is None or self.has_realtime_external_lookup():
            return False
        return self.route_requires_realtime_external_lookup(route)

    def realtime_mcp_candidate_names(self) -> list[str]:
        """返回当前轮次可用的实时公共外部 MCP 工具名。"""

        return [tool.name for tool in self.mcp_tools.realtime_public_tools()]

    def normalize_candidate_mcp_tool_names(self, tool_names: list[str] | tuple[str, ...] | None) -> list[str]:
        """按当前 MCP 目录过滤并保留真实存在的工具名。"""

        if not tool_names:
            return []
        normalized: list[str] = []
        for tool_name in tool_names:
            if not tool_name or self.mcp_tools.get(tool_name) is None or tool_name in normalized:
                continue
            normalized.append(tool_name)
        return normalized

    def ensure_realtime_mcp_plan_defaults(
        self,
        plan: AgentPlan,
        route: IntentRoute | None,
    ) -> AgentPlan:
        """为实时外部检索场景补齐最小可执行 MCP 计划。"""

        if not self.route_requires_realtime_external_lookup(route):
            return plan
        candidate_mcp_tools = self.normalize_candidate_mcp_tool_names(plan.candidate_mcp_tools)
        if not candidate_mcp_tools:
            candidate_mcp_tools = self.realtime_mcp_candidate_names()
        if not candidate_mcp_tools:
            return plan
        plan.candidate_mcp_tools = candidate_mcp_tools
        plan.capability_requirements = self.normalize_capability_requirements(
            plan.capability_requirements,
            route.capability_requirements if route else [],
        )
        plan.requires_command = False
        plan.requires_rag = False
        if not plan.missing_info and not plan.confirmation_question:
            plan.should_execute = True
        if not plan.steps:
            plan.steps = [f"调用 MCP 工具 `{candidate_mcp_tools[0]}` 检索实时公开信息。"]
        if not plan.reason:
            plan.reason = "当前目标需要实时公共外部检索，已补齐 MCP 工具候选。"
        return plan

    def build_realtime_mcp_fallback_plan(
        self,
        route: IntentRoute | None,
        goal: str,
        *,
        reason: str,
    ) -> AgentPlan:
        """在 Planner 局部结构漂移时构造最小可执行 MCP 计划。"""

        candidate_mcp_tools = self.realtime_mcp_candidate_names()
        return AgentPlan(
            goal=goal,
            facts=[],
            missing_info=[],
            risk_level="low",
            requires_rag=False,
            requires_command=False,
            should_execute=bool(candidate_mcp_tools),
            candidate_mcp_tools=candidate_mcp_tools,
            capability_requirements=self.normalize_capability_requirements(
                route.capability_requirements if route else [],
                route.capability_requirements if route else [],
            ),
            steps=([f"调用 MCP 工具 `{candidate_mcp_tools[0]}` 检索实时公开信息。"] if candidate_mcp_tools else []),
            unavailable_reason=None if candidate_mcp_tools else "realtime_source_missing",
            reason=reason,
        )

    @staticmethod
    def select_mcp_query_field(tool_name: str, input_schema: dict[str, Any]) -> str:
        """从 MCP tool schema 中挑选最合适的查询字段名。"""

        properties = input_schema.get("properties") if isinstance(input_schema, dict) else None
        if not isinstance(properties, dict) or not properties:
            return "query"

        preferred_names = ("query", "q", "keyword", "keywords", "question", "text", "prompt", "input")
        normalized_map = {str(name).strip().lower(): str(name) for name in properties}
        for preferred_name in preferred_names:
            if preferred_name in normalized_map:
                return normalized_map[preferred_name]

        required = input_schema.get("required")
        if isinstance(required, list):
            for field_name in required:
                if isinstance(field_name, str) and field_name in properties:
                    return field_name

        if len(properties) == 1:
            return str(next(iter(properties)))
        return "query"

    def build_mcp_query_params(self, tool_name: str, query_text: str) -> list[Param]:
        """为 MCP 检索工具构造稳定的结构化查询参数。"""

        tool = self.mcp_tools.get(tool_name)
        field_name = self.select_mcp_query_field(tool_name, tool.input_schema if tool else {})
        payload = {field_name: query_text.strip()}
        return [Param(type="text", value=json.dumps(payload, ensure_ascii=False))]

    def normalize_mcp_task_params(self, tool_name: str, params: list[Param], fallback_query: str = "") -> list[Param]:
        """把模型生成的 MCP 参数标准化为满足 tool schema 的结构。"""

        tool = self.mcp_tools.get(tool_name)
        if tool is None:
            return params

        field_name = self.select_mcp_query_field(tool_name, tool.input_schema)
        query_like_fields = {"query", "q", "keyword", "keywords", "question", "text", "prompt", "input"}
        if field_name.lower() not in query_like_fields:
            return params

        if len(params) == 1:
            raw_value = params[0].value.strip()
            if raw_value.startswith("{"):
                try:
                    parsed = json.loads(raw_value)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict) and parsed.get(field_name):
                    return params

        candidate_text = ""
        if len(params) == 1 and params[0].type == "text":
            candidate_text = params[0].value.strip()
        if not candidate_text:
            candidate_text = fallback_query.strip()
        if not candidate_text:
            return params
        return self.build_mcp_query_params(tool_name, candidate_text)

    def should_force_realtime_mcp_task(
        self,
        route: IntentRoute | None,
        plan: AgentPlan | None,
        auto_tasks: AutoTaskList | None,
    ) -> bool:
        """判断当前轮次是否应直接构造最小实时 MCP 任务。"""

        if route is None or plan is None:
            return False
        if not self.route_requires_realtime_external_lookup(route):
            return False
        if plan.unavailable_reason == "realtime_source_missing":
            return False
        if not plan.should_execute or plan.missing_info or plan.confirmation_question:
            return False
        if not self.normalize_candidate_mcp_tool_names(plan.candidate_mcp_tools):
            return False
        if auto_tasks is None:
            return True
        return not auto_tasks.tasks

    def build_realtime_mcp_auto_tasks(
        self,
        *,
        route: IntentRoute | None,
        plan: AgentPlan,
        query_text: str,
        existing_reply: str | None = None,
    ) -> AutoTaskList:
        """为实时公开检索场景构造最小可执行的 MCP 自动任务。"""

        candidate_mcp_tools = self.normalize_candidate_mcp_tool_names(plan.candidate_mcp_tools)
        if not candidate_mcp_tools:
            return AutoTaskList(
                reply=existing_reply or self.unavailable_realtime_reply(),
                need_confirm=True,
            )

        tool_name = candidate_mcp_tools[0]
        reply = (existing_reply or "").strip() or self.build_auto_task_reply(
            route,
            plan,
            AutoTaskList(tasks=[AutoTask(task_type="mcp_tool", command=tool_name, params=[])]),
        )
        return AutoTaskList(
            reply=reply,
            tasks=[
                AutoTask(
                    task_type="mcp_tool",
                    command=tool_name,
                    params=self.build_mcp_query_params(tool_name, query_text),
                )
            ],
            need_confirm=False,
        )

    def select_route_command_tools(self, contents: list[Content]):
        """入口路由阶段暴露完整 service 命令目录，避免关键词召回隐藏能力。"""

        _ = contents
        return self.policy.select_command_tools()

    def select_route_skill_summaries(self, contents: list[Content]):
        """入口路由阶段暴露完整 Skill 目录，避免关键词提示影响可见性。"""

        _ = contents
        return self.policy.select_skill_summaries()

    def select_plan_command_tools(self, context: Context):
        """规划阶段暴露完整 service 命令目录。"""

        _ = context
        return self.policy.select_command_tools()

    def select_plan_skill_summaries(self, context: Context):
        """规划阶段暴露完整 Skill 目录。"""

        _ = context
        return self.policy.select_skill_summaries()

    def select_task_command_tools(self, context: Context, *, plan: AgentPlan | None = None):
        """任务生成阶段优先按 Planner 候选命令解析，否则暴露完整目录。"""

        _ = context
        return self.policy.select_command_tools(
            candidate_commands=plan.candidate_commands if plan is not None else None,
        )

    def select_task_skill_summaries(self, context: Context, *, plan: AgentPlan | None = None):
        """任务生成阶段优先按 Planner 候选 Skill 解析，否则暴露完整目录。"""

        _ = context
        return self.policy.select_skill_summaries(
            skill_names=plan.candidate_skills if plan is not None else None,
        )

    def resolve_candidate_mcp_tools(self, plan: AgentPlan | None) -> set[str]:
        """将 Planner 候选 MCP tool 解析成当前真实存在的工具名。"""

        if plan is None or not plan.candidate_mcp_tools:
            return set()
        return self.policy.resolve_candidate_mcp_tools(plan.candidate_mcp_tools)

    def render_route_command_tools_prompt(self, contents: list[Content]) -> str:
        """为入口路由阶段生成命令目录。"""

        return self.render_command_tools_prompt_from_tools(self.select_route_command_tools(contents))

    def render_route_skill_catalog_prompt(self, contents: list[Content]) -> str:
        """为入口路由阶段生成 Skill 目录。"""

        return self.render_skill_catalog_prompt_from_summaries(self.select_route_skill_summaries(contents))

    def render_plan_command_tools_prompt(self, context: Context) -> str:
        """为规划阶段生成命令目录。"""

        return self.render_command_tools_prompt_from_tools(self.select_plan_command_tools(context))

    def render_plan_skill_catalog_prompt(self, context: Context) -> str:
        """为规划阶段生成 Skill 目录。"""

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

    @staticmethod
    def stage_from_node_type(node_type: str) -> str:
        """把 Runtime 节点类型映射为后台 live trace 的阶段名。"""

        mapping = {
            "normalize_input": "session",
            "append_user_message": "session",
            "intent_route": "route",
            "retrieve_local_knowledge": "knowledge",
            "retrieve_knowledge": "knowledge",
            "extract_context": "extract",
            "summary_history": "extract",
            "planner": "plan",
            "plan_tasks": "task_generation",
            "execution_policy": "workflow",
            "validate_auto_tasks": "task_generation",
            "direct_vision_reply": "reply",
            "persist_assistant_reply": "persist",
        }
        return mapping.get(node_type, "")
