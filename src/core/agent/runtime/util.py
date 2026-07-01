import re
import json
import asyncio
from uuid import uuid4
from datetime import datetime
from time import time, perf_counter
from typing import Callable, Annotated, Awaitable

from nonebot import logger
from nonebot.params import Depends
from src.platform.helper import Helpers
from src.core.agent.prompts import Prompt
from nonebot_plugin_alconna import UniMessage
from src.core.mcp import MCPTool, MCPToolCatalog
from src.core.llm.util import uni_message_to_contents
from src.core.agent.builtin import ExecutionReplyAgent
from src.platform.helper.depends import HelpersDepends
from src.platform.session.depends import UserOrCreatedDepends
from src.core.storage import MessageActorRole, chat_history_store
from src.core.llm.message import Content, Context, LLMRole, Messages
from src.core.agent.builtin.conversation import ExecutionReplyAgentConfig

from .context import ContextPack
from .harness import AutoGPTHarness
from .formatting import preview_text
from .loop import CognitiveAgentLoop
from .knowledge import RuntimeContext
from .exception import SessionLockError
from .roles import RuntimeRoleTraceRecord
from .command_tools import CommandToolCatalog
from .pipeline import MessageProcessingPipeline
from .live_trace import agent_live_trace_registry
from .host import AgentHost, TurnEnvelope, TurnOutputBundle
from .observation_quality import build_safe_execution_fallback
from .persistence import WorkflowRunStore, WorkflowCheckpointStore
from .orchestration_config import get_runtime_orchestration_snapshot
from .workflow import (
    WorkflowDispatcher,
    workflow_to_auto_tasks,
    clone_workflow_for_execution,
    workflow_requires_confirmation,
)
from .schema import (
    ChatMessage,
    IntentRoute,
    ReplyRecord,
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


def preview_contents(contents: list[Content], limit: int = 180) -> str:
    """从内容列表中提取文本预览。"""

    text = "".join(content.value for content in contents if content.type == "text")
    if text.strip():
        return preview_text(text, limit=limit)
    return preview_text(f"[non-text contents x{len(contents)}]", limit=limit)


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
        self.last_turn_envelope: TurnEnvelope | None = None
        self.last_context_pack: ContextPack | None = None
        self.last_turn_output_bundle: TurnOutputBundle | None = None
        self.last_runtime_role_records: list[RuntimeRoleTraceRecord] = []
        self.last_mcp_tools = MCPToolCatalog()
        self.pending_workflow: TaskWorkflow | None = None
        self.history_backfilled = False
        self.workflow_checkpoint_store = WorkflowCheckpointStore()
        self.workflow_run_store = WorkflowRunStore()
        self.agent_host = AgentHost()

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

    async def backfill_recent_history(self, limit: int = 8, exclude_message_id: str | None = None) -> None:
        """会话首次创建时，从持久化聊天记录回填最近的人机对话。

        进程内 ``messages`` 在超时清理或重启后会丢失，导致同一用户隔一会儿
        再聊时，Agent 看不到上一段对话。这里在会话刚创建时，从 DB 拉取最近
        若干条用户/助手消息，压缩成一条带标记的助手备注注入上下文，让 Agent
        能承接跨会话记忆，同时不破坏正常的逐轮 user/assistant 结构。

        参数:
            limit (int): 最多回填多少条最近消息。
            exclude_message_id (str | None): 当前正在处理的消息 ID，避免被被动采集后又回填给模型。
        """

        if self.history_backfilled:
            return
        # 仅在“只有系统提示词、还没有任何对话”时回填，避免重复注入或污染在途会话。
        non_system = [message for message in self.messages.messages if getattr(message, "role", None) != LLMRole.system]
        if non_system:
            return
        self.history_backfilled = True
        try:
            records = await chat_history_store.search_user_chat_messages(
                self.user_id,
                None,
                limit=limit,
                exclude_message_id=exclude_message_id,
            )
        except Exception as error:
            logger.warning(f"AutoGPT history backfill failed for user {self.user_id}: {error}")
            return
        if not records:
            return
        lines: list[str] = []
        for record in records:
            speaker = "机器人" if record.actor_role == MessageActorRole.assistant else (record.user_name or "用户")
            text = preview_text(record.display_text, limit=200)
            if text:
                lines.append(f"[{record.created_at.strftime('%m-%d %H:%M')}] {speaker}: {text}")
        if not lines:
            return
        self.messages.assistant_message(
            "# 历史会话回填\n以下是该用户最近的人机对话，供承接上下文参考：\n" + "\n".join(lines)
        )
        logger.info(f"AutoGPT backfilled {len(lines)} history lines for user {self.user_id}")

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
            message_contents = self.message_to_contents(message)
            message_preview = preview_contents(message_contents, limit=120)
            agent_live_trace_registry.start_trace(
                self.last_trace_id,
                user_id=self.user_id,
                session_id=str(self.user_id),
                message_preview=message_preview,
            )
            self.last_turn_envelope = self.agent_host.create_turn_envelope(
                trace_id=self.last_trace_id,
                user_id=self.user_id,
                contents=message_contents,
                message_preview=message_preview,
                runtime_context=runtime_context,
                pending_workflow=self.pending_workflow,
            )
            await self.backfill_recent_history(
                exclude_message_id=runtime_context.message_id if runtime_context is not None else None
            )
            self.last_context_pack = self.agent_host.build_context_pack(self.last_turn_envelope, self)
            logger.info(f'AutoGPT trace "{self.last_trace_id}" started for user {self.user_id}')
            await self.restore_pending_workflow()
            self.last_context_pack = self.agent_host.build_context_pack(self.last_turn_envelope, self)
            if pending_result := await self.resolve_pending_workflow_action(message, trace_id=self.last_trace_id):
                self.last_turn_result = pending_result
                if pending_result.workflow is not None:
                    self.last_workflow = pending_result.workflow
                self.record_host_output(pending_result)
                self.record_direct_reply_from_host()
                logger.info(f'AutoGPT trace "{self.last_trace_id}" resumed pending workflow for user {self.user_id}')
                if pending_result.workflow is None or not pending_result.workflow.steps:
                    agent_live_trace_registry.emit(
                        self.last_trace_id,
                        event_type="reply_completed",
                        stage="reply",
                        status="completed",
                        observation_summary=preview_text(
                            pending_result.auto_tasks.reply if pending_result.auto_tasks else ""
                        ),
                    )
                    agent_live_trace_registry.finish_trace(self.last_trace_id, status="completed")
                return pending_result
            pipeline = MessageProcessingPipeline(
                harness=self.build_harness(
                    trace_id=self.last_trace_id,
                    progress_reporter=progress_reporter,
                    runtime_context=runtime_context,
                )
            )
            started = perf_counter()
            logger.info(
                f'AutoGPT trace "{self.last_trace_id}" pipeline processing started '
                f'message_preview="{message_preview}"'
            )
            turn_result = await pipeline.process(message)
            self.messages = pipeline.messages
            self.last_mcp_tools = pipeline.mcp_tools
            self.last_turn_result = turn_result
            self.last_workflow = turn_result.workflow
            self.record_host_output(turn_result)
            self.record_direct_reply_from_host()
            logger.info(
                f'AutoGPT trace "{self.last_trace_id}" pipeline processing finished '
                f"in {perf_counter() - started:.3f}s workflow={turn_result.workflow.kind if turn_result.workflow else None} "
                f"auto_tasks={len(turn_result.auto_tasks.tasks) if turn_result.auto_tasks else 0}"
            )
            logger.info(f'AutoGPT trace "{self.last_trace_id}" finished for user {self.user_id}')
            if turn_result.workflow is None or not turn_result.workflow.steps:
                agent_live_trace_registry.emit(
                    self.last_trace_id,
                    event_type="reply_completed",
                    stage="reply",
                    status="completed",
                    workflow_kind=turn_result.workflow.kind if turn_result.workflow else "",
                    observation_summary=preview_text(turn_result.auto_tasks.reply if turn_result.auto_tasks else ""),
                )
                agent_live_trace_registry.finish_trace(self.last_trace_id, status="completed")
            return turn_result
        except Exception as error:
            logger.exception(f'AutoGPT trace "{self.last_trace_id}" failed for user {self.user_id}: {error}')
            agent_live_trace_registry.finish_trace(self.last_trace_id, status="failed", error=error)
            raise
        finally:
            self.lock = False

    def record_host_output(self, turn_result: AgentTurnResult) -> TurnOutputBundle | None:
        """Build Host output artifacts for the latest turn and keep them inspectable."""

        if self.last_turn_envelope is None:
            return None
        if self.last_context_pack is None:
            self.last_context_pack = self.agent_host.build_context_pack(self.last_turn_envelope, self)
        bundle = self.agent_host.build_turn_output(
            envelope=self.last_turn_envelope,
            turn_result=turn_result,
            context_pack=self.last_context_pack,
        )
        self.last_turn_output_bundle = bundle
        self.last_runtime_role_records = list(bundle.runtime_roles)
        return bundle

    def user_visible_initial_reply(self, turn_result: AgentTurnResult | None = None) -> str:
        """Return the Host-approved initial user-visible reply for platform delivery."""

        bundle = self.last_turn_output_bundle
        if bundle is not None:
            preferred_order = ("failure_reply", "confirmation_message", "progress_message", "final_reply")
            for message_type in preferred_order:
                for message in bundle.reply.messages:
                    if message.message_type == message_type and message.text.strip():
                        return message.text.strip()
        auto_tasks = turn_result.auto_tasks if turn_result is not None else None
        return (auto_tasks.reply or "").strip() if auto_tasks is not None else ""

    def record_direct_reply_from_host(self) -> None:
        """Write Host-classified direct final replies into reply memory."""

        bundle = self.last_turn_output_bundle
        if bundle is None:
            return
        if bundle.decision.requires_execution or bundle.decision.requires_confirmation:
            return
        for message in bundle.reply.messages:
            if message.message_type == "final_reply" and message.write_to_history and message.text.strip():
                self.record_reply_record(message.text, trace_id=bundle.trace_id)
                return

    def record_reply_record(
        self,
        reply: str,
        *,
        trace_id: str = "",
        source_observations: list[str] | None = None,
    ) -> None:
        """Persist a compact final reply record for follow-up turns."""

        text = reply.strip()
        if not text:
            return
        current_trace_id = trace_id or self.last_trace_id
        record = ReplyRecord(
            trace_id=current_trace_id,
            reply=text,
            summary=preview_text(text, limit=500),
            source_observations=source_observations or [],
        )
        marker = f"# 系统最终回复记录\ntrace_id: {current_trace_id}\n"
        if any(marker in message.single_modal() for message in self.messages.messages):
            return
        self.messages.assistant_message(marker + json.dumps(record.model_dump(), ensure_ascii=False, default=str))

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
        current_trace_id = trace_id or self.last_trace_id
        logger.info(
            f'AutoGPT trace "{current_trace_id}" recording {len(observations)} observations '
            f"commands={[observation.command for observation in observations]}"
        )
        payload = [observation.model_dump() for observation in observations]
        content = json.dumps(payload, ensure_ascii=False, default=str)
        self.messages.assistant_message(f"# 系统命令执行观察\ntrace_id: {current_trace_id}\n{content}")

        output_sections = []
        for observation in observations:
            agent_live_trace_registry.emit(
                current_trace_id,
                event_type="observation_recorded",
                stage="loop",
                status="completed" if observation.success else "failed",
                step_id="",
                tool_name=observation.tool_name or observation.command,
                params_preview={
                    "source_type": observation.source_type,
                    "status": observation.status,
                    "relevance": observation.relevance,
                    "answer_quality": observation.answer_quality,
                    "query": observation.query,
                },
                observation_summary=observation.display_summary or observation.context_summary or observation.message,
            )
            context_outputs = observation.context_outputs or (
                [observation.context_summary] if observation.context_summary else []
            )
            if not context_outputs and observation.display_summary:
                context_outputs = [observation.display_summary]
            if not context_outputs:
                context_outputs = observation.outputs
            if not context_outputs:
                continue
            outputs = "\n".join(f"- {output}" for output in context_outputs)
            tool_name = observation.tool_name or observation.command
            label = "工具" if observation.source_type != "command" else "命令"
            output_sections.append(f"{label}：{tool_name}\n{outputs}")
        if output_sections:
            self.messages.assistant_message(
                "# 系统命令返回结果\n" f"trace_id: {current_trace_id}\n" + "\n\n".join(output_sections)
            )

    async def execute_task_workflow(
        self,
        workflow: TaskWorkflow,
        dispatcher: WorkflowDispatcher,
        *,
        trace_id: str = "",
        progress_reporter: ProgressReporter | None = None,
    ) -> WorkflowExecutionResult:
        """执行 AI 任务流，并在同一轮把观察结果整理为最终回复。"""

        current_trace_id = trace_id or self.last_trace_id
        agent_live_trace_registry.emit(
            current_trace_id,
            event_type="workflow_started",
            stage="workflow",
            status="running",
            workflow_kind=workflow.kind,
            params_preview={
                "status": workflow.status,
                "steps": len(workflow.steps),
                "need_confirm": workflow.need_confirm,
                "goal": workflow.goal,
            },
        )
        logger.info(
            f'AutoGPT trace "{current_trace_id}" execute_task_workflow started '
            f"workflow_kind={workflow.kind} status={workflow.status} steps={len(workflow.steps)}"
        )
        loop_started = perf_counter()
        execution = await CognitiveAgentLoop(
            dispatcher,
            messages=self.messages,
            command_tools=CommandToolCatalog.from_helpers(self.helpers),
            mcp_tools=self.build_workflow_mcp_catalog(workflow),
            progress_reporter=progress_reporter,
        ).execute(workflow)
        logger.info(
            f'AutoGPT trace "{current_trace_id}" loop execution finished in {perf_counter() - loop_started:.3f}s '
            f"status={execution.workflow.status} observations={len(execution.observations)} "
            f'user_message_preview="{preview_text(execution.user_message)}"'
        )
        agent_live_trace_registry.emit(
            current_trace_id,
            event_type="loop_execution_completed",
            stage="loop",
            status=execution.workflow.status,
            workflow_kind=execution.workflow.kind,
            params_preview={
                "observations": len(execution.observations),
                "workflow_status": execution.workflow.status,
                "user_message": preview_text(execution.user_message),
            },
            duration_ms=(perf_counter() - loop_started) * 1000,
        )
        if execution.observations:
            record_started = perf_counter()
            logger.info(f'AutoGPT trace "{current_trace_id}" recording execution observations')
            self.record_observations(execution.observations, trace_id=current_trace_id)
            logger.info(
                f'AutoGPT trace "{current_trace_id}" recorded execution observations in {perf_counter() - record_started:.3f}s'
            )
        workflow_record_started = perf_counter()
        logger.info(
            f'AutoGPT trace "{current_trace_id}" persisting workflow status={execution.workflow.status} '
            f"need_confirm={execution.workflow.need_confirm}"
        )
        agent_live_trace_registry.emit(
            current_trace_id,
            event_type="persist_started",
            stage="persist",
            status="running",
            workflow_kind=execution.workflow.kind,
            params_preview={"workflow_status": execution.workflow.status},
        )
        await self.record_workflow(execution.workflow, trace_id=current_trace_id)
        logger.info(
            f'AutoGPT trace "{current_trace_id}" persisted workflow in {perf_counter() - workflow_record_started:.3f}s'
        )
        agent_live_trace_registry.emit(
            current_trace_id,
            event_type="persist_completed",
            stage="persist",
            status="completed",
            workflow_kind=execution.workflow.kind,
            duration_ms=(perf_counter() - workflow_record_started) * 1000,
        )
        if execution.observations:
            if progress_reporter is not None:
                await progress_reporter("我正在整理检索和执行结果，马上给你结论。")
            reply_started = perf_counter()
            logger.info(f'AutoGPT trace "{current_trace_id}" building execution final reply')
            agent_live_trace_registry.emit(
                current_trace_id,
                event_type="reply_started",
                stage="reply",
                status="running",
                workflow_kind=execution.workflow.kind,
                params_preview={"observations": len(execution.observations)},
            )
            execution.final_reply = await self.build_execution_final_reply_with_timeout(execution)
            logger.info(
                f'AutoGPT trace "{current_trace_id}" built execution final reply in {perf_counter() - reply_started:.3f}s '
                f'final_reply_preview="{preview_text(execution.final_reply)}"'
            )
            agent_live_trace_registry.emit(
                current_trace_id,
                event_type="reply_completed",
                stage="reply",
                status="completed",
                workflow_kind=execution.workflow.kind,
                observation_summary=preview_text(execution.final_reply),
                duration_ms=(perf_counter() - reply_started) * 1000,
            )
        if not execution.final_reply:
            execution.final_reply = execution.user_message or build_safe_execution_fallback(execution.observations)
            logger.info(
                f'AutoGPT trace "{current_trace_id}" using execution user_message as final reply '
                f'preview="{preview_text(execution.final_reply)}"'
            )
        if execution.final_reply:
            self.record_final_reply(execution.final_reply, execution, trace_id=current_trace_id)
        agent_live_trace_registry.finish_trace(
            current_trace_id,
            status="completed" if execution.workflow.status != "failed" else "failed",
        )
        return execution

    def build_workflow_mcp_catalog(self, workflow: TaskWorkflow) -> MCPToolCatalog:
        """根据当前工作流步骤构造最小 MCP 能力目录，避免执行期再重复拉取目录。"""

        catalog = MCPToolCatalog()
        for step in workflow.steps:
            if step.step_type != "mcp_tool" or not step.command or catalog.get(step.command) is not None:
                continue
            tool = self.last_mcp_tools.get(step.command)
            if tool is not None:
                catalog.append(tool.model_copy(deep=True))
                continue
            catalog.append(MCPTool(name=step.command, description=step.description or step.title))
        return catalog

    async def build_execution_final_reply_with_timeout(self, execution: WorkflowExecutionResult) -> str:
        """在有限时间内生成最终回复，超时则回退到已有结果。"""

        try:
            return await asyncio.wait_for(self.build_execution_final_reply(execution), timeout=8.0)
        except asyncio.TimeoutError:
            logger.warning(f'AutoGPT trace "{self.last_trace_id}" execution reply synthesis timed out')
            return build_safe_execution_fallback(execution.observations)

    async def build_execution_final_reply(self, execution: WorkflowExecutionResult) -> str:
        """使用强模型把任务流执行结果总结成最终用户回复。"""

        try:
            snapshot = get_runtime_orchestration_snapshot()
            llm_name = snapshot.config.model_profiles.supervisor_model
            started = perf_counter()
            logger.info(
                f'AutoGPT trace "{self.last_trace_id}" execution reply synthesis started '
                f'model="{llm_name}" observations={len(execution.observations)} raw_outputs={len(execution.raw_outputs)}'
            )
            reply = await ExecutionReplyAgent(config=ExecutionReplyAgentConfig(llm_name=llm_name)).execute(
                self.messages,
                workflow=execution.workflow,
                observations=execution.observations,
                raw_outputs=execution.raw_outputs,
            )
            logger.info(
                f'AutoGPT trace "{self.last_trace_id}" execution reply synthesis finished '
                f'in {perf_counter() - started:.3f}s preview="{preview_text(reply)}"'
            )
            return reply or (execution.user_message or "")
        except Exception as error:
            logger.warning(f'AutoGPT trace "{self.last_trace_id}" execution reply synthesis failed: {error}')
            return build_safe_execution_fallback(execution.observations)

    def record_final_reply(
        self,
        reply: str,
        execution: WorkflowExecutionResult,
        *,
        trace_id: str = "",
    ) -> None:
        """把用户真实看到的最终回复写回会话，供下一轮追问承接。"""

        text = reply.strip()
        if not text:
            return
        current_trace_id = trace_id or self.last_trace_id
        record = ReplyRecord(
            trace_id=current_trace_id,
            reply=text,
            summary=preview_text(text, limit=500),
            source_observations=[
                observation.tool_name or observation.command
                for observation in execution.observations
                if observation.tool_name or observation.command
            ],
        )
        self.record_reply_record(
            text,
            trace_id=current_trace_id,
            source_observations=record.source_observations,
        )
        self.messages.assistant_message(text)

    async def record_workflow(self, workflow: TaskWorkflow, trace_id: str = "") -> None:
        """把当前轮次的工作流状态写回会话。"""

        current_trace_id = trace_id or workflow.trace_id or self.last_trace_id
        self.last_workflow = workflow
        if workflow_requires_confirmation(workflow) and workflow.status == "needs_confirm":
            self.pending_workflow = workflow.model_copy(deep=True)
        elif workflow.status in {"completed", "failed", "cancelled"} or not workflow.need_confirm:
            self.pending_workflow = None
        logger.info(
            f'AutoGPT trace "{current_trace_id}" record_workflow status={workflow.status} '
            f"kind={workflow.kind} steps={len(workflow.steps)} pending={self.pending_workflow is not None}"
        )
        self.append_workflow_message(workflow, trace_id=trace_id)
        checkpoint_started = perf_counter()
        await self.workflow_checkpoint_store.save_workflow(self.user_id, workflow)
        logger.info(
            f'AutoGPT trace "{current_trace_id}" saved workflow checkpoint in {perf_counter() - checkpoint_started:.3f}s'
        )
        run_started = perf_counter()
        await self.workflow_run_store.save_run(self.user_id, workflow)
        logger.info(f'AutoGPT trace "{current_trace_id}" saved workflow run in {perf_counter() - run_started:.3f}s')

    async def restore_pending_workflow(self) -> TaskWorkflow | None:
        """从持久化检查点恢复待确认工作流。"""

        if self.pending_workflow is not None:
            return self.pending_workflow

        workflow = await self.workflow_checkpoint_store.load_pending_workflow(self.user_id)
        if workflow is None:
            return None

        self.pending_workflow = workflow.model_copy(deep=True)
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
            cancelled_workflow = self.pending_workflow.model_copy(deep=True)
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

        content = json.dumps(workflow.model_dump(), ensure_ascii=False, default=str)
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
            await session.update_helpers(helpers)
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
