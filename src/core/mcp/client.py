from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import httpx

from .config import MCPConfig, load_mcp_config
from .schema import MCPTool, MCPCallResult, MCPHealthStatus


class MCPClientError(RuntimeError):
    """MCP 客户端调用失败。"""


class MCPClient:
    """基于官方 MCP Python SDK 的轻量 Client facade。

    业务层只依赖这里的 `list_tools()` 和 `call_tool()`，避免把 SDK
    的 session/transport 细节扩散到 Agent runtime。
    """

    def __init__(self, config: MCPConfig | None = None) -> None:
        self.config = config or load_mcp_config()

    async def list_tools(self) -> list[MCPTool]:
        """读取远端 MCP server 暴露的 tools。"""

        if not self.config.enabled:
            return []

        try:
            async with self.open_session() as session:
                response = await session.list_tools()
        except MCPClientError:
            response = await self.fallback_list_tools()
        tools = getattr(response, "tools", response)
        return [tool for tool in (self.normalize_tool(item) for item in tools or []) if tool.enabled]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> MCPCallResult:
        """调用远端 MCP tool，并转换为项目内部标准结果。"""

        if not self.config.enabled:
            return MCPCallResult(
                tool_name=tool_name,
                success=False,
                display_text="MCP 当前未启用。",
                context_summary="MCP tool 调用被跳过：MCP 当前未启用。",
                error_code="mcp_disabled",
            )
        if not self.config.is_tool_allowed(tool_name):
            return MCPCallResult(
                tool_name=tool_name,
                success=False,
                display_text=f"MCP 工具 `{tool_name}` 不在允许列表中。",
                context_summary=f"MCP tool `{tool_name}` 被白名单策略拒绝。",
                error_code="mcp_tool_not_allowed",
            )

        try:
            try:
                async with self.open_session() as session:
                    response = await session.call_tool(tool_name, arguments or {})
            except MCPClientError:
                response = await self.fallback_call_tool(tool_name, arguments or {})
        except Exception as error:  # noqa: BLE001
            return MCPCallResult(
                tool_name=tool_name,
                success=False,
                display_text=f"MCP 工具 `{tool_name}` 调用失败：{error}",
                context_summary=f"MCP tool `{tool_name}` 调用失败：{error}",
                error_code=type(error).__name__,
            )

        text = self.extract_response_text(response)
        is_error = bool(
            getattr(response, "isError", False)
            or getattr(response, "is_error", False)
            or (isinstance(response, dict) and (response.get("isError") or response.get("is_error")))
        )
        return MCPCallResult(
            tool_name=tool_name,
            success=not is_error,
            display_text=text or ("MCP 工具执行完成。" if not is_error else "MCP 工具返回错误。"),
            context_summary=text[:500] if text else ("MCP 工具执行完成。" if not is_error else "MCP 工具返回错误。"),
            raw_result=self.dump_model(response),
            error_code="mcp_tool_error" if is_error else None,
        )

    async def fallback_list_tools(self) -> list[dict[str, Any]]:
        """在官方 SDK 不可用时，以 Streamable HTTP JSON-RPC 方式读取 tools。"""

        result = await self.rpc_request("tools/list", {})
        tools = result.get("tools", []) if isinstance(result, dict) else []
        return tools if isinstance(tools, list) else []

    async def fallback_call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """在官方 SDK 不可用时，以 Streamable HTTP JSON-RPC 方式调用 tool。"""

        return await self.rpc_request(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
        )

    async def rpc_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """执行一次轻量 Streamable HTTP JSON-RPC 请求。

        这条 fallback 只在官方 SDK 因当前 Pydantic v1 项目无法安装时使用；
        后续项目升级到 Pydantic v2 后，官方 SDK session 会自动优先接管。
        """

        request_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **self.config.headers,
        }
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            request_headers = await self.prepare_rpc_headers(client, headers)
            response = await client.post(self.config.server_url, json=request_payload, headers=request_headers)
        response.raise_for_status()
        payload = self.parse_rpc_response(response)
        if "error" in payload:
            raise MCPClientError(str(payload["error"]))
        result = payload.get("result", {})
        return result if isinstance(result, dict) else {"result": result}

    async def prepare_rpc_headers(self, client: httpx.AsyncClient, headers: dict[str, str]) -> dict[str, str]:
        """尝试完成 MCP initialize，返回带 session id 的请求头。

        某些 Streamable HTTP server 要求先 initialize 才能 tools/list；
        如果远端是无状态简化实现，初始化失败时继续使用原始请求头。
        """

        initialize_payload = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "ClassRobot", "version": "0.1.0"},
            },
        }
        try:
            response = await client.post(self.config.server_url, json=initialize_payload, headers=headers)
            response.raise_for_status()
            session_id = response.headers.get("mcp-session-id") or response.headers.get("Mcp-Session-Id")
            if not session_id:
                return headers
            session_headers = {**headers, "Mcp-Session-Id": session_id}
            await client.post(
                self.config.server_url,
                json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                headers=session_headers,
            )
            return session_headers
        except Exception:
            return headers

    @staticmethod
    def parse_rpc_response(response: httpx.Response) -> dict[str, Any]:
        """解析 JSON 或 text/event-stream JSON-RPC 响应。"""

        content_type = response.headers.get("content-type", "")
        if "text/event-stream" not in content_type:
            payload = response.json()
            return payload if isinstance(payload, dict) else {"result": payload}

        data_lines = []
        for line in response.text.splitlines():
            if line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())
        for item in data_lines:
            if not item or item == "[DONE]":
                continue
            payload = json.loads(item)
            if isinstance(payload, dict):
                return payload
        return {}

    async def health_check(self) -> MCPHealthStatus:
        """返回管理端可展示的 MCP 连接状态。"""

        if not self.config.enabled:
            return MCPHealthStatus(
                status="disabled",
                enabled=False,
                server_url=self.config.server_url,
                transport=self.config.transport,
                message="MCP Client 未启用。",
            )
        try:
            tools = await self.list_tools()
        except Exception as error:  # noqa: BLE001
            return MCPHealthStatus(
                status="error",
                enabled=True,
                server_url=self.config.server_url,
                transport=self.config.transport,
                message=str(error),
            )
        return MCPHealthStatus(
            status="ok",
            enabled=True,
            server_url=self.config.server_url,
            transport=self.config.transport,
            tool_count=len(tools),
            tools=[tool.name for tool in tools],
            message="MCP Client 已连接。" if tools else "MCP Client 已启用，但当前没有可用工具。",
        )

    def open_session(self):
        """打开官方 SDK session。"""

        if self.config.transport == "sse":
            return self.open_sse_session()
        return self.open_streamable_http_session()

    def open_streamable_http_session(self):
        """创建 Streamable HTTP session 上下文。"""

        return StreamableHTTPSessionContext(self.config)

    def open_sse_session(self):
        """创建 SSE session 上下文。"""

        return SSESessionContext(self.config)

    def normalize_tool(self, tool: Any) -> MCPTool:
        """把 SDK tool 对象标准化为项目内 tool schema。"""

        payload = self.dump_model(tool)
        name = str(payload.get("name") or getattr(tool, "name", "")).strip()
        description = str(payload.get("description") or getattr(tool, "description", "") or "").strip()
        input_schema = (
            payload.get("inputSchema")
            or payload.get("input_schema")
            or getattr(tool, "inputSchema", None)
            or getattr(tool, "input_schema", None)
            or {}
        )
        enabled = bool(name and self.config.is_tool_allowed(name))
        return MCPTool(
            name=name,
            description=description,
            input_schema=input_schema if isinstance(input_schema, dict) else {},
            server_url=self.config.server_url,
            enabled=enabled,
        )

    @staticmethod
    def dump_model(value: Any) -> Any:
        """兼容 Pydantic v1/v2 和 SDK 普通对象。"""

        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        if isinstance(value, dict):
            return value
        return {"repr": repr(value)}

    @classmethod
    def extract_response_text(cls, response: Any) -> str:
        """从 MCP call result 中提取适合写入 observation 的文本。"""

        content = getattr(response, "content", None)
        if not content and isinstance(response, dict):
            content = response.get("content")
        if not content:
            payload = cls.dump_model(response)
            return json.dumps(payload, ensure_ascii=False, default=str)[:1000]

        parts: list[str] = []
        for item in content:
            text = getattr(item, "text", None)
            if text is not None:
                parts.append(str(text))
                continue
            data = getattr(item, "data", None)
            if data is not None:
                parts.append(json.dumps(data, ensure_ascii=False, default=str))
                continue
            parts.append(json.dumps(cls.dump_model(item), ensure_ascii=False, default=str))
        return "\n".join(part for part in parts if part).strip()


