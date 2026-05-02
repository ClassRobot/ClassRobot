import json


def test_record_observations_writes_traceable_context(loaded_plugins):
    from utils.helper import Helpers
    from src.plugins.autogpt.util import ChatSession
    from src.plugins.autogpt.schema import CommandObservation, Param

    session = ChatSession(user_id=1, helpers=Helpers())
    session.last_trace_id = "autogpt-test"

    session.record_observations(
        [
            CommandObservation(
                trace_id="autogpt-test",
                command="查询课表",
                params=[Param(type="text", value="今天")],
                success=True,
                message="命令已投递给 NoneBot 事件系统。",
            )
        ]
    )

    messages = session.messages.messages
    assert len(messages) == 1
    content = messages[0].single_modal()
    assert content.startswith("# 系统命令执行观察\ntrace_id: autogpt-test\n")

    payload = json.loads(content.split("\n", 2)[2])
    assert payload[0]["trace_id"] == "autogpt-test"
    assert payload[0]["command"] == "查询课表"
    assert payload[0]["success"] is True
