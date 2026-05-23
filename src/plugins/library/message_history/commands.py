from __future__ import annotations

from typing import Optional

from nonebot_plugin_alconna import Args, Alconna, CommandMeta, Field, MultiVar

from src.platform.commands import CommandBinding, CommandParam, on_agent_command
from src.platform.config import comp_config, priority
from src.platform.helper import HelperScope

chat_context_command_kwargs = {
    "priority": priority,
    "block": True,
    "skip_for_unmatch": False,
    "comp_config": comp_config,
}

query_group_history_cmd = on_agent_command(
    Alconna(
        "检索群聊记录",
        Args["query", MultiVar(str, "*"), Field(default=(), completion="可选：输入关键词，例如 迟到、调课、值日")],
        meta=CommandMeta(
            description="检索当前系统群组的历史消息，用于回顾讨论内容。"
        ),
    ),
    aliases={"查询群聊记录", "回顾群聊", "群聊记录", "总结群聊"},
    binding=CommandBinding(
        description="检索当前系统群组的历史消息，可按关键词回顾刚才聊了什么。",
        scopes={HelperScope.public},
        tags={"chat", "group", "history"},
        execution_mode="service",
        params=[
            CommandParam(
                name="关键词",
                description="可选检索关键词；不提供时默认回顾最近群聊。",
                source_name="query",
                multiple=True,
            )
        ],
    ),
    **chat_context_command_kwargs,
)

chat_statistics_cmd = on_agent_command(
    Alconna(
        "统计聊天记录",
        Args["scope?", Optional[str], Field(default=None, completion="可选：user 或 group")],
        Args["window?", Optional[str], Field(default=None, completion="可选：all、today、yesterday 或 week")],
        meta=CommandMeta(description="统计当前用户或当前系统群的消息数量。"),
    ),
    aliases={"聊天统计", "消息统计", "统计群聊", "统计私聊"},
    binding=CommandBinding(
        description="统计当前私聊或系统群的消息数量，可按今天、昨天、本周筛选。",
        scopes={HelperScope.public},
        tags={"chat", "statistics", "history"},
        execution_mode="service",
        params=[
            CommandParam(
                name="范围",
                description="统计范围：user 表示当前用户私聊；group 表示当前绑定系统群。",
                source_name="scope",
                required=False,
            ),
            CommandParam(
                name="时间范围",
                description="统计时间范围：all、today、yesterday 或 week。",
                source_name="window",
                required=False,
            ),
        ],
    ),
    **chat_context_command_kwargs,
)

__helpers__ = [query_group_history_cmd.__helper__, chat_statistics_cmd.__helper__]

__all__ = ["query_group_history_cmd", "chat_statistics_cmd", "__helpers__"]
