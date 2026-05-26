from __future__ import annotations

from collections.abc import Iterable

from pydantic import Field, BaseModel

from .schema import MCPTool
from .client import MCPClient


class MCPToolCatalog(BaseModel):
    """当前 MCP server 暴露给 Agent 的工具目录。"""

    tools: list[MCPTool] = Field(default_factory=list)
    tool_index: dict[str, MCPTool] = Field(default_factory=dict)
    last_error: str = ""

    @classmethod
    async def from_client(cls, client: MCPClient | None = None) -> "MCPToolCatalog":
        """从 MCP Client 拉取工具目录，失败时返回空目录。"""

        client = client or MCPClient()
        catalog = cls()
        try:
            for tool in await client.list_tools():
                catalog.append(tool)
        except Exception as error:  # noqa: BLE001
            catalog.last_error = str(error)
        return catalog

    def append(self, tool: MCPTool) -> None:
        """追加工具并建立索引。"""

        if not tool.enabled or not tool.name:
            return
        self.tools.append(tool)
        self.tool_index[tool.name] = tool

    def get(self, tool_name: str) -> MCPTool | None:
        """按 MCP tool 名称查找工具。"""

        return self.tool_index.get(tool_name)

    def resolve_tools(self, tool_names: Iterable[str] | None) -> set[str]:
        """把候选 MCP tool 名称解析成当前真实存在的名称。"""

        if not tool_names:
            return set()
        return {name for name in tool_names if name in self.tool_index}

    def realtime_public_tools(self) -> list[MCPTool]:
        """返回可用于实时公共外部信息检索的 MCP tool。"""

        return [
            tool
            for tool in self.tools
            if tool.enabled
            and tool.freshness == "realtime"
            and bool({"web_search", "news", "browser"} & set(tool.domain_tags))
        ]

    def has_realtime_public_lookup(self) -> bool:
        """判断当前 MCP 目录是否存在实时公共外部查询能力。"""

        return bool(self.realtime_public_tools())

    def select_tools(
        self,
        *,
        limit: int | None = None,
        tool_names: Iterable[str] | None = None,
    ) -> list[MCPTool]:
        """按显式候选名称挑选工具，否则返回完整目录。"""

        selected: list[MCPTool]
        if tool_names:
            selected = [self.tool_index[name] for name in tool_names if name in self.tool_index]
            if selected:
                return selected[:limit] if limit is not None else selected
        selected = list(self.tools)
        return selected[:limit] if limit is not None else selected

    def to_prompt(
        self,
        *,
        limit: int | None = None,
        tool_names: Iterable[str] | None = None,
    ) -> str:
        """渲染 MCP tool 目录。"""

        selected = self.select_tools(limit=limit, tool_names=tool_names)
        if selected:
            return "\n".join(tool.to_prompt() for tool in selected)
        if self.last_error:
            return f"暂无可用 MCP 工具（目录加载失败：{self.last_error}）。"
        return "暂无可用 MCP 工具。"

    def __bool__(self) -> bool:
        return bool(self.tools)
