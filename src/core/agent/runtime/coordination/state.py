from __future__ import annotations

from dataclasses import field, dataclass

from src.core.llm.message import Content, Context

from ..schema import AgentPlan, IntentRoute, AutoTaskList, RuntimeScene


@dataclass(slots=True)
class PipelineState:
    """承载一次消息处理流程中的中间状态。"""

    trace_id: str = ""
    user_content: list[Content] = field(default_factory=list)
    runtime_scene: RuntimeScene = "chat"
    intent_route: IntentRoute | None = None
    agent_plan: AgentPlan | None = None
    extracted_context: Context | None = None
    local_knowledge: str | None = None
    retrieved_knowledge: str | None = None
    auto_tasks: AutoTaskList | None = None
