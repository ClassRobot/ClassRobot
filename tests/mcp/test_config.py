from src.core.mcp.config import MCPConfig


def test_mcp_config_defaults_disabled():
    config = MCPConfig()

    assert config.enabled is False
    assert config.server_url == "http://127.0.0.1:8000/mcp"
    assert config.transport == "streamable_http"
    assert config.tool_allowlist == []


def test_mcp_config_parses_env_style_values():
    config = MCPConfig.parse_obj(
        {
            "mcp_enabled": "true",
            "mcp_server_url": " http://127.0.0.1:8000/mcp ",
            "mcp_transport": "streamable-http",
            "mcp_timeout": "15",
            "mcp_auth_token": " token ",
            "mcp_tool_allowlist": '["search_docs", "create_ticket"]',
        }
    )

    assert config.enabled is True
    assert config.transport == "streamable_http"
    assert config.timeout == 15
    assert config.headers == {"Authorization": "Bearer token"}
    assert config.is_tool_allowed("search_docs") is True
    assert config.is_tool_allowed("unknown") is False