class StreamableHTTPSessionContext:
    """官方 SDK Streamable HTTP session 上下文适配器。"""

    def __init__(self, config: MCPConfig) -> None:
        self.config = config
        self.transport_context = None
        self.session_context = None
        self.session = None

    async def __aenter__(self):
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as error:
            raise MCPClientError("缺少官方 MCP Python SDK，已回退到轻量 Streamable HTTP 客户端。") from error

        timeout = timedelta(seconds=self.config.timeout)
        self.transport_context = streamablehttp_client(
            self.config.server_url,
            headers=self.config.headers or None,
            timeout=timeout,
        )
        read_stream, write_stream, *_ = await self.transport_context.__aenter__()
        self.session_context = ClientSession(read_stream, write_stream)
        self.session = await self.session_context.__aenter__()
        await self.session.initialize()
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.session_context is not None:
            await self.session_context.__aexit__(exc_type, exc, tb)
        if self.transport_context is not None:
            await self.transport_context.__aexit__(exc_type, exc, tb)


class SSESessionContext:
    """官方 SDK SSE session 上下文适配器。"""

    def __init__(self, config: MCPConfig) -> None:
        self.config = config
        self.transport_context = None
        self.session_context = None
        self.session = None

    async def __aenter__(self):
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
        except ImportError as error:
            raise MCPClientError("缺少官方 MCP Python SDK，已回退到轻量 SSE/HTTP 客户端。") from error

        self.transport_context = sse_client(
            self.config.server_url,
            headers=self.config.headers or None,
            timeout=self.config.timeout,
        )
        read_stream, write_stream = await self.transport_context.__aenter__()
        self.session_context = ClientSession(read_stream, write_stream)
        self.session = await self.session_context.__aenter__()
        await self.session.initialize()
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.session_context is not None:
            await self.session_context.__aexit__(exc_type, exc, tb)
        if self.transport_context is not None:
            await self.transport_context.__aexit__(exc_type, exc, tb)
