from __future__ import annotations


def test_live_trace_disabled_is_noop(loaded_plugins) -> None:
    from src.core.agent.runtime.live_trace import AgentLiveTraceConfig, AgentLiveTraceRegistry

    _ = loaded_plugins
    registry = AgentLiveTraceRegistry(AgentLiveTraceConfig(enabled=False))

    assert registry.start_trace("trace-disabled", user_id=1, message_preview="hello") is None
    assert registry.emit("trace-disabled", event_type="node_entered") is None
    assert registry.list_traces() == []
    assert registry.status()["enabled"] is False


def test_live_trace_records_and_finishes_trace(loaded_plugins) -> None:
    from src.core.agent.runtime.live_trace import AgentLiveTraceConfig, AgentLiveTraceRegistry

    _ = loaded_plugins
    registry = AgentLiveTraceRegistry(
        AgentLiveTraceConfig(enabled=True, max_traces=5, max_events_per_trace=10, retention_seconds=60)
    )

    registry.start_trace("trace-1", user_id=7, session_id="7", message_preview="你好")
    registry.emit(
        "trace-1",
        event_type="node_entered",
        stage="route",
        node_type="intent_route",
        node_label="IntentRouteNode",
        status="running",
    )
    registry.emit(
        "trace-1",
        event_type="mcp_call_started",
        stage="tool_call",
        tool_name="browser_search",
        params_preview={"query": "最近热点"},
    )
    registry.finish_trace("trace-1", status="completed")

    traces = registry.list_traces()
    assert len(traces) == 1
    assert traces[0]["trace_id"] == "trace-1"
    assert traces[0]["status"] == "completed"
    detail = registry.get_trace("trace-1")
    assert detail is not None
    assert [event.event_type for event in detail.events] == [
        "turn_started",
        "node_entered",
        "mcp_call_started",
        "turn_finished",
    ]


def test_live_trace_subscriber_receives_lightweight_updates(loaded_plugins) -> None:
    from src.core.agent.runtime.live_trace import AgentLiveTraceConfig, AgentLiveTraceRegistry

    _ = loaded_plugins
    registry = AgentLiveTraceRegistry(AgentLiveTraceConfig(enabled=True, max_traces=5, max_events_per_trace=10))
    subscriber_id, queue = registry.subscribe()
    try:
        registry.start_trace("trace-ws")
        registry.emit("trace-ws", event_type="mcp_call_started", stage="tool_call", tool_name="browser_search")

        assert queue.get_nowait()["type"] == "trace_started"
        event_update = queue.get_nowait()
        assert event_update["type"] == "event"
        assert event_update["trace_id"] == "trace-ws"
        assert event_update["sequence"] == 2
    finally:
        registry.unsubscribe(subscriber_id)


def test_live_trace_prunes_trace_capacity(loaded_plugins) -> None:
    from src.core.agent.runtime.live_trace import AgentLiveTraceConfig, AgentLiveTraceRegistry

    _ = loaded_plugins
    registry = AgentLiveTraceRegistry(AgentLiveTraceConfig(enabled=True, max_traces=2))

    registry.start_trace("trace-1")
    registry.start_trace("trace-2")
    registry.start_trace("trace-3")

    assert [item["trace_id"] for item in registry.list_traces()] == ["trace-3", "trace-2"]
    assert registry.get_trace("trace-1") is None


def test_redactor_masks_secret_values_and_truncates_text(loaded_plugins) -> None:
    from src.core.agent.runtime.live_trace import AgentTraceRedactor

    _ = loaded_plugins
    preview = AgentTraceRedactor.preview(
        {
            "authorization": "Bearer abc",
            "nested": {"api_key": "secret", "query": "x" * 700},
            "items": list(range(30)),
        }
    )

    assert preview["authorization"] == "***"
    assert preview["nested"]["api_key"] == "***"
    assert preview["nested"]["query"].endswith("...")
    assert preview["items"][-1].startswith("... ")
