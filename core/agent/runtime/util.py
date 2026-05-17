import re
import json
from time import time
from uuid import uuid4
from datetime import datetime
from typing import Callable, Annotated, Awaitable

from nonebot import logger
from nonebot.params import Depends
from nonebot_plugin_alconna import UniMessage

from utils.helper import Helpers
from utils.template import Prompt
from utils.helper.depends import HelpersDepends
from core.agent.builtin import ExecutionReplyAgent
from core.agent.builtin.conversation import ExecutionReplyAgentConfig
from core.llm.message import Content, Context, LLMRole, Messages
from core.llm.util import uni_message_to_contents
from utils.models.depends import UserOrCreatedDepends

from .harness import AutoGPTHarness
from .knowledge import RuntimeContext
from .exception import SessionLockError
from .pipeline import MessageProcessingPipeline
from .loop import CognitiveAgentLoop
from .command_tools import CommandToolCatalog
from .persistence import WorkflowRunStore, WorkflowCheckpointStore
from .orchestration_config import get_runtime_orchestration_snapshot
from .workflow import WorkflowDispatcher, workflow_to_auto_tasks, clone_workflow_for_execution, workflow_requires_confirmation
from .schema import (
    ChatMessage,
    IntentRoute,
    AutoTaskList,
    TaskWorkflow,
    AgentTurnResult,
    CommandObservation,
    WorkflowExecutionResult,
)

pattern = r"!\[image\]\(([^)]+)\)"
ProgressReporter = Callable[[str], Awaitable[None]]
CONFIRM_PATTERNS = ("确认", "继续执行", "继续吧", "执行吧", "可以执行", "好的执行", "确认执行")
CANCEL_PATTERNS = ("取消", "不用了", "算了", "停止", "终止", "先别执行", "取消执行")


