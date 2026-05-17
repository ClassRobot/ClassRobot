from __future__ import annotations

from nonebot_plugin_alconna import Args, Alconna, CommandMeta, Field, MultiVar

from utils.commands import CommandBinding, CommandParam, on_agent_command
from utils.config import comp_config, priority
from utils.helper import HelperScope

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
            description="检索当前已绑定系统群组的近期采集消息，用于回顾争议点、谁说过什么、刚才聊了什么。"
        ),
    ),
    aliases={"查询群聊记录", "回顾群聊", "群聊记录", "总结群聊"},
    binding=CommandBinding(
        description="检索当前已绑定系统群组的近期采集消息，用于回顾争议点、谁说过什么、刚才聊了什么。",
        ai_description="当用户询问当前已绑定系统群组里刚才、之前、最近讨论过什么，或谁说过什么时，优先调用该命令检索群环境采集消息。该命令依赖系统内 Group 绑定，而不是直接读取平台群 ID；如果没有明显关键词，可以直接使用用户原话或留空回顾最近消息。",
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

__helpers__ = [query_group_history_cmd.__helper__]

__all__ = ["query_group_history_cmd", "__helpers__"]
