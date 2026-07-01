from __future__ import annotations

import os
import time
import asyncio
from typing import Any
from uuid import uuid4
from threading import RLock
from datetime import datetime
from collections import OrderedDict, deque

from pydantic import Field, BaseModel, ConfigDict, field_validator


class AgentLiveTraceConfig(BaseModel):
    """开发态 Agent 实时追踪配置。"""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    enabled: bool = Field(default=False, alias="agent_live_trace_enabled")
    max_traces: int = Field(default=50, alias="agent_live_trace_max_traces")
    max_events_per_trace: int = Field(default=400, alias="agent_live_trace_max_events_per_trace")
    retention_seconds: int = Field(default=1800, alias="agent_live_trace_retention_seconds")
    include_debug_preview: bool = Field(default=True, alias="agent_live_trace_include_debug_preview")

    @field_validator("enabled", "include_debug_preview", mode="before")
    @classmethod
    def normalize_bool(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @field_validator("max_traces", "max_events_per_trace", "retention_seconds", mode="before")
    @classmethod
    def normalize_positive_int(cls, value: object) -> int:
        try:
            parsed = int(value) if value is not None else 0
        except (TypeError, ValueError):
            return 0
        return max(parsed, 0)

    @classmethod
    def from_runtime(cls) -> "AgentLiveTraceConfig":
        """从 NoneBot driver config 与环境变量读取 live trace 配置。"""

        data: dict[str, Any] = {}
        try:
            from nonebot import get_driver

            driver_config = get_driver().config
            for key in (
                "agent_live_trace_enabled",
                "agent_live_trace_max_traces",
                "agent_live_trace_max_events_per_trace",
                "agent_live_trace_retention_seconds",
                "agent_live_trace_include_debug_preview",
            ):
                value = getattr(driver_config, key, None)
                if value is not None:
                    data[key] = value
        except Exception:
            pass

        env_key_map = {
            "AGENT_LIVE_TRACE_ENABLED": "agent_live_trace_enabled",
            "AGENT_LIVE_TRACE_MAX_TRACES": "agent_live_trace_max_traces",
            "AGENT_LIVE_TRACE_MAX_EVENTS_PER_TRACE": "agent_live_trace_max_events_per_trace",
            "AGENT_LIVE_TRACE_RETENTION_SECONDS": "agent_live_trace_retention_seconds",
            "AGENT_LIVE_TRACE_INCLUDE_DEBUG_PREVIEW": "agent_live_trace_include_debug_preview",
        }
        for env_key, config_key in env_key_map.items():
            if env_key in os.environ:
                data[config_key] = os.environ[env_key]
        return cls.model_validate(data).with_safe_defaults()

    def with_safe_defaults(self) -> "AgentLiveTraceConfig":
        defaults = type(self)()
        values = self.model_dump()
        for field_name in ("max_traces", "max_events_per_trace", "retention_seconds"):
            if values[field_name] <= 0:
                values[field_name] = getattr(defaults, field_name)
        return type(self)(**values)


class AgentTraceRedactor:
    """生成适合后台展示的参数预览，避免密钥与大段上下文裸露。"""

    sensitive_tokens = ("token", "secret", "password", "authorization", "api_key", "apikey", "cookie", "key")
    max_string_length = 500
    max_sequence_items = 20
    max_mapping_items = 40

    @classmethod
    def preview(cls, value: Any, *, include_debug_preview: bool = True) -> Any:
        """返回脱敏、截断后的展示值。"""

        redacted = cls.redact(value)
        if include_debug_preview:
            return redacted
        return cls.compact(redacted)

    @classmethod
    def redact(cls, value: Any, *, key: str = "") -> Any:
        if cls.is_sensitive_key(key):
            return "***"
        if isinstance(value, BaseModel):
            return cls.redact(value.model_dump(), key=key)
        if isinstance(value, dict):
            items = list(value.items())[: cls.max_mapping_items]
            result = {str(item_key): cls.redact(item_value, key=str(item_key)) for item_key, item_value in items}
            if len(value) > cls.max_mapping_items:
                result["_truncated"] = f"{len(value) - cls.max_mapping_items} more keys"
            return result
        if isinstance(value, (list, tuple, set)):
            values = list(value)
            result = [cls.redact(item, key=key) for item in values[: cls.max_sequence_items]]
            if len(values) > cls.max_sequence_items:
                result.append(f"... {len(values) - cls.max_sequence_items} more items")
            return result
        if isinstance(value, str):
            return cls.truncate(value)
        return value

    @classmethod
    def compact(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: cls.compact(item) for key, item in list(value.items())[:10]}
        if isinstance(value, list):
            return [cls.compact(item) for item in value[:8]]
        if isinstance(value, str):
            return cls.truncate(value, limit=160)
        return value

    @classmethod
    def truncate(cls, text: str, *, limit: int | None = None) -> str:
        max_length = limit or cls.max_string_length
        compact = " ".join(text.split())
        if len(compact) <= max_length:
            return compact
        return compact[: max_length - 3] + "..."

    @classmethod
    def is_sensitive_key(cls, key: str) -> bool:
        lowered = key.lower()
        return any(token in lowered for token in cls.sensitive_tokens)


class AgentLiveTraceEvent(BaseModel):
    """Agent 开发态实时追踪事件。"""

    sequence: int
    trace_id: str
    user_id: int | None = None
    session_id: str = ""
    message_preview: str = ""
    event_type: str
    stage: str = ""
    node_type: str = ""
    node_label: str = ""
    status: str = ""
    workflow_kind: str = ""
    step_id: str = ""
    tool_name: str = ""
    model_name: str = ""
    params_preview: Any = None
    observation_summary: str = ""
    error: str = ""
    duration_ms: float | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class AgentLiveTraceRecord(BaseModel):
    """单条 AutoGPT trace 的实时状态与事件 ring buffer。"""

    trace_id: str
    user_id: int | None = None
    session_id: str = ""
    message_preview: str = ""
    status: str = "running"
    current_stage: str = "session"
    current_node: str = ""
    workflow_kind: str = ""
    current_tool: str = ""
    event_count: int = 0
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    finished_at: str | None = None
    events: list[AgentLiveTraceEvent] = Field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        """导出列表页使用的紧凑状态。"""

        return {
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "message_preview": self.message_preview,
            "status": self.status,
            "current_stage": self.current_stage,
            "current_node": self.current_node,
            "workflow_kind": self.workflow_kind,
            "current_tool": self.current_tool,
            "event_count": self.event_count,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "finished_at": self.finished_at,
        }


class AgentLiveTraceRegistry:
    """进程内 live trace 注册表，服务开发态后台短轮询。"""

    terminal_statuses = {"completed", "failed", "cancelled"}

    def __init__(self, config: AgentLiveTraceConfig | None = None) -> None:
        self.config = config or AgentLiveTraceConfig.from_runtime()
        self._records: OrderedDict[str, AgentLiveTraceRecord] = OrderedDict()
        self._event_buffers: dict[str, deque[AgentLiveTraceEvent]] = {}
        self._finished_monotonic: dict[str, float] = {}
        self._subscribers: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._sequence = 0
        self._lock = RLock()

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def reload_config(self) -> AgentLiveTraceConfig:
        """重新读取运行时配置。"""

        with self._lock:
            self.config = AgentLiveTraceConfig.from_runtime()
            self.prune_locked()
            return self.config

    def start_trace(
        self,
        trace_id: str,
        *,
        user_id: int | None = None,
        session_id: str = "",
        message_preview: str = "",
    ) -> AgentLiveTraceRecord | None:
        """登记一条新 trace，并记录 turn_started 事件。"""

        if not self.enabled or not trace_id:
            return None
        with self._lock:
            self.prune_locked()
            record = AgentLiveTraceRecord(
                trace_id=trace_id,
                user_id=user_id,
                session_id=session_id,
                message_preview=AgentTraceRedactor.truncate(message_preview, limit=180),
            )
            self._records[trace_id] = record
            self._event_buffers[trace_id] = deque(maxlen=self.config.max_events_per_trace)
            self.emit_locked(
                trace_id,
                event_type="turn_started",
                stage="session",
                status="running",
                params_preview={"user_id": user_id, "session_id": session_id},
            )
            self.notify_locked({"type": "trace_started", "trace_id": trace_id})
            self.prune_locked()
            return self.snapshot_record_locked(trace_id)

    def emit(
        self,
        trace_id: str,
        *,
        event_type: str,
        stage: str = "",
        node_type: str = "",
        node_label: str = "",
        status: str = "",
        workflow_kind: str = "",
        step_id: str = "",
        tool_name: str = "",
        model_name: str = "",
        params_preview: Any = None,
        observation_summary: str = "",
        error: str | Exception = "",
        duration_ms: float | None = None,
    ) -> AgentLiveTraceEvent | None:
        """追加一条实时事件；未启用或 trace 不存在时静默跳过。"""

        if not self.enabled or not trace_id:
            return None
        with self._lock:
            event = self.emit_locked(
                trace_id,
                event_type=event_type,
                stage=stage,
                node_type=node_type,
                node_label=node_label,
                status=status,
                workflow_kind=workflow_kind,
                step_id=step_id,
                tool_name=tool_name,
                model_name=model_name,
                params_preview=params_preview,
                observation_summary=observation_summary,
                error=str(error) if error else "",
                duration_ms=duration_ms,
            )
            if event is not None:
                self.notify_locked({"type": "event", "trace_id": trace_id, "sequence": event.sequence})
            return event

    def emit_locked(
        self,
        trace_id: str,
        *,
        event_type: str,
        stage: str = "",
        node_type: str = "",
        node_label: str = "",
        status: str = "",
        workflow_kind: str = "",
        step_id: str = "",
        tool_name: str = "",
        model_name: str = "",
        params_preview: Any = None,
        observation_summary: str = "",
        error: str = "",
        duration_ms: float | None = None,
    ) -> AgentLiveTraceEvent | None:
        record = self._records.get(trace_id)
        if record is None:
            return None
        self._sequence += 1
        preview = AgentTraceRedactor.preview(
            params_preview,
            include_debug_preview=self.config.include_debug_preview,
        )
        event = AgentLiveTraceEvent(
            sequence=self._sequence,
            trace_id=trace_id,
            user_id=record.user_id,
            session_id=record.session_id,
            message_preview=record.message_preview,
            event_type=event_type,
            stage=stage,
            node_type=node_type,
            node_label=node_label,
            status=status,
            workflow_kind=workflow_kind,
            step_id=step_id,
            tool_name=tool_name,
            model_name=model_name,
            params_preview=preview,
            observation_summary=AgentTraceRedactor.truncate(observation_summary, limit=500),
            error=AgentTraceRedactor.truncate(error, limit=500),
            duration_ms=round(duration_ms, 3) if duration_ms is not None else None,
        )
        self._event_buffers.setdefault(trace_id, deque(maxlen=self.config.max_events_per_trace)).append(event)
        record.events = list(self._event_buffers[trace_id])
        record.event_count = len(record.events)
        record.updated_at = event.created_at
        if stage:
            record.current_stage = stage
        if node_label or node_type:
            record.current_node = node_label or node_type
        if workflow_kind:
            record.workflow_kind = workflow_kind
        if tool_name:
            record.current_tool = tool_name
        if status:
            record.status = self.resolve_record_status(event_type, status)
        self._records.move_to_end(trace_id)
        return event

    def finish_trace(self, trace_id: str, *, status: str = "completed", error: str | Exception = "") -> None:
        """标记 trace 结束并记录 turn_finished/turn_failed。"""

        if not self.enabled or not trace_id:
            return
        with self._lock:
            record = self._records.get(trace_id)
            if record is None:
                return
            event_type = "turn_failed" if status == "failed" else "turn_finished"
            self.emit_locked(
                trace_id,
                event_type=event_type,
                stage="session",
                status=status,
                error=str(error) if error else "",
            )
            record.status = status
            record.finished_at = datetime.now().isoformat()
            record.updated_at = record.finished_at
            self._finished_monotonic[trace_id] = time.monotonic()
            self.notify_locked({"type": "trace_finished", "trace_id": trace_id, "status": status})
            self.prune_locked()

    def list_traces(self) -> list[dict[str, Any]]:
        """返回 active 与 recent completed trace 摘要。"""

        if not self.enabled:
            return []
        with self._lock:
            self.prune_locked()
            return [record.summary() for record in reversed(self._records.values())]

    def get_trace(self, trace_id: str) -> AgentLiveTraceRecord | None:
        """读取单条 trace 详情。"""

        if not self.enabled:
            return None
        with self._lock:
            self.prune_locked()
            return self.snapshot_record_locked(trace_id)

    def status(self) -> dict[str, Any]:
        """返回 live trace 运行状态。"""

        with self._lock:
            self.prune_locked()
            active_count = sum(1 for record in self._records.values() if record.status not in self.terminal_statuses)
            return {
                "enabled": self.enabled,
                "max_traces": self.config.max_traces,
                "max_events_per_trace": self.config.max_events_per_trace,
                "retention_seconds": self.config.retention_seconds,
                "include_debug_preview": self.config.include_debug_preview,
                "active_count": active_count,
                "trace_count": len(self._records),
            }

    def clear(self) -> None:
        """清空内存注册表，主要用于测试。"""

        with self._lock:
            self._records.clear()
            self._event_buffers.clear()
            self._finished_monotonic.clear()
            self._sequence = 0
            self.notify_locked({"type": "cleared"})

    def subscribe(self) -> tuple[str, asyncio.Queue[dict[str, Any]]]:
        """订阅 live trace 更新事件。"""

        subscriber_id = uuid4().hex
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        with self._lock:
            self._subscribers[subscriber_id] = queue
        return subscriber_id, queue

    def unsubscribe(self, subscriber_id: str) -> None:
        """取消 live trace 更新订阅。"""

        with self._lock:
            self._subscribers.pop(subscriber_id, None)

    def prune_locked(self) -> None:
        now = time.monotonic()
        expired = [
            trace_id
            for trace_id, finished_at in self._finished_monotonic.items()
            if now - finished_at > self.config.retention_seconds
        ]
        for trace_id in expired:
            self.remove_locked(trace_id)

        while len(self._records) > self.config.max_traces:
            trace_id, _record = next(iter(self._records.items()))
            self.remove_locked(trace_id)

    def remove_locked(self, trace_id: str) -> None:
        self._records.pop(trace_id, None)
        self._event_buffers.pop(trace_id, None)
        self._finished_monotonic.pop(trace_id, None)

    def notify_locked(self, payload: dict[str, Any]) -> None:
        """向 WebSocket 订阅者广播轻量更新通知。"""

        if not self._subscribers:
            return
        message = dict(payload)
        message["created_at"] = datetime.now().isoformat()
        for queue in list(self._subscribers.values()):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                pass

    def snapshot_record_locked(self, trace_id: str) -> AgentLiveTraceRecord | None:
        record = self._records.get(trace_id)
        if record is None:
            return None
        snapshot = record.model_copy(deep=True)
        snapshot.events = list(self._event_buffers.get(trace_id, ()))
        snapshot.event_count = len(snapshot.events)
        return snapshot

    @staticmethod
    def resolve_record_status(event_type: str, status: str) -> str:
        if event_type == "turn_failed" or status == "failed":
            return "failed"
        if event_type == "turn_finished" or status in {"completed", "cancelled"}:
            return status
        return "running"


agent_live_trace_registry = AgentLiveTraceRegistry()