async def get_prompt_system(helpers: Helpers) -> str:
    """根据当前可用命令生成 AutoGPT 系统提示词。

    参数:
        helpers (Helpers): 当前用户可见的帮助信息集合。

    返回:
        str: 渲染后的系统提示词文本。
    """
    prompt_system = await Prompt("autogpt").render(
        {"helpers": helpers, "info": ("当前时间:" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}
    )
    return prompt_system


def markdown_to_message(text: str) -> UniMessage:
    """将 Markdown 文本转换为 `UniMessage` 消息对象。

    参数:
        text (str): 包含文本和 Markdown 图片语法的原始内容。

    返回:
        UniMessage: 适合直接发送的统一消息对象。
    """
    parts: list[str] = []
    last_idx = 0
    matches = list(re.finditer(pattern, text))

    # 按顺序拆分文本片段和 Markdown 图片地址。
    for match in matches:
        if match.start() > last_idx:
            parts.append(text[last_idx : match.start()])
        parts.append(match.group(1))
        last_idx = match.end()

    if last_idx < len(text):
        parts.append(text[last_idx:])

    if not matches:
        parts = [text]

    parts = [part for part in parts if part]

    reply_message = UniMessage()
    for part in parts:
        if part.startswith("http://") or part.startswith("https://"):
            reply_message += UniMessage.image(url=part)
        else:
            reply_message += part.replace(".", "⋅")
    return reply_message


class ChatSession:
    """封装单个用户的聊天会话状态与消息处理行为。

    该类负责维护用户会话上下文、系统提示词、会话锁以及
    AutoGPT 主流程调用入口。
    """

    def __init__(self, user_id: int, helpers: Helpers) -> None:
        """初始化实例。

        参数:
            user_id (int): 用户标识。
            helpers (Helpers): 帮助信息集合。
        """
        self.update_time = time()
        self.user_id = user_id
        self.lock = False  # 聊天锁，防止一轮聊天还没结束又开始新的聊天
        self.messages = Messages()
        self.helpers = helpers
        self.last_trace_id = ""
        self.last_workflow: TaskWorkflow | None = None
        self.last_turn_result: AgentTurnResult | None = None
        self.pending_workflow: TaskWorkflow | None = None
        self.workflow_checkpoint_store = WorkflowCheckpointStore()
        self.workflow_run_store = WorkflowRunStore()

    def is_last_duplicate_message(self, contents: list[Content]) -> bool:
        """检查即将发送的用户消息是否与上一条重复。

        参数:
            contents (list[Content]): 当前待发送的消息内容列表。

        返回:
            bool: 如果与最后一条用户消息一致则返回 `True`。
        """
        user_content = Context(role=LLMRole.user, content=contents)
        user_message = self.messages.get(LLMRole.user)
        if user_message and user_message[-1] == user_content:
            return True
        return False

    async def update_helpers(self, helpers: Helpers) -> None:
        """更新会话可用的帮助信息并刷新系统提示词。

        参数:
            helpers (Helpers): 当前用户可见的帮助信息集合。
        """
        self.helpers = helpers
        # 系统提示词依赖当前用户可见的命令集合，
        # 因此角色变化或 skill 热加载后都需要刷新首条 system 消息。
        prompts = await get_prompt_system(helpers)
        if self.messages and self.messages[0].role == LLMRole.system:
            self.messages[0].content = prompts
        else:
            self.messages.system_message(prompts)

    async def send_message(
        self,
        message: str | UniMessage | ChatMessage,
        progress_reporter: ProgressReporter | None = None,
        runtime_context: RuntimeContext | None = None,
    ) -> AgentTurnResult:
        """处理用户消息并执行 AutoGPT 主流程。

        参数:
            message (str | UniMessage | ChatMessage): 用户输入的原始消息。

        返回:
            AgentTurnResult: 统一承载本轮路由、计划、工作流和自动任务结果。
        """
        if self.lock:
            raise SessionLockError("聊天锁已经被锁定，无法发送消息！")
        try:
            self.lock = True
            self.last_trace_id = f"autogpt-{uuid4().hex[:12]}"
            logger.info(f'AutoGPT trace "{self.last_trace_id}" started for user {self.user_id}')
            await self.restore_pending_workflow()
            if pending_result := await self.resolve_pending_workflow_action(message, trace_id=self.last_trace_id):
                self.last_turn_result = pending_result
                if pending_result.workflow is not None:
                    self.last_workflow = pending_result.workflow
                logger.info(f'AutoGPT trace "{self.last_trace_id}" resumed pending workflow for user {self.user_id}')
                return pending_result
            pipeline = MessageProcessingPipeline(
                harness=self.build_harness(
                    trace_id=self.last_trace_id,
                    progress_reporter=progress_reporter,
                    runtime_context=runtime_context,
                )
            )
            turn_result = await pipeline.process(message)
            self.messages = pipeline.messages
            self.last_turn_result = turn_result
            self.last_workflow = turn_result.workflow
            logger.info(f'AutoGPT trace "{self.last_trace_id}" finished for user {self.user_id}')
            return turn_result
        except Exception as error:
            logger.exception(f'AutoGPT trace "{self.last_trace_id}" failed for user {self.user_id}: {error}')
            raise
        finally:
            self.lock = False

    def build_harness(
        self,
        *,
        trace_id: str = "",
        progress_reporter: ProgressReporter | None = None,
        runtime_context: RuntimeContext | None = None,
    ) -> AutoGPTHarness:
        """构建当前会话轮次使用的 Harness 分层依赖。"""

        return AutoGPTHarness.build(
            helpers=self.helpers,
            messages=self.messages,
            trace_id=trace_id or self.last_trace_id,
            progress_reporter=progress_reporter,
            runtime_context=runtime_context,
        )

    def record_observations(self, observations: list[CommandObservation], trace_id: str = "") -> None:
        """把命令执行观察写回会话，供下一轮规划参考。

        除投递状态外，也会记录命令实际发送给用户的回复文本，让下一轮
        Agent 能基于工具结果继续回答，而不是重复调用同一个命令。
        """
        if not observations:
            return
        payload = [observation.dict() for observation in observations]
        content = json.dumps(payload, ensure_ascii=False, default=str)
        self.messages.assistant_message(f"# 系统命令执行观察\ntrace_id: {trace_id or self.last_trace_id}\n{content}")

        output_sections = []
        for observation in observations:
            context_outputs = observation.context_outputs or observation.outputs
            if not context_outputs:
                continue
            outputs = "\n".join(f"- {output}" for output in context_outputs)
            output_sections.append(f"命令：{observation.command}\n{outputs}")
        if output_sections:
            self.messages.assistant_message(
                "# 系统命令返回结果\n" f"trace_id: {trace_id or self.last_trace_id}\n" + "\n\n".join(output_sections)
            )

    async def execute_task_workflow(
        self,
        workflow: TaskWorkflow,
        dispatcher: WorkflowDispatcher,
        *,
        trace_id: str = "",
    ) -> WorkflowExecutionResult:
        """执行 AI 任务流，并在同一轮把观察结果整理为最终回复。"""

        current_trace_id = trace_id or self.last_trace_id
        execution = await CognitiveAgentLoop(
            dispatcher,
            messages=self.messages,
            command_tools=CommandToolCatalog.from_helpers(self.helpers),
        ).execute(workflow)
        if execution.observations:
            self.record_observations(execution.observations, trace_id=current_trace_id)
        await self.record_workflow(execution.workflow, trace_id=current_trace_id)
        if execution.observations:
            execution.final_reply = await self.build_execution_final_reply(execution)
        if not execution.final_reply:
            execution.final_reply = execution.user_message
        return execution

    async def build_execution_final_reply(self, execution: WorkflowExecutionResult) -> str:
        """使用强模型把任务流执行结果总结成最终用户回复。"""

        try:
            snapshot = get_runtime_orchestration_snapshot()
            llm_name = snapshot.config.model_profiles.supervisor_model
            reply = await ExecutionReplyAgent(config=ExecutionReplyAgentConfig(llm_name=llm_name)).execute(
                self.messages,
                workflow=execution.workflow,
                observations=execution.observations,
                raw_outputs=execution.raw_outputs,
            )
            return reply or (execution.user_message or "")
        except Exception as error:
            logger.warning(f'AutoGPT trace "{self.last_trace_id}" execution reply synthesis failed: {error}')
            return execution.user_message or ""

    async def record_workflow(self, workflow: TaskWorkflow, trace_id: str = "") -> None:
        """把当前轮次的工作流状态写回会话。"""

        self.last_workflow = workflow
        if workflow_requires_confirmation(workflow) and workflow.status == "needs_confirm":
            self.pending_workflow = workflow.copy(deep=True)
        elif workflow.status in {"completed", "failed", "cancelled"} or not workflow.need_confirm:
            self.pending_workflow = None
        self.append_workflow_message(workflow, trace_id=trace_id)
        await self.workflow_checkpoint_store.save_workflow(self.user_id, workflow)
        await self.workflow_run_store.save_run(self.user_id, workflow)

    async def restore_pending_workflow(self) -> TaskWorkflow | None:
        """从持久化检查点恢复待确认工作流。"""

        if self.pending_workflow is not None:
            return self.pending_workflow

        workflow = await self.workflow_checkpoint_store.load_pending_workflow(self.user_id)
        if workflow is None:
            return None

        self.pending_workflow = workflow.copy(deep=True)
        self.last_workflow = workflow
        self.append_workflow_message(workflow, trace_id=workflow.trace_id)
        return self.pending_workflow

    async def resolve_pending_workflow_action(
        self,
        message: str | UniMessage | ChatMessage,
        trace_id: str = "",
    ) -> AgentTurnResult | None:
        """处理上一轮待确认工作流的继续执行或取消。"""

        if self.pending_workflow is None:
            return None

        contents = self.message_to_contents(message)
        decision = self.classify_pending_workflow_decision(contents)
        if decision is None:
            return None

        self.messages.user_message(contents)
        current_trace_id = trace_id or self.last_trace_id
        if decision == "cancel":
            cancelled_workflow = self.pending_workflow.copy(deep=True)
            cancelled_workflow.status = "cancelled"
            if cancelled_workflow.approval.required:
                cancelled_workflow.approval.status = "rejected"
                cancelled_workflow.add_event("approval_rejected", "用户取消了待确认工作流。", status="rejected")
            for step in cancelled_workflow.steps:
                if step.approval.required:
                    step.approval.status = "rejected"
            cancelled_workflow.add_event("workflow_cancelled", "工作流已取消。", status="cancelled")
            cancelled_workflow.finished_at = datetime.now()
            self.pending_workflow = None
            self.messages.assistant_message("已取消上一条待确认任务。")
            await self.record_workflow(cancelled_workflow, trace_id=current_trace_id)
            return AgentTurnResult(
                route=IntentRoute(intent="chat", reply="已取消上一条待确认任务。", reason="用户取消待确认工作流。"),
                auto_tasks=AutoTaskList(reply="已取消上一条待确认任务。"),
            )

        resumed_workflow = clone_workflow_for_execution(self.pending_workflow, trace_id=current_trace_id)
        self.pending_workflow = None
        reply = "好的，我继续为你处理。"
        self.messages.assistant_message(reply)
        self.last_workflow = resumed_workflow
        await self.workflow_checkpoint_store.save_workflow(self.user_id, resumed_workflow)
        await self.workflow_run_store.save_run(self.user_id, resumed_workflow)
        return AgentTurnResult(
            route=IntentRoute(
                intent="complex_task" if len(resumed_workflow.steps) > 1 else "command",
                requires_command=True,
                reply=reply,
                reason="用户确认执行待确认工作流。",
            ),
            auto_tasks=workflow_to_auto_tasks(resumed_workflow, reply=reply),
            workflow=resumed_workflow,
        )

    @staticmethod
    def message_to_contents(message: str | UniMessage | ChatMessage) -> list[Content]:
        """将消息统一转成内容列表。"""

        if isinstance(message, ChatMessage):
            return list(message.message)
        return uni_message_to_contents(message)

    @classmethod
    def classify_pending_workflow_decision(cls, contents: list[Content]) -> str | None:
        """判断用户是在确认、取消，还是在补充新的自然语言信息。"""

        text = cls.normalize_decision_text(contents)
        if not text or len(text) > 12:
            return None
        if any(pattern in text for pattern in CANCEL_PATTERNS):
            return "cancel"
        if any(pattern in text for pattern in CONFIRM_PATTERNS):
            return "confirm"
        return None

    @staticmethod
    def normalize_decision_text(contents: list[Content]) -> str:
        """提取用户文本内容并归一化为短确认语句。"""

        text = "".join(content.value for content in contents if content.type == "text")
        return re.sub(r"[\s,，。！？!?.；;:：~～、]", "", text).lower()

    def append_workflow_message(self, workflow: TaskWorkflow, trace_id: str = "") -> None:
        """把工作流快照写入会话消息，便于后续轮次继续引用。"""

        content = json.dumps(workflow.dict(), ensure_ascii=False, default=str)
        self.messages.assistant_message(
            f"# 系统工作流状态\ntrace_id: {trace_id or workflow.trace_id or self.last_trace_id}\n{content}"
        )

    async def clear(self) -> None:
        """从会话管理器中移除当前会话。"""
        await self.workflow_checkpoint_store.clear(self.user_id)
        self.pending_workflow = None
        self.last_workflow = None
        self.last_turn_result = None
        chat_session_manager.sessions.pop(self.user_id, None)


class ChatSessionManager:
    """管理聊天会话的生命周期、缓存与超时清理。"""

    timeout = 60 * 60

    def __init__(self) -> None:
        """初始化实例。"""
        self.sessions: dict[int, ChatSession] = {}

    def clear_timeout(self) -> None:
        """清理长时间未活动的会话。"""
        current_time = time()
        for session in list(self.sessions.values()):
            if current_time - session.update_time > self.timeout:
                del self.sessions[session.user_id]

    async def get_chat_session(self, user_id: int, helpers: Helpers) -> ChatSession:
        """获取用户会话，不存在则创建并刷新帮助上下文。

        参数:
            user_id (int): 当前用户标识。
            helpers (Helpers): 当前用户可见的帮助信息集合。

        返回:
            ChatSession: 已准备好系统提示词的聊天会话对象。
        """
        self.clear_timeout()

        if session := self.sessions.get(user_id):
            session.update_time = time()
        else:
            session = ChatSession(user_id, helpers)
        await session.update_helpers(helpers)
        self.sessions[user_id] = session
        return session


async def get_chat_session(user: UserOrCreatedDepends, helpers: HelpersDepends) -> ChatSession:
    """获取当前用户对应的聊天会话依赖对象。"""
    chat_session = await chat_session_manager.get_chat_session(user.id, helpers)
    return chat_session


ChatSessionDepends = Annotated[ChatSession, Depends(get_chat_session)]
chat_session_manager = ChatSessionManager()
