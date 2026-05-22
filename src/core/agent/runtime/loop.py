import json
import os
import time
from datetime import datetime
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from nonebot import logger
from pydantic import BaseModel, Extra, Field, validator

from src.shared.template import Prompt
from src.core.llm import LLMTaskType, client_create
from src.core.llm.message import Messages
from src.core.llm.util import json_loads

from .command_tools import CommandToolCatalog
from .schema import (
    Param,
    AutoTask,
    RiskLevel,
    WorkflowStep,
    TaskWorkflow,
    WorkflowApproval,
    CommandObservation,
    WorkflowExecutionResult,
)
from .workflow import (
    WorkflowDispatcher,
    update_execution_metrics,
    collect_unsent_observation_outputs,
)

LoopActionType = Literal["command", "verify", "skill", "confirm", "respond", "schedule", "finish", "stop"]
LoopStopReason = Literal[
    "max_steps",
    "max_verify_attempts",
    "max_repeat_actions",
    "max_runtime_seconds",
    "invalid_decision",
    "finished",
]


class AgentLoopConfig(BaseModel):
    """Agent 观察驱动循环的硬预算配置。

    这些值来自 `.env` 的启动级配置，由代码强制执行。Prompt 可以看到
    预算，但不能绕过预算。
    """

    class Config:
        extra = Extra.ignore
        allow_population_by_field_name = True

    max_steps: int = Field(default=8, alias="agent_loop_max_steps")
    max_verify_attempts: int = Field(default=3, alias="agent_loop_max_verify_attempts")
    max_repeat_actions: int = Field(default=2, alias="agent_loop_max_repeat_actions")
    max_runtime_seconds: int = Field(default=120, alias="agent_loop_max_runtime_seconds")

    @validator("max_steps", "max_verify_attempts", "max_repeat_actions", "max_runtime_seconds", pre=True)
    def normalize_positive_int(cls, value: object) -> int:
        """把环境变量里的字符串转成正整数，非法值回退到字段默认值。"""

        try:
            parsed = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0
        return max(parsed, 0)

    @classmethod
    def from_runtime(cls) -> "AgentLoopConfig":
        """从 NoneBot 配置和进程环境读取循环锁配置。"""

        data: dict[str, Any] = {}
        try:
            from nonebot import get_driver

            driver_config = get_driver().config
            for key in (
                "agent_loop_max_steps",
                "agent_loop_max_verify_attempts",
                "agent_loop_max_repeat_actions",
                "agent_loop_max_runtime_seconds",
            ):
                value = getattr(driver_config, key, None)
                if value is not None:
                    data[key] = value
        except Exception:
            pass

        env_key_map = {
            "AGENT_LOOP_MAX_STEPS": "agent_loop_max_steps",
            "AGENT_LOOP_MAX_VERIFY_ATTEMPTS": "agent_loop_max_verify_attempts",
            "AGENT_LOOP_MAX_REPEAT_ACTIONS": "agent_loop_max_repeat_actions",
            "AGENT_LOOP_MAX_RUNTIME_SECONDS": "agent_loop_max_runtime_seconds",
        }
        for env_key, config_key in env_key_map.items():
            if env_key in os.environ:
                data[config_key] = os.environ[env_key]
        config = cls.parse_obj(data)
        return config.with_safe_defaults()

    def with_safe_defaults(self) -> "AgentLoopConfig":
        """避免把非正数配置成无限循环或不可用循环。"""

        defaults = type(self)()
        values = self.dict()
        for field_name, value in values.items():
            if value <= 0:
                values[field_name] = getattr(defaults, field_name)
        return type(self)(**values)


class AgentLoopDecision(BaseModel):
    """单轮 observe-reason-act 循环产生的可审计动作摘要。"""

    action_type: LoopActionType = "finish"
    capability_name: str = ""
    params: list[Param] = Field(default_factory=list)
    reason: str = ""
    verify_target: str = ""
    stop_condition: str = ""

    @classmethod
    def from_step(cls, step: WorkflowStep) -> "AgentLoopDecision":
        """把已有 TaskWorkflow 步骤提升成循环动作。"""

        return cls(
            action_type="command",
            capability_name=step.command,
            params=list(step.params),
            reason=step.description or step.title,
        )

    @classmethod
    def stop(cls, reason: str, *, stop_condition: str = "") -> "AgentLoopDecision":
        """构造一个停止动作。"""

        return cls(action_type="stop", reason=reason, stop_condition=stop_condition or reason)


