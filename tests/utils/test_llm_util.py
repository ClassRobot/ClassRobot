def test_json_loads_extracts_json_from_code_fence(loaded_plugins):
    from src.core.llm.util import json_loads

    payload = """```json
{"intent":"chat","reason":"普通问候"}
```"""

    assert json_loads(payload) == {"intent": "chat", "reason": "普通问候"}


def test_json_loads_repairs_truncated_json_string(loaded_plugins):
    from src.core.llm.util import json_loads

    payload = '{"intent":"complex_task","reason":"模型输出被截断'

    assert json_loads(payload) == {
        "intent": "complex_task",
        "reason": "模型输出被截断",
    }


def test_json_loads_extracts_first_balanced_object_from_noise(loaded_plugins):
    from src.core.llm.util import json_loads

    payload = '先说明一下 {"intent":"command","requires_command":true} 其余内容忽略'

    assert json_loads(payload) == {
        "intent": "command",
        "requires_command": True,
    }
