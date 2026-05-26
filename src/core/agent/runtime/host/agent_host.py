from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nonebot import logger
from src.core.llm.message import Content
from src.core.agent.runtime.reply import ReplyPolicy
from src.core.agent.runtime.context import ContextPack, ContextEngine
from src.core.agent.runtime.live_trace import agent_live_trace_registry
from src.core.agent.runtime.delegation import AgentCatalog, AgentHandoffRecord

from .schema import TurnDecision, TurnEnvelope, TurnOutputBundle

if TYPE_CHECKING:
    from src.core.agent.runtime.schema import AgentTurnResult
    from src.core.agent.runtime.knowledge import RuntimeContext


class AgentHost:
    """Host control plane that wraps turns, context, delegation, and reply policy."""

    host_agent_name = "agent_host"

    def __init__(
        self,
        *,
        context_engine: ContextEngine | None = None,
        agent_catalog: AgentCatalog | None = None,
        reply_policy: ReplyPolicy | None = None,
    ) -> None:
        self.context_engine = context_engine or ContextEngine()
        self.agent_catalog = agent_catalog or AgentCatalog.default()
        self.reply_policy = reply_policy or ReplyPolicy()

    def create_turn_envelope(
        self,
        *,
        trace_id: str,
        user_id: int | None,
        contents: list[Content],
        message_preview: str,
        runtime_context: "RuntimeContext | None" = None,
        pending_workflow: Any = None,
    ) -> TurnEnvelope:
        envelope = TurnEnvelope(
            trace_id=trace_id,
            user_id=user_id,
            contents=list(contents),
            message_preview=message_preview,
            runtime_context=self.runtime_context_preview(runtime_context),
            pending_workflow=self.workflow_preview(pending_workflow),
        )
        agent_live_trace_registry.emit(
            trace_id,
            event_type="host_turn_started",
            stage="session",
            status="running",
            params_preview={
                "user_id": user_id,
                "message_preview": message_preview,
                "has_pending_workflow": pending_workflow is not None,
            },
        )
        return envelope

    def build_context_pack(self, envelope: TurnEnvelope, session: Any) -> ContextPack:
        pack = self.context_engine.build_pack(
            trace_id=envelope.trace_id,
            user_id=envelope.user_id,
            message_preview=envelope.message_preview,
            messages=session.messages,
            pending_workflow=getattr(session, "pending_workflow", None),
            last_workflow=getattr(session, "last_workflow", None),
            last_turn_result=getattr(session, "last_turn_result", None),
        )
        agent_live_trace_registry.emit(
            envelope.trace_id,
            event_type="context_pack_built",
            stage="knowledge",
            status="completed",
            params_preview={
                "summary": pack.compact_summary(),
                "layers": [layer for layer in pack.dict() if layer.endswith("_context") or layer.endswith("_memory")],
            },
        )
        return pack

    def build_turn_output(
        self,
        *,
        envelope: TurnEnvelope,
        turn_result: "AgentTurnResult",
        context_pack: ContextPack,
    ) -> TurnOutputBundle:
        handoffs = self.build_handoffs(envelope=envelope, turn_result=turn_result, context_pack=context_pack)
        decision = self.build_decision(turn_result=turn_result, handoffs=handoffs)
        auto_tasks = turn_result.auto_tasks
        workflow = turn_result.workflow
        reply_text = getattr(auto_tasks, "reply", "") if auto_tasks is not None else ""
        reply_text, consistency_reason = self.enforce_reply_consistency(
            reply=reply_text,
            decision=decision,
            workflow=workflow,
        )
        if auto_tasks is not None and reply_text != (getattr(auto_tasks, "reply", "") or ""):
            auto_tasks.reply = reply_text
        reply = self.reply_policy.build_envelope(
            trace_id=envelope.trace_id,
            reply=reply_text,
            need_confirm=bool(getattr(auto_tasks, "need_confirm", False) or getattr(workflow, "need_confirm", False)),
            requires_execution=decision.requires_execution,
            failed=bool(getattr(auto_tasks, "is_violation", False)),
            failure_reason=("violation" if getattr(auto_tasks, "is_violation", False) else consistency_reason),
        )
        bundle = TurnOutputBundle(
            trace_id=envelope.trace_id,
            decision=decision,
            reply=reply,
            context_pack=context_pack,
            handoffs=handoffs,
            audit_artifacts={
                "route_intent": getattr(turn_result.route, "intent", "") if turn_result.route is not None else "",
                "workflow_kind": getattr(workflow, "kind", "") if workflow is not None else "",
                "workflow_steps": len(getattr(workflow, "steps", []) or []) if workflow is not None else 0,
                "consistency_reason": consistency_reason,
            },
        )
        self.attach_handoffs_to_observability(turn_result, handoffs)
        self.emit_handoffs(envelope.trace_id, handoffs)
        logger.info(
            f'AutoGPT trace "{envelope.trace_id}" AgentHost output built '
            f"decision={decision.decision_type} handoffs={len(handoffs)}"
        )
        return bundle

    def build_handoffs(
        self,
        *,
        envelope: TurnEnvelope,
        turn_result: "AgentTurnResult",
        context_pack: ContextPack,
    ) -> list[AgentHandoffRecord]:
        decisions = self.agent_catalog.select_for_turn(
            context_pack=context_pack,
            route=turn_result.route,
            plan=turn_result.plan,
            workflow=turn_result.workflow,
        )
        handoffs: list[AgentHandoffRecord] = []
        for decision in decisions:
            descriptor = self.agent_catalog.get(decision.target_agent)
            layers = decision.context_layers or (descriptor.context_requirements if descriptor else [])
            handoffs.append(
                AgentHandoffRecord(
                    trace_id=envelope.trace_id,
                    source_agent=self.host_agent_name,
                    target_agent=decision.target_agent,
                    status="planned",
                    reason=decision.reason,
                    context_layers=list(layers),
                    context_summary=context_pack.compact_summary(),
                )
            )
        return handoffs

    @staticmethod
    def build_decision(*, turn_result: "AgentTurnResult", handoffs: list[AgentHandoffRecord]) -> TurnDecision:
        workflow = turn_result.workflow
        auto_tasks = turn_result.auto_tasks
        if workflow is not None and getattr(workflow, "need_confirm", False):
            return TurnDecision(
                decision_type="confirm", reason="Workflow requires confirmation.", requires_confirmation=True
            )
        if workflow is not None and getattr(workflow, "steps", None):
            return TurnDecision(
                decision_type="execute", reason="Workflow contains executable steps.", requires_execution=True
            )
        if auto_tasks is not None and getattr(auto_tasks, "reply", ""):
            return TurnDecision(decision_type="direct_reply", reason="Turn has a direct reply.")
        if handoffs:
            final_agent = handoffs[-1].target_agent
            return TurnDecision(
                decision_type="delegate", target_agent=final_agent, reason="Host selected specialized agents."
            )
        return TurnDecision(decision_type="stop", reason="No executable action or reply was produced.")

    def enforce_reply_consistency(
        self,
        *,
        reply: str,
        decision: TurnDecision,
        workflow: Any = None,
    ) -> tuple[str, str]:
        """Prevent user-visible replies from claiming work that will not run."""

        text = (reply or "").strip()
        if not text or not self.reply_policy.claims_future_action(text):
            return text, ""
        has_executable_steps = bool(getattr(workflow, "steps", []) if workflow is not None else [])
        if has_executable_steps or decision.requires_execution or decision.requires_confirmation:
            return text, ""
        return (
            "这次还没有生成可执行的工具调用步骤，所以我不会假装已经开始查询。" "你可以稍后让我重新尝试，或补充更明确的查询范围。",
            "action_claim_without_workflow",
        )

    @staticmethod
    def attach_handoffs_to_observability(
        turn_result: "AgentTurnResult",
        handoffs: list[AgentHandoffRecord],
    ) -> None:
        """Persist compact handoff records in workflow observability when available."""

        if turn_result.workflow is None:
            return
        turn_result.workflow.observability.handoffs = [
            {
                "source_agent": handoff.source_agent,
                "target_agent": handoff.target_agent,
                "status": handoff.status,
                "reason": handoff.reason,
                "context_layers": handoff.context_layers,
                "created_at": handoff.created_at.isoformat(),
            }
            for handoff in handoffs
        ]

    @staticmethod
    def emit_handoffs(trace_id: str, handoffs: list[AgentHandoffRecord]) -> None:
        for handoff in handoffs:
            agent_live_trace_registry.emit(
                trace_id,
                event_type="agent_handoff_planned",
                stage="plan",
                status=handoff.status,
                node_type="agent_handoff",
                node_label=handoff.target_agent,
                params_preview={
                    "target_agent": handoff.target_agent,
                    "context_layers": handoff.context_layers,
                    "reason": handoff.reason,
                },
                observation_summary=handoff.context_summary,
            )

    @staticmethod
    def runtime_context_preview(runtime_context: "RuntimeContext | None") -> dict[str, Any]:
        if runtime_context is None:
            return {}
        return {
            "user_id": runtime_context.user_id,
            "platform": runtime_context.platform,
            "platform_name": runtime_context.platform_name,
            "channel_id": runtime_context.channel_id,
            "guild_id": runtime_context.guild_id,
            "message_id": runtime_context.message_id,
        }

    @staticmethod
    def workflow_preview(workflow: Any) -> dict[str, Any] | None:
        if workflow is None:
            return None
        return {
            "trace_id": getattr(workflow, "trace_id", ""),
            "kind": getattr(workflow, "kind", ""),
            "status": getattr(workflow, "status", ""),
            "steps": len(getattr(workflow, "steps", []) or []),
        }