class ObservationFact(BaseModel):
    """把命令观察转成 Agent 更容易消费的结构化事实。"""

    success: bool
    entity_type: str | None = None
    entity_name: str | None = None
    exists: bool | None = None
    changed: bool = False
    verified: bool = False
    summary: str = ""
    suggested_next_actions: list[str] = Field(default_factory=list)


class CapabilityCatalog(BaseModel):
    """Agent Loop 可消费的能力目录。

    第一版先承接 command 能力；skill、RAG、schedule 后续可以按同一
    目录契约加入，而不用改变循环预算和 observation 结构。
    """

    command_tools: CommandToolCatalog = Field(default_factory=CommandToolCatalog)

    @classmethod
    def from_commands(cls, command_tools: CommandToolCatalog) -> "CapabilityCatalog":
        """从当前用户可见的命令工具目录构造能力目录。"""

        return cls(command_tools=command_tools)

    def get_command_risk(self, command: str) -> RiskLevel:
        """返回命令风险等级，未知命令默认中风险。"""

        tool = self.command_tools.get(command)
        return tool.risk_level if tool else "medium"

    def has_command(self, command: str) -> bool:
        """判断命令是否在当前可见且可执行的能力目录中。"""

        return self.command_tools.get(command) is not None

    def to_prompt(self) -> str:
        """渲染给决策 Prompt 的能力目录。"""

        return self.command_tools.to_prompt()


