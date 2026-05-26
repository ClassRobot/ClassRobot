from __future__ import annotations

from typing import Literal
from collections.abc import Iterable

from pydantic import Field, BaseModel
from src.core.mcp import MCPToolCatalog

from .command_tools import CommandToolCatalog

CapabilityKind = Literal["internal_command", "local_knowledge", "external_rag", "mcp_tool", "direct_chat"]
CapabilityFreshness = Literal["static", "recent", "realtime"]
CapabilityScope = Literal["private_user", "bound_group", "public_external"]
CapabilityExecutionMode = Literal["answer", "retrieve", "act"]
CapabilityFallbackBehavior = Literal["retry", "degrade", "explain_unavailable"]
CapabilityFailureReason = Literal[
    "capability_unavailable",
    "realtime_source_missing",
    "permission_denied",
    "insufficient_context",
    "tool_failed",
    "command_not_found",
]


class CapabilityDescriptor(BaseModel):
    """Agent 可见能力的统一描述。"""

    kind: CapabilityKind
    name: str
    description: str = ""
    freshness: CapabilityFreshness = "static"
    scope: CapabilityScope = "public_external"
    execution_mode: CapabilityExecutionMode = "answer"
    fallback_behavior: CapabilityFallbackBehavior = "degrade"
    domain_tags: list[str] = Field(default_factory=list)
    when_to_use: str = ""
    available: bool = True

    def to_prompt(self) -> str:
        """渲染成模型可读的一行能力说明。"""

        tags = "、".join(self.domain_tags) if self.domain_tags else "无"
        availability = "可用" if self.available else "不可用"
        usage = self.when_to_use or self.description or self.name
        return (
            f"- {self.name} [{self.kind}] | freshness={self.freshness} | scope={self.scope} "
            f"| mode={self.execution_mode} | fallback={self.fallback_behavior} | tags={tags} "
            f"| status={availability} | use={usage}"
        )


class CapabilityAvailability(BaseModel):
    """当前轮次可用能力摘要。"""

    has_internal_commands: bool = False
    has_local_knowledge: bool = True
    has_external_rag: bool = True
    has_mcp_tools: bool = False
    has_realtime_external_lookup: bool = False

    def to_prompt(self) -> str:
        """渲染成 Prompt 中的能力可用性摘要。"""

        return "\n".join(
            [
                f"- has_internal_commands: {str(self.has_internal_commands).lower()}",
                f"- has_local_knowledge: {str(self.has_local_knowledge).lower()}",
                f"- has_external_rag: {str(self.has_external_rag).lower()}",
                f"- has_mcp_tools: {str(self.has_mcp_tools).lower()}",
                f"- has_realtime_external_lookup: {str(self.has_realtime_external_lookup).lower()}",
            ]
        )


class CapabilityRequirement(BaseModel):
    """模型对当前用户目标所需能力的声明。"""

    kind: CapabilityKind = "direct_chat"
    freshness: CapabilityFreshness = "static"
    scope: CapabilityScope = "public_external"
    execution_mode: CapabilityExecutionMode = "answer"
    required: bool = False
    reason: str = ""

    @property
    def needs_realtime_public_external(self) -> bool:
        """是否要求实时公共外部信息能力。"""

        return self.required and self.freshness == "realtime" and self.scope == "public_external"


class RuntimeCapabilityCatalog(BaseModel):
    """汇总当前 Agent 可见能力，供路由器、Planner 和 Loop 使用。"""

    descriptors: list[CapabilityDescriptor] = Field(default_factory=list)
    availability: CapabilityAvailability = Field(default_factory=CapabilityAvailability)

    @classmethod
    def build(
        cls,
        *,
        command_tools: CommandToolCatalog,
        mcp_tools: MCPToolCatalog,
    ) -> "RuntimeCapabilityCatalog":
        """从命令目录和 MCP 目录构建统一能力视图。"""

        descriptors: list[CapabilityDescriptor] = [
            CapabilityDescriptor(
                kind="direct_chat",
                name="direct_chat",
                description="不需要外部工具时直接回答、解释或闲聊。",
                freshness="static",
                scope="public_external",
                execution_mode="answer",
                fallback_behavior="degrade",
                domain_tags=["chat", "answer"],
                when_to_use="普通聊天、解释、无需实时资料的问题。",
            ),
            CapabilityDescriptor(
                kind="local_knowledge",
                name="local_knowledge",
                description="检索当前用户或当前绑定群的历史聊天与文件空间。",
                freshness="recent",
                scope="private_user",
                execution_mode="retrieve",
                fallback_behavior="explain_unavailable",
                domain_tags=["memory", "files", "chat_history"],
                when_to_use="用户询问自己或当前群过去聊过、上传过、保存过的内容。",
            ),
            CapabilityDescriptor(
                kind="external_rag",
                name="external_rag",
                description="检索已配置的外部知识库、校规、制度和资料。",
                freshness="static",
                scope="public_external",
                execution_mode="retrieve",
                fallback_behavior="explain_unavailable",
                domain_tags=["docs", "policy", "knowledge_base"],
                when_to_use="用户询问学校资料、制度、政策依据或知识库原文。",
            ),
        ]
        descriptors.extend(cls.command_descriptors(command_tools))
        descriptors.extend(cls.mcp_descriptors(mcp_tools))
        availability = CapabilityAvailability(
            has_internal_commands=bool(command_tools),
            has_mcp_tools=bool(mcp_tools),
            has_realtime_external_lookup=any(
                descriptor.available
                and descriptor.kind == "mcp_tool"
                and descriptor.freshness == "realtime"
                and descriptor.scope == "public_external"
                for descriptor in descriptors
            ),
        )
        return cls(descriptors=descriptors, availability=availability)

    @staticmethod
    def command_descriptors(command_tools: CommandToolCatalog) -> list[CapabilityDescriptor]:
        """把项目命令目录转换为统一能力描述。"""

        return [
            CapabilityDescriptor(
                kind="internal_command",
                name=tool.command,
                description=tool.description,
                freshness="recent",
                scope="private_user",
                execution_mode="act",
                fallback_behavior="explain_unavailable",
                domain_tags=["classrobot_command"],
                when_to_use=tool.description,
            )
            for tool in command_tools
        ]

    @staticmethod
    def mcp_descriptors(mcp_tools: MCPToolCatalog) -> list[CapabilityDescriptor]:
        """把 MCP tool 目录转换为统一能力描述。"""

        return [
            CapabilityDescriptor(
                kind="mcp_tool",
                name=tool.name,
                description=tool.public_description or tool.description,
                freshness=tool.freshness,
                scope="public_external",
                execution_mode="retrieve" if tool.freshness == "realtime" else "act",
                fallback_behavior="explain_unavailable",
                domain_tags=list(tool.domain_tags),
                when_to_use=tool.when_to_use or tool.description,
                available=tool.enabled,
            )
            for tool in mcp_tools.tools
        ]

    def has_realtime_external_lookup(self) -> bool:
        """是否存在实时公共外部查询能力。"""

        return self.availability.has_realtime_external_lookup

    def to_prompt(self, *, descriptors: Iterable[CapabilityDescriptor] | None = None) -> str:
        """渲染完整能力目录。"""

        selected = list(descriptors) if descriptors is not None else self.descriptors
        lines = ["## Capability Availability", self.availability.to_prompt(), "## Capability Catalog"]
        lines.extend(descriptor.to_prompt() for descriptor in selected)
        return "\n".join(lines)
