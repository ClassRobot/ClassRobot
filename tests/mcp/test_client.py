import pytest


@pytest.mark.asyncio
async def test_mcp_client_uses_exception_type_when_message_is_empty():
    from src.core.mcp.client import MCPClient

    class BrokenSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def call_tool(self, tool_name, arguments):
            raise RuntimeError()

    client = MCPClient()
    client.config.enabled = True
    client.open_session = lambda: BrokenSession()

    result = await client.call_tool("browser_search", {"query": "热点"})

    assert result.success is False
    assert "RuntimeError" in result.display_text
    assert result.error_code == "RuntimeError"


def test_mcp_client_extracts_summary_from_structured_content():
    from src.core.mcp.client import MCPClient

    response = {
        "content": [{"type": "text", "text": '{"summary":"这是一段摘要"}'}],
        "structuredContent": {
            "summary": "这是一段摘要",
            "results": [
                {"title": "热点 1", "snippet": "内容 1", "source": "example.com"},
            ],
        },
        "isError": False,
    }

    assert MCPClient.extract_response_summary(response) == "这是一段摘要"


def test_mcp_client_extracts_direct_text_field():
    from src.core.mcp.client import MCPClient

    response = {
        "type": "text",
        "text": "Search results for '热点' via bing:\n1. 结果 A\n2. 结果 B",
    }

    assert MCPClient.extract_response_text(response).startswith("Search results for '热点' via bing")


def test_mcp_client_extracts_text_from_content_dict_items():
    from src.core.mcp.client import MCPClient

    response = {
        "content": [
            {
                "type": "text",
                "text": "Search results for '热点' via bing:\n1. 结果 A\n2. 结果 B",
            }
        ]
    }

    assert MCPClient.extract_response_text(response).startswith("Search results for '热点' via bing")
