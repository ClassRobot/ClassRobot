import pytest

from src.core.mcp.catalog import MCPToolCatalog
from src.core.mcp.schema import MCPTool


class FakeMCPClient:
    async def list_tools(self):
        return [
            MCPTool(
                name="search_docs",
                description="检索外部文档",
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                server_url="http://127.0.0.1:8000/mcp",
            )
        ]


class FailingMCPClient:
    async def list_tools(self):
        raise RuntimeError("server offline")


@pytest.mark.asyncio
async def test_mcp_tool_catalog_loads_tools():
    catalog = await MCPToolCatalog.from_client(FakeMCPClient())

    assert catalog.get("search_docs") is not None
    assert "search_docs" in catalog.to_prompt()
    assert "query*" in catalog.to_prompt()


@pytest.mark.asyncio
async def test_mcp_tool_catalog_degrades_to_empty_on_failure():
    catalog = await MCPToolCatalog.from_client(FailingMCPClient())

    assert not catalog
    assert "server offline" in catalog.to_prompt()
