"""`utils.llm.agents` 已降级为兼容路径，新代码请统一从 `core.agent` 导入。"""

from __future__ import annotations

import sys
from importlib import import_module

from core.agent import AgentProfile as AgentProfile
from core.agent import AgentResponse as AgentResponse
from core.agent import AgentSession as AgentSession
from core.agent import AgentTool as AgentTool
from core.agent import AutoTaskAgent as AutoTaskAgent
from core.agent import BaseAgent as BaseAgent
from core.agent import BaseAgentConfig as BaseAgentConfig
from core.agent import BaseFunctionAgent as BaseFunctionAgent
from core.agent import CLASSBOT_TASK_AGENT_PROFILE as CLASSBOT_TASK_AGENT_PROFILE
from core.agent import DOMESTIC_PROVIDERS as DOMESTIC_PROVIDERS
from core.agent import DomesticProvider as DomesticProvider
from core.agent import ExtractAgent as ExtractAgent
from core.agent import FileAgent as FileAgent
from core.agent import LLMAgent as LLMAgent
from core.agent import RagAgent as RagAgent
from core.agent import SummaryAgent as SummaryAgent
from core.agent import ToolCallResult as ToolCallResult
from core.agent import ToolCallingAgent as ToolCallingAgent
from core.agent import ToolCallingAgentConfig as ToolCallingAgentConfig
from core.agent import VisionAgent as VisionAgent
from core.agent import build_llm_config as build_llm_config
from core.agent import create_classbot_agent as create_classbot_agent
from core.agent import dumps_llm_configs as dumps_llm_configs
from core.agent import get_domestic_provider as get_domestic_provider
from core.agent import tool as tool

LEGACY_SUBMODULE_ALIASES = {
    "utils.llm.agents.agent": "core.agent.agent",
    "utils.llm.agents.base": "core.agent.base",
    "utils.llm.agents.builtin": "core.agent.builtin",
    "utils.llm.agents.builtin.conversation": "core.agent.builtin.conversation",
    "utils.llm.agents.builtin.multimodal": "core.agent.builtin.multimodal",
    "utils.llm.agents.builtin.planning": "core.agent.builtin.planning",
    "utils.llm.agents.builtin.retrieval": "core.agent.builtin.retrieval",
    "utils.llm.agents.domestic": "core.agent.domestic",
    "utils.llm.agents.exception": "core.agent.exception",
    "utils.llm.agents.profiles": "core.agent.profiles",
    "utils.llm.agents.ragflow": "core.agent.ragflow",
    "utils.llm.agents.ragflow.client": "core.agent.ragflow.client",
    "utils.llm.agents.ragflow.ragflow": "core.agent.ragflow.ragflow",
    "utils.llm.agents.ragflow.schema": "core.agent.ragflow.schema",
    "utils.llm.agents.schema": "core.agent.schema",
    "utils.llm.agents.tool": "core.agent.tool",
    "utils.llm.agents.tools": "core.agent.tools",
}


def register_legacy_aliases() -> None:
    """把旧的 `utils.llm.agents.*` 路径映射到 `core.agent.*`。"""

    package = sys.modules[__name__]
    for legacy_name, target_name in LEGACY_SUBMODULE_ALIASES.items():
        target_module = import_module(target_name)
        sys.modules[legacy_name] = target_module
    package.builtin = sys.modules["utils.llm.agents.builtin"]
    package.ragflow = sys.modules["utils.llm.agents.ragflow"]


register_legacy_aliases()

__all__ = [
    "AgentProfile",
    "AgentResponse",
    "AgentSession",
    "AgentTool",
    "AutoTaskAgent",
    "BaseAgent",
    "BaseAgentConfig",
    "BaseFunctionAgent",
    "CLASSBOT_TASK_AGENT_PROFILE",
    "DOMESTIC_PROVIDERS",
    "DomesticProvider",
    "ExtractAgent",
    "FileAgent",
    "LLMAgent",
    "RagAgent",
    "SummaryAgent",
    "ToolCallResult",
    "ToolCallingAgent",
    "ToolCallingAgentConfig",
    "VisionAgent",
    "build_llm_config",
    "builtin",
    "create_classbot_agent",
    "dumps_llm_configs",
    "get_domestic_provider",
    "ragflow",
    "tool",
]
