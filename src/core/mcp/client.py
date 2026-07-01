from __future__ import annotations

import json
import time
from typing import Any
from datetime import timedelta

import httpx
from nonebot import logger

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
            logger.info("MCP list_tools skipped because MCP is disabled")
            return []

        started = time.perf_counter()
        try:
            async with self.open_session() as session:
                response = await session.list_tools()
            transport = self.config.transport
        except MCPClientError:
            logger.info("MCP list_tools falling back to JSON-RPC transport")
            response = await self.fallback_list_tools()
            transport = "fallback_rpc"
        tools = getattr(response, "tools", response)
        normalized_tools = [tool for tool in (self.normalize_tool(item) for item in tools or []) if tool.enabled]
        logger.info(
            f"MCP list_tools completed in {time.perf_counter() - started:.3f}s "
            f"transport={transport} tool_count={len(normalized_tools)}"
        )
        return normalized_tools

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

        started = time.perf_counter()
        payload = arguments or {}
        logger.info(
            f'MCP call_tool started tool="{tool_name}" transport={self.config.transport} '
            f"timeout={self.config.timeout}s args_keys={sorted(payload.keys())}"
        )
        try:
            try:
                async with self.open_session() as session:
                    response = await session.call_tool(tool_name, payload)
                transport = self.config.transport
            except MCPClientError:
                logger.info(f'MCP call_tool "{tool_name}" falling back to JSON-RPC transport')
                response = await self.fallback_call_tool(tool_name, payload)
                transport = "fallback_rpc"
        except Exception as error:  # noqa: BLE001
            error_text = str(error).strip() or type(error).__name__
            logger.warning(
                f'MCP call_tool failed tool="{tool_name}" in {time.perf_counter() - started:.3f}s '
                f'error="{error_text}"'
            )
            return MCPCallResult(
                tool_name=tool_name,
                success=False,
                display_text=f"外部工具调用失败：{error_text}",
                context_summary=f"外部工具调用失败：{error_text}",
                error_code=type(error).__name__,
            )

        text = self.extract_response_text(response)
        summary = self.extract_response_summary(response)
        is_error = bool(
            getattr(response, "isError", False)
            or getattr(response, "is_error", False)
            or (isinstance(response, dict) and (response.get("isError") or response.get("is_error")))
        )
        logger.info(
            f'MCP call_tool completed tool="{tool_name}" in {time.perf_counter() - started:.3f}s '
            f"transport={transport} success={not is_error} summary_len={len(summary)} text_len={len(text)}"
        )
        return MCPCallResult(
            tool_name=tool_name,
            success=not is_error,
            display_text=summary or text or ("MCP 工具执行完成。" if not is_error else "MCP 工具返回错误。"),
            context_summary=(summary or text[:500] or ("MCP 工具执行完成。" if not is_error else "MCP 工具返回错误。")),
            raw_result=self.dump_model(response),
            error_code="mcp_tool_error" if is_error else None,
        )

    async def fallback_list_tools(self) -> list[dict[str, Any]]:
        """在官方 SDK 不可用时，以 Streamable HTTP JSON-RPC 方式读取 tools。"""

        logger.info("MCP fallback_list_tools issuing JSON-RPC tools/list request")
        result = await self.rpc_request("tools/list", {})
        tools = result.get("tools", []) if isinstance(result, dict) else []
        return tools if isinstance(tools, list) else []

    async def fallback_call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """在官方 SDK 不可用时，以 Streamable HTTP JSON-RPC 方式调用 tool。"""

        logger.info(f'MCP fallback_call_tool issuing JSON-RPC tools/call request for "{tool_name}"')
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
            logger.info(
                f'MCP rpc_request sending method="{method}" url="{self.config.server_url}" '
                f'headers_session={"Mcp-Session-Id" in request_headers}'
            )
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
        annotations = payload.get("annotations") if isinstance(payload.get("annotations"), dict) else {}
        input_schema = (
            payload.get("inputSchema")
            or payload.get("input_schema")
            or getattr(tool, "inputSchema", None)
            or getattr(tool, "input_schema", None)
            or {}
        )
        domain_tags = self.normalize_domain_tags(
            payload.get("domain_tags")
            or payload.get("domainTags")
            or annotations.get("domain_tags")
            or annotations.get("domainTags")
            or payload.get("tags")
            or annotations.get("tags")
        )
        if not domain_tags:
            domain_tags = self.infer_domain_tags(name, description)
        freshness = str(
            payload.get("freshness")
            or annotations.get("freshness")
            or ("realtime" if self.is_realtime_tool(name, description, domain_tags) else "static")
        ).strip()
        if freshness not in {"static", "recent", "realtime"}:
            freshness = "static"
        enabled = bool(name and self.config.is_tool_allowed(name))
        return MCPTool(
            name=name,
            description=description,
            input_schema=input_schema if isinstance(input_schema, dict) else {},
            server_url=self.config.server_url,
            enabled=enabled,
            domain_tags=domain_tags,
            freshness=freshness,
            public_description=str(
                payload.get("public_description")
                or payload.get("publicDescription")
                or annotations.get("public_description")
                or annotations.get("publicDescription")
                or ""
            ).strip(),
            when_to_use=str(
                payload.get("when_to_use")
                or payload.get("whenToUse")
                or annotations.get("when_to_use")
                or annotations.get("whenToUse")
                or ""
            ).strip(),
        )

    @staticmethod
    def normalize_domain_tags(value: Any) -> list[str]:
        """标准化 MCP metadata 中的领域标签。"""

        if value is None:
            return []
        if isinstance(value, str):
            raw_items = value.replace("，", ",").split(",")
        elif isinstance(value, list):
            raw_items = value
        else:
            raw_items = [value]
        tags: list[str] = []
        seen: set[str] = set()
        for item in raw_items:
            tag = str(item).strip().lower().replace("-", "_")
            if not tag or tag in seen:
                continue
            tags.append(tag)
            seen.add(tag)
        return tags

    @classmethod
    def infer_domain_tags(cls, name: str, description: str) -> list[str]:
        """从工具自描述中补足通用领域标签。"""

        text = f"{name} {description}".lower()
        tags: list[str] = []
        if any(token in text for token in ("web", "search", "browser", "internet", "联网", "搜索", "网页")):
            tags.append("web_search")
        if any(token in text for token in ("news", "hot", "trend", "新闻", "热点", "热搜")):
            tags.append("news")
        if any(token in text for token in ("doc", "docs", "document", "文档", "资料")):
            tags.append("docs")
        return tags

    @staticmethod
    def is_realtime_tool(name: str, description: str, domain_tags: list[str]) -> bool:
        """判断 MCP tool 是否适合实时公共外部检索。"""

        text = f"{name} {description}".lower()
        return bool(
            {"web_search", "news", "browser"} & set(domain_tags)
            or any(token in text for token in ("realtime", "latest", "current", "实时", "最新", "新闻", "热点"))
        )

    @staticmethod
    def dump_model(value: Any) -> Any:
        """兼容 Pydantic v1/v2 和 SDK 普通对象。"""

        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.model_dump()
        if isinstance(value, dict):
            return value
        return {"repr": repr(value)}

    @classmethod
    def extract_response_text(cls, response: Any) -> str:
        """从 MCP call result 中提取适合写入 observation 的文本。"""

        payload = cls.dump_model(response)
        if isinstance(payload, dict):
            direct_text = payload.get("text")
            if isinstance(direct_text, str) and direct_text.strip():
                return direct_text.strip()

        content = getattr(response, "content", None)
        if not content and isinstance(response, dict):
            content = response.get("content")
        if not content:
            return json.dumps(payload, ensure_ascii=False, default=str)[:1000]

        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text is not None:
                    parts.append(str(text))
                    continue
                data = item.get("data")
                if data is not None:
                    parts.append(json.dumps(data, ensure_ascii=False, default=str))
                    continue
                parts.append(json.dumps(item, ensure_ascii=False, default=str))
                continue
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

    @classmethod
    def extract_response_summary(cls, response: Any) -> str:
        """尽量从结构化 MCP 结果中提取面向用户的简洁摘要。"""

        payload = cls.dump_model(response)
        if not isinstance(payload, dict):
            return ""

        structured = payload.get("structuredContent") or payload.get("structured_content")
        if isinstance(structured, dict):
            summary = cls.summarize_structured_content(structured)
            if summary:
                return summary

        content = payload.get("content")
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text") or "").strip()
                if not text:
                    continue
                parsed = cls.try_load_json_text(text)
                if isinstance(parsed, dict):
                    summary = cls.summarize_structured_content(parsed)
                    if summary:
                        return summary
        return ""

    @staticmethod
    def try_load_json_text(text: str) -> dict[str, Any] | None:
        """尝试把文本解析成 JSON 对象。"""

        if not text.startswith("{"):
            return None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def summarize_structured_content(structured: dict[str, Any]) -> str:
        """把搜索类结构化结果压缩成短摘要。"""

        summary = str(structured.get("summary") or "").strip()
        if summary:
            return summary[:1200]

        results = structured.get("results")
        if not isinstance(results, list) or not results:
            return ""

        lines: list[str] = []
        for index, item in enumerate(results[:3], start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            snippet = str(item.get("snippet") or "").strip()
            source = str(item.get("source") or "").strip()
            if not title and not snippet:
                continue
            line = f"{index}. {title}"
            if source:
                line += f" ({source})"
            if snippet:
                line += f": {snippet}"
            lines.append(line[:400])
        return "\n".join(lines)


class StreamableHTTPSessionContext:
    """官方 SDK Streamable HTTP session 上下文适配器。"""

    def __init__(self, config: MCPConfig) -> None:
        self.config = config
        self.transport_context = None
        self.session_context = None
        self.session = None

    async def __aenter__(self):
        try:
            from mcp import ClientSession  # type: ignore[import-not-found]
            from mcp.client.streamable_http import streamablehttp_client  # type: ignore[import-not-found]
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
            from mcp import ClientSession  # type: ignore[import-not-found]
            from mcp.client.sse import sse_client  # type: ignore[import-not-found]
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