class LoopBudget:
    """运行期循环预算锁，负责硬性阻断重复调用和无限验证。"""

    def __init__(self, config: AgentLoopConfig | None = None) -> None:
        self.config = config or AgentLoopConfig.from_runtime()
        self.started_at = time.monotonic()
        self.steps_used = 0
        self.verify_attempts: dict[str, int] = defaultdict(int)
        self.repeat_actions: dict[str, int] = defaultdict(int)
        self.stop_reason: LoopStopReason | None = None
        self.stop_message = ""

    def check(self, decision: AgentLoopDecision) -> str | None:
        """返回阻断原因；没有阻断时返回 None。"""

        if self.elapsed_seconds() > self.config.max_runtime_seconds:
            return self.mark_stop(
                "max_runtime_seconds",
                f"运行时间已超过 {self.config.max_runtime_seconds} 秒，我先停止继续消耗资源。",
            )
        if self.steps_used >= self.config.max_steps:
            return self.mark_stop(
                "max_steps",
                f"本轮最多执行 {self.config.max_steps} 步，我已经到达上限。",
            )
        verify_target = self.verify_target_key(decision)
        if verify_target and self.verify_attempts[verify_target] >= self.config.max_verify_attempts:
            return self.mark_stop(
                "max_verify_attempts",
                f"同一目标最多验证 {self.config.max_verify_attempts} 次，我仍然无法确认结果。",
            )
        action_key = self.action_key(decision)
        if self.repeat_actions[action_key] >= self.config.max_repeat_actions:
            return self.mark_stop(
                "max_repeat_actions",
                f"同一个动作最多重复 {self.config.max_repeat_actions} 次，我先停止避免循环调用。",
            )
        return None

    def consume(self, decision: AgentLoopDecision) -> None:
        """记录一次即将执行的循环动作。"""

        self.steps_used += 1
        self.repeat_actions[self.action_key(decision)] += 1
        verify_target = self.verify_target_key(decision)
        if verify_target:
            self.verify_attempts[verify_target] += 1

    def mark_stop(self, reason: LoopStopReason, message: str) -> str:
        """记录停止原因并返回面向调用方的说明。"""

        self.stop_reason = reason
        self.stop_message = message
        return message

    def elapsed_seconds(self) -> float:
        """返回本轮循环已运行的秒数。"""

        return time.monotonic() - self.started_at

    def snapshot(self) -> dict[str, Any]:
        """生成可放入 prompt 或测试断言的预算快照。"""

        return {
            "max_steps": self.config.max_steps,
            "steps_used": self.steps_used,
            "max_verify_attempts": self.config.max_verify_attempts,
            "verify_attempts": dict(self.verify_attempts),
            "max_repeat_actions": self.config.max_repeat_actions,
            "repeat_actions": dict(self.repeat_actions),
            "max_runtime_seconds": self.config.max_runtime_seconds,
            "elapsed_seconds": round(self.elapsed_seconds(), 3),
            "stop_reason": self.stop_reason,
            "stop_message": self.stop_message,
        }

    @classmethod
    def action_key(cls, decision: AgentLoopDecision) -> str:
        """把动作归一化为重复调用检测键。"""

        params = [param.dict() for param in decision.params]
        return json.dumps(
            {
                "action_type": decision.action_type,
                "capability_name": decision.capability_name,
                "params": params,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

    @staticmethod
    def verify_target_key(decision: AgentLoopDecision) -> str:
        """解析验证目标键。"""

        if decision.action_type != "verify" and not decision.verify_target:
            return ""
        if decision.verify_target:
            return decision.verify_target
        return decision.capability_name


class ObservationInterpreter:
    """把命令结果解释成领域无关事实，避免任务专用分支。"""

    absence_patterns = (
        "没有找到",
        "未找到",
        "不存在",
        "暂无",
        "没有查询到",
        "未查询到",
        "not found",
        "does not exist",
        "no record",
        "no records",
    )
    write_words = (
        "创建",
        "添加",
        "删除",
        "修改",
        "更新",
        "发布",
        "绑定",
        "取消",
        "提交",
        "保存",
        "导入",
        "create",
        "add",
        "delete",
        "update",
        "publish",
        "bind",
        "submit",
        "save",
        "import",
    )
    read_words = (
        "查询",
        "查看",
        "获取",
        "我的",
        "列出",
        "统计",
        "搜索",
        "query",
        "search",
        "list",
        "get",
        "find",
    )

    def interpret_many(self, observations: list[CommandObservation]) -> list[ObservationFact]:
        """批量解释命令观察。"""

        return [self.interpret(observation) for observation in observations]

    def interpret(self, observation: CommandObservation) -> ObservationFact:
        """解释单条命令观察。"""

        text = self.observation_text(observation)
        lowered = text.lower()
        exists = self.infer_exists(observation, lowered)
        changed = observation.success and self.command_contains(observation.command, self.write_words)
        verified = observation.success and self.command_contains(observation.command, self.read_words) and exists is not False
        actions = self.suggest_next_actions(
            success=observation.success,
            exists=exists,
            changed=changed,
            verified=verified,
        )
        return ObservationFact(
            success=observation.success,
            entity_type=self.infer_entity_type(observation.command),
            entity_name=self.infer_entity_name(observation),
            exists=exists,
            changed=changed,
            verified=verified,
            summary=self.compact_summary(observation, text),
            suggested_next_actions=actions,
        )

    def infer_exists(self, observation: CommandObservation, lowered_text: str) -> bool | None:
        """从通用否定模式和查询语义中推断实体是否存在。"""

        if not observation.success:
            return None
        if any(pattern in lowered_text for pattern in self.absence_patterns):
            return False
        if self.command_contains(observation.command, self.read_words):
            return True if lowered_text.strip() else None
        return None

    @staticmethod
    def observation_text(observation: CommandObservation) -> str:
        """拼出可供事实提取的观察文本。"""

        parts = [observation.message, *observation.context_outputs, *observation.outputs]
        return "\n".join(part for part in parts if part).strip()

    @staticmethod
    def command_contains(command: str, words: tuple[str, ...]) -> bool:
        """判断命令名是否包含某类通用动作词。"""

        command_lower = command.lower()
        return any(word in command_lower for word in words)

    @classmethod
    def infer_entity_type(cls, command: str) -> str | None:
        """从命令名粗略提取实体类型，不绑定具体业务域。"""

        entity = command
        for word in (*cls.write_words, *cls.read_words):
            entity = entity.replace(word, "")
        entity = entity.strip(" ：:，,。 ")
        return entity or None

    @staticmethod
    def infer_entity_name(observation: CommandObservation) -> str | None:
        """从参数中提取一个最可能代表实体名称的值。"""

        for param in observation.params:
            value = str(param.value).strip()
            if value:
                return value[:80]
        return None

    @staticmethod
    def compact_summary(observation: CommandObservation, text: str) -> str:
        """生成短摘要，避免 observation 被大段输出淹没。"""

        if text:
            return text[:300]
        return "命令执行成功。" if observation.success else "命令执行失败。"

    @staticmethod
    def suggest_next_actions(
        *,
        success: bool,
        exists: bool | None,
        changed: bool,
        verified: bool,
    ) -> list[str]:
        """给模型提供领域无关的下一步提示。"""

        if not success:
            return ["retry", "ask_user"]
        if changed:
            return ["verify", "finish"]
        if exists is False:
            return ["create_or_update", "ask_user", "finish"]
        if verified:
            return ["finish"]
        return ["finish"]


DecisionProvider = Callable[
    [TaskWorkflow, list[WorkflowStep], list[CommandObservation], list[ObservationFact], LoopBudget],
    Awaitable[AgentLoopDecision],
]


class CognitiveAgentLoop:
    """通用观察驱动循环执行器。

    它不关心“任务、班级、通知”等具体业务，只执行通用闭环：
    选择能力 -> 执行 -> 读取 observation -> 更新事实 -> 检查预算 -> 继续或停止。
    """

    def __init__(
        self,
        dispatcher: WorkflowDispatcher,
        *,
        messages: Messages | None = None,
        command_tools: CommandToolCatalog | None = None,
        config: AgentLoopConfig | None = None,
        decision_provider: DecisionProvider | None = None,
        observation_interpreter: ObservationInterpreter | None = None,
    ) -> None:
        self.dispatcher = dispatcher
        self.messages = messages or Messages()
        self.capabilities = CapabilityCatalog.from_commands(command_tools or CommandToolCatalog())
        self.config = config or AgentLoopConfig.from_runtime()
        self.decision_provider = decision_provider
        self.observation_interpreter = observation_interpreter or ObservationInterpreter()

    async def execute(self, workflow: TaskWorkflow) -> WorkflowExecutionResult:
        """按观察驱动循环执行任务流。"""

        if workflow.need_confirm or workflow.status == "needs_confirm":
            workflow.add_event("approval_requested", "工作流仍在等待用户确认，暂不执行。", status="pending")
            logger.info(f'AutoGPT trace "{workflow.trace_id}" workflow requires confirmation before execution')
            return WorkflowExecutionResult(workflow=workflow, observability=workflow.observability)

        if not workflow.steps:
            return self.complete_without_steps(workflow)

        workflow.status = "running"
        workflow.started_at = datetime.now()
        workflow.add_event("workflow_started", "观察驱动循环开始执行。", status="running")
        result = WorkflowExecutionResult(workflow=workflow, observability=workflow.observability)
        budget = LoopBudget(self.config)
        pending_steps = list(workflow.steps)
        facts: list[ObservationFact] = []

        while True:
            decision = await self.decide_next_action(workflow, pending_steps, result.observations, facts, budget)
            if decision.action_type in {"finish", "respond"}:
                workflow.status = "completed"
                workflow.finished_at = datetime.now()
                workflow.add_event("workflow_completed", decision.reason or "任务流已完成。", status="completed")
                break
            if decision.action_type == "stop":
                self.apply_budget_stop(workflow, result, budget, decision.stop_condition or decision.reason)
                break
            if decision.action_type == "confirm":
                self.apply_decision_confirmation_stop(workflow, result, decision)
                break

            blocked_reason = budget.check(decision)
            if blocked_reason:
                self.apply_budget_stop(workflow, result, budget, blocked_reason)
                break
            budget.consume(decision)

            step = self.resolve_step_for_decision(workflow, pending_steps, decision)
            if step is None:
                self.apply_invalid_decision_stop(workflow, result, decision)
                break
            if self.requires_confirmation(step, decision):
                self.apply_confirmation_stop(workflow, result, step)
                break
            if step.step_type != "command" or decision.action_type not in {"command", "verify"}:
                self.apply_unsupported_step_stop(workflow, result, step, decision)
                break

            observations = await self.execute_command_step(workflow, step, decision)
            result.observations.extend(observations)
            facts.extend(self.observation_interpreter.interpret_many(observations))
            if self.has_failed_observation(workflow, result, step, observations):
                break

        result.raw_outputs = collect_unsent_observation_outputs(result.observations)
        if result.raw_outputs and not result.user_message:
            result.user_message = "\n\n".join(result.raw_outputs)
        update_execution_metrics(workflow, result.observations)
        result.observability = workflow.observability
        return result

    async def decide_next_action(
        self,
        workflow: TaskWorkflow,
        pending_steps: list[WorkflowStep],
        observations: list[CommandObservation],
        facts: list[ObservationFact],
        budget: LoopBudget,
    ) -> AgentLoopDecision:
        """选择下一步动作，优先使用外部决策器，其次使用通用默认策略。"""

        if self.decision_provider is not None:
            return await self.decision_provider(workflow, pending_steps, observations, facts, budget)
        if pending_steps:
            return AgentLoopDecision.from_step(pending_steps[0])
        if self.should_ask_model_for_followup(facts):
            return await self.decide_with_llm(workflow, pending_steps, observations, facts, budget)
        return AgentLoopDecision(action_type="finish", reason="已有任务步骤执行完成。")

    def should_ask_model_for_followup(self, facts: list[ObservationFact]) -> bool:
        """判断是否值得让模型基于 observation 再决定下一步。"""

        if not facts:
            return False
        latest = facts[-1]
        if not latest.success:
            return False
        if latest.verified:
            return False
        if "verify" in latest.suggested_next_actions and self.capabilities.command_tools:
            return True
        if "create_or_update" in latest.suggested_next_actions and self.capabilities.command_tools:
            return True
        return False

    async def decide_with_llm(
        self,
        workflow: TaskWorkflow,
        pending_steps: list[WorkflowStep],
        observations: list[CommandObservation],
        facts: list[ObservationFact],
        budget: LoopBudget,
    ) -> AgentLoopDecision:
        """让监督模型基于 observation 和能力目录给出下一步动作。"""

        try:
            prompt = await Prompt("agent_loop_decision").render(
                {
                    "workflow": json.dumps(workflow.dict(), ensure_ascii=False, default=str),
                    "pending_steps": json.dumps([step.dict() for step in pending_steps], ensure_ascii=False, default=str),
                    "observations": json.dumps(
                        [observation.dict() for observation in observations[-6:]],
                        ensure_ascii=False,
                        default=str,
                    ),
                    "facts": json.dumps([fact.dict() for fact in facts[-6:]], ensure_ascii=False, default=str),
                    "capabilities": self.capabilities.to_prompt(),
                    "budget": json.dumps(budget.snapshot(), ensure_ascii=False, default=str),
                }
            )
            messages = Messages()
            messages.system_message(prompt)
            response = await client_create(
                messages,
                multi_modal=False,
                max_tokens=1024,
                task_type=LLMTaskType.plan,
                llm_name=self.resolve_supervisor_model_name(),
            )
            content = response.choices[0].message.content or "{}"
            return self.normalize_model_decision(AgentLoopDecision.parse_obj(json_loads(content)))
        except Exception as error:
            logger.warning(f'AutoGPT trace "{workflow.trace_id}" loop decision failed: {error}')
            return AgentLoopDecision(action_type="finish", reason="无法可靠生成下一步动作，基于已有观察结束。")

    @staticmethod
    def resolve_supervisor_model_name() -> str | None:
        """读取运行时编排图中给循环决策绑定的监督模型。"""

        try:
            from .orchestration_config import get_runtime_orchestration_snapshot

            return get_runtime_orchestration_snapshot().config.model_profiles.supervisor_model
        except Exception:
            return None

    def normalize_model_decision(self, decision: AgentLoopDecision) -> AgentLoopDecision:
        """校验模型动作不越过当前能力目录。"""

        if decision.action_type in {"command", "verify"} and not self.capabilities.has_command(decision.capability_name):
            return AgentLoopDecision.stop(
                f"模型选择的能力 `{decision.capability_name}` 不在当前可执行目录中。",
                stop_condition="invalid_capability",
            )
        return decision

    def resolve_step_for_decision(
        self,
        workflow: TaskWorkflow,
        pending_steps: list[WorkflowStep],
        decision: AgentLoopDecision,
    ) -> WorkflowStep | None:
        """把循环动作映射为工作流步骤。"""

        if pending_steps:
            step = pending_steps.pop(0)
            if step.command == decision.capability_name:
                return step
            pending_steps.insert(0, step)
        if not decision.capability_name:
            return None
        if decision.action_type in {"command", "verify"} and not self.capabilities.has_command(decision.capability_name):
            return None

        step = WorkflowStep(
            step_id=f"loop-step-{len(workflow.steps) + 1}",
            step_type="command",
            title=f"循环调用：{decision.capability_name}",
            command=decision.capability_name,
            params=list(decision.params),
            description=decision.reason,
            risk_level=self.capabilities.get_command_risk(decision.capability_name),
        )
        workflow.steps.append(step)
        return step

    def requires_confirmation(self, step: WorkflowStep, decision: AgentLoopDecision) -> bool:
        """判断动态动作是否需要确认。"""

        return step.risk_level == "high" or decision.action_type == "confirm"

    def apply_confirmation_stop(
        self,
        workflow: TaskWorkflow,
        result: WorkflowExecutionResult,
        step: WorkflowStep,
    ) -> None:
        """把高风险或显式确认动作转为待确认状态。"""

        step.status = "pending"
        step.approval = WorkflowApproval(
            required=True,
            type="high_risk" if step.risk_level == "high" else "user_confirm",
            status="pending",
            reason="循环决策命中了需要用户确认的操作。",
            prompt=f"接下来需要执行「{step.command}」，是否确认继续？",
            risk_level=step.risk_level,
        )
        workflow.need_confirm = True
        workflow.status = "needs_confirm"
        workflow.add_event(
            "approval_requested",
            step.approval.prompt,
            step_id=step.step_id,
            command=step.command,
            status="pending",
        )
        result.user_message = step.approval.prompt

    @staticmethod
    def apply_decision_confirmation_stop(
        workflow: TaskWorkflow,
        result: WorkflowExecutionResult,
        decision: AgentLoopDecision,
    ) -> None:
        """处理模型明确提出的追问或确认动作。"""

        prompt = decision.reason or "这个操作需要你确认或补充信息后我再继续。"
        workflow.need_confirm = True
        workflow.status = "needs_confirm"
        workflow.approval = WorkflowApproval(
            required=True,
            type="user_confirm",
            status="pending",
            reason=prompt,
            prompt=prompt,
            risk_level="low",
        )
        workflow.add_event("approval_requested", prompt, status="pending")
        result.user_message = prompt

    async def execute_command_step(
        self,
        workflow: TaskWorkflow,
        step: WorkflowStep,
        decision: AgentLoopDecision,
    ) -> list[CommandObservation]:
        """执行单个命令步骤并写入生命周期事件。"""

        step.status = "running"
        step.started_at = datetime.now()
        workflow.add_event(
            "step_started",
            f"步骤「{step.title}」开始执行。",
            step_id=step.step_id,
            command=step.command,
            status="running",
        )
        task = AutoTask(command=decision.capability_name or step.command, params=list(decision.params or step.params))
        logger.info(
            'AutoGPT trace "{}" loop step "{}" dispatching command "{}"'.format(
                workflow.trace_id,
                step.step_id,
                task.command,
            )
        )
        observations = await self.dispatcher(task)
        step.status = "completed"
        step.observation_message = "命令已通过观察驱动循环执行完成。"
        step.finished_at = datetime.now()
        workflow.add_event(
            "step_completed",
            step.observation_message,
            step_id=step.step_id,
            command=step.command,
            status="completed",
        )
        return observations

    def has_failed_observation(
        self,
        workflow: TaskWorkflow,
        result: WorkflowExecutionResult,
        step: WorkflowStep,
        observations: list[CommandObservation],
    ) -> bool:
        """处理命令失败观察，返回是否需要停止循环。"""

        failed_observation = next((observation for observation in observations if not observation.success), None)
        if failed_observation is None:
            return False

        step.status = "failed"
        step.observation_message = failed_observation.message
        step.finished_at = datetime.now()
        workflow.status = "failed"
        workflow.finished_at = datetime.now()
        workflow.add_event(
            "step_failed",
            failed_observation.message,
            step_id=step.step_id,
            command=step.command,
            status="failed",
        )
        workflow.add_event("workflow_failed", failed_observation.message, status="failed")
        result.user_message = self.build_stop_reply(
            "执行过程中有一步没有完成。",
            result.observations,
            [*result.observations, *observations],
        )
        return True

    def apply_budget_stop(
        self,
        workflow: TaskWorkflow,
        result: WorkflowExecutionResult,
        budget: LoopBudget,
        reason: str,
    ) -> None:
        """预算耗尽时收束工作流，并生成解释性用户回复。"""

        workflow.status = "failed"
        workflow.finished_at = datetime.now()
        workflow.add_event("workflow_failed", reason, status="failed")
        result.user_message = self.build_stop_reply(reason, result.observations, result.observations, budget=budget)

    @staticmethod
    def apply_invalid_decision_stop(
        workflow: TaskWorkflow,
        result: WorkflowExecutionResult,
        decision: AgentLoopDecision,
    ) -> None:
        """处理无法执行的模型决策。"""

        message = decision.reason or "模型给出的下一步动作无法映射到当前能力目录。"
        workflow.status = "failed"
        workflow.finished_at = datetime.now()
        workflow.add_event("workflow_failed", message, status="failed")
        result.user_message = message

    @staticmethod
    def apply_unsupported_step_stop(
        workflow: TaskWorkflow,
        result: WorkflowExecutionResult,
        step: WorkflowStep,
        decision: AgentLoopDecision,
    ) -> None:
        """处理第一版尚未接入的 skill/schedule 等动作。"""

        message = f"任务流动作 `{decision.action_type}` 当前尚未接入循环执行器。"
        step.status = "failed"
        step.finished_at = datetime.now()
        workflow.status = "failed"
        workflow.finished_at = datetime.now()
        workflow.add_event("step_failed", message, step_id=step.step_id, status="failed")
        workflow.add_event("workflow_failed", message, status="failed")
        result.user_message = message

    @staticmethod
    def complete_without_steps(workflow: TaskWorkflow) -> WorkflowExecutionResult:
        """无步骤工作流直接完成，兼容普通聊天和知识回复路径。"""

        workflow.status = "completed"
        workflow.finished_at = datetime.now()
        workflow.add_event("workflow_started", "工作流没有可执行步骤，直接结束。", status="completed")
        workflow.add_event("workflow_completed", "工作流已完成。", status="completed")
        update_execution_metrics(workflow, [])
        return WorkflowExecutionResult(workflow=workflow, observability=workflow.observability)

    @staticmethod
    def build_stop_reply(
        reason: str,
        attempted_observations: list[CommandObservation],
        all_observations: list[CommandObservation],
        *,
        budget: LoopBudget | None = None,
    ) -> str:
        """预算或失败停止时生成稳定、可解释的回复兜底。"""

        attempted_commands = []
        seen: set[str] = set()
        for observation in all_observations or attempted_observations:
            if observation.command in seen:
                continue
            attempted_commands.append(observation.command)
            seen.add(observation.command)
        attempts = "、".join(attempted_commands) if attempted_commands else "还没有成功执行命令"
        budget_text = ""
        if budget is not None:
            budget_text = f" 当前循环预算：已执行 {budget.steps_used}/{budget.config.max_steps} 步。"
        return (
            f"我已经尝试了 {attempts}，但目前还不能继续确认结果。{reason}{budget_text}"
            "我先停止继续消耗资源；你可以稍后让我重新尝试，或补充更多条件后我再继续。"
        )
