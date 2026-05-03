from abc import ABC, abstractmethod
from time import perf_counter
from typing import Awaitable, Callable

from nonebot import logger
from pydantic import BaseModel, Field
from nonebot_plugin_alconna import UniMessage
from utils.helper import Helpers
from utils.llm import LLMTaskType, client_create
from utils.template.prompts import Prompt
from utils.llm.message import Content, Context, LLMRole, Messages
from utils.llm.util import uni_message_to_contents
from utils.llm.util import json_loads
from utils.llm.agents.tools import AutoTaskAgent, ExtractAgent, RagAgent, SummaryAgent

from .schema import AgentPlan, IntentRoute, AutoTaskList, ChatMessage, AgentTurnResult
from .command_tools import CommandToolCatalog
from .workflow import build_turn_result

ProgressReporter = Callable[[str], Awaitable[None]]


class PipelineState(BaseModel):
    """承载一次消息处理流程中的中间状态。"""

    trace_id: str = ""
    user_content: list[Content] = Field(default_factory=list)
    intent_route: IntentRoute | None = None
    agent_plan: AgentPlan | None = None
    extracted_context: Context | None = None
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


class IntentRouteNode(WorkflowNode):
    """先判断消息类型，避免所有请求都进入重型规划链路。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        route_messages = Messages()
        route_messages.extend(pipeline.messages.get(LLMRole.system))
        route_messages.system_message(
            await Prompt("intent_route").render(
                {
                    "helpers": pipeline.helpers,
                    "command_tools": pipeline.command_tools,
                    "history": pipeline.serialize_recent_history(),
                }
            )
        )
        response = await client_create(
            route_messages,
            multi_modal=False,
            max_tokens=1024,
            task_type=LLMTaskType.plan,
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
        await pipeline.report_progress(pipeline.build_user_progress_message(state.intent_route))

        if state.intent_route.intent == "violation":
            state.auto_tasks = AutoTaskList(
                reply=state.intent_route.reply or "用户发送的消息包含违规内容，已被屏蔽！",
                is_violation=True,
            )
        elif not state.intent_route.requires_command and not state.intent_route.requires_rag:
            state.auto_tasks = AutoTaskList(
                reply=state.intent_route.reply or "我在，有什么需要我帮你处理的吗？",
                need_confirm=state.intent_route.need_confirm,
            )


class ExtractContextNode(WorkflowNode):
    """从当前会话中抽取结构化上下文。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None:
            return
        state.extracted_context = await ExtractAgent().execute(pipeline.messages)


class PlannerNode(WorkflowNode):
    """把上下文转换成显式计划，再交给后续节点执行。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None or state.extracted_context is None:
            return

        plan_messages = Messages()
        plan_messages.extend(pipeline.messages.get(LLMRole.system))
        plan_messages.system_message(
            await Prompt("agent_plan").render(
                {
                    "helpers": pipeline.helpers,
                    "command_tools": pipeline.command_tools,
                    "route": state.intent_route.json(ensure_ascii=False) if state.intent_route else "{}",
                    "context": state.extracted_context.single_modal(),
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
        ).execute(
            state.extracted_context,
            state.retrieved_knowledge,
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
        helpers: Helpers,
        messages: Messages,
        trace_id: str = "",
        progress_reporter: ProgressReporter | None = None,
    ) -> None:
        self.helpers = helpers
        self.command_tools = CommandToolCatalog.from_helpers(helpers)
        self.messages = messages
        self.trace_id = trace_id
        self.progress_reporter = progress_reporter
        self._last_progress = ""

    async def report_progress(self, message: str) -> None:
        """向用户发送少量有价值的处理状态，失败时只记日志不中断主流程。"""

        if not self.progress_reporter or not message or message == self._last_progress:
            return
        self._last_progress = message
        try:
            await self.progress_reporter(message)
        except Exception as error:
            logger.warning(f'AutoGPT trace "{self.trace_id}" progress feedback failed: {error}')

    @staticmethod
    def build_user_progress_message(route: IntentRoute | None) -> str:
        """根据入口路由生成用户能理解的单条状态提示。"""

        if route is None or route.intent in {"chat", "violation"}:
            return ""
        if route.requires_rag and route.requires_command:
            return "我先查一下相关信息，再帮你处理，请稍等~"
        if route.requires_rag:
            return "我查一下相关资料，请稍等~"
        if route.requires_command:
            return "我帮你处理一下，请稍等~"
        return ""

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

        messages = Messages(messages=self.messages.messages[-keep_recent:])
        return messages.get(LLMRole.user, LLMRole.assistant).json(ensure_ascii=False)

    @staticmethod
    def should_retrieve(route: IntentRoute | None, plan: AgentPlan | None) -> bool:
        """只有明确需要知识检索时才调用 RAG。"""

        return bool((route and route.requires_rag) or (plan and plan.requires_rag))

    def resolve_candidate_commands(self, plan: AgentPlan | None) -> set[str]:
        """将 Planner 候选命令解析成当前 Helper 中真实存在的命令名。"""

        if plan is None or not plan.candidate_commands:
            return set()
        return self.command_tools.resolve_commands(plan.candidate_commands)

    def build_nodes(self, message: str | UniMessage | ChatMessage) -> list[WorkflowNode]:
        """构建当前轮次要执行的工作流节点列表。"""
        return [
            SummaryHistoryNode(),
            NormalizeUserInputNode(message),
            AppendUserMessageNode(),
            IntentRouteNode(),
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
