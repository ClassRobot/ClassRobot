from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from src.platform.helper import Helpers, UserRole, HelperScope

from tests.autogpt.command_tool_helpers import ensure_service_helper


def build_helpers_with_semantic_commands() -> Helpers:
    """构造 Agent 语义决策测试使用的命令目录。"""

    helpers = Helpers()
    helpers.extend(
        [
            ensure_service_helper(
                "我的信息",
                "查看自己的账号信息、当前角色、是否为管理员、是否为教师或学生",
                aliases={"个人信息", "用户信息"},
                roles={UserRole.user},
                scopes={HelperScope.user},
            ),
            ensure_service_helper(
                "查询班级",
                "查询自己创建、管理或加入的班级列表",
                aliases={"我的班级", "班级列表"},
                roles={UserRole.teacher},
                scopes={HelperScope.teacher},
            ),
            ensure_service_helper(
                "查询课表",
                "查询本人今天、明天、后天或指定日期的课表",
                aliases={"我的课表", "查看课表"},
                roles={UserRole.user},
                scopes={HelperScope.user},
            ),
            ensure_service_helper(
                "统计聊天记录",
                "统计当前用户私聊或当前系统群的消息数量",
                aliases={"聊天统计", "消息统计", "统计群聊", "统计私聊"},
                roles={UserRole.user},
                scopes={HelperScope.public},
            ),
        ]
    )
    return helpers


def llm_response(content: str) -> SimpleNamespace:
    """构造 OpenAI SDK 风格的最小测试响应。"""

    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def patch_pipeline_llm(monkeypatch: pytest.MonkeyPatch, responses: list[str]) -> list[str]:
    """让 Pipeline、ExtractAgent 和 AutoTaskAgent 共用同一组模拟响应。"""

    import src.core.agent.builtin.planning as planning_module
    from src.core.agent.runtime import pipeline as pipeline_module
    import src.core.agent.builtin.conversation as conversation_module

    calls: list[str] = []

    async def fake_client_create(*args, **kwargs):
        calls.append(str(kwargs.get("task_type") or "unknown"))
        if not responses:
            raise AssertionError("fake LLM responses exhausted")
        return llm_response(responses.pop(0))

    monkeypatch.setattr(pipeline_module, "client_create", fake_client_create)
    monkeypatch.setattr(planning_module, "client_create", fake_client_create)
    monkeypatch.setattr(conversation_module, "client_create", fake_client_create)
    return calls


def route_response(*, reason: str = "用户需要调用项目命令") -> str:
    """生成命令型入口路由响应。"""

    return json.dumps(
        {
            "intent": "command",
            "reply": None,
            "requires_rag": False,
            "requires_command": True,
            "need_confirm": False,
            "reason": reason,
            "knowledge_sources": [],
        },
        ensure_ascii=False,
    )


def extract_response(text: str) -> str:
    """生成抽取上下文响应。"""

    return json.dumps(
        {"role": "user", "content": [{"type": "text", "value": text}]},
        ensure_ascii=False,
    )


def plan_response(command: str, goal: str) -> str:
    """生成 Planner 响应。"""

    return json.dumps(
        {
            "goal": goal,
            "facts": [],
            "missing_info": [],
            "risk_level": "low",
            "requires_rag": False,
            "requires_command": True,
            "should_execute": True,
            "candidate_commands": [command],
            "candidate_skills": [],
            "steps": [f"调用{command}"],
            "confirmation_question": None,
            "reason": "根据当前可用命令目录语义选择命令。",
        },
        ensure_ascii=False,
    )


def task_response(command: str, reply: str, params: list[str] | None = None) -> str:
    """生成 AutoTaskAgent 响应。"""

    params = params or []
    task_params = [{"type": "text", "separate": False, "value": value} for value in params]
    payload = {
        "reply": reply,
        "tasks": [{"command": command, "params": task_params}],
        "need_confirm": False,
        "is_violation": False,
    }
    return reply + "\n<hr/>\n" + json.dumps(payload, ensure_ascii=False)
