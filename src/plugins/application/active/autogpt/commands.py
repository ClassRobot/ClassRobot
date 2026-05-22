from src.platform.commands import CommandBinding, on_agent_command
from src.platform.config import priority
from src.platform.helper import HelperScope
from src.core.auth import UserRole

clear_chat = on_agent_command(
    "清空聊天",
    aliases={"重置聊天", "聊天清空", "聊天重置"},
    binding=CommandBinding(
        description="清空机器人与当前用户的聊天记录。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        ai_description="当用户要求清空当前对话上下文、重置聊天状态或丢弃之前的聊天内容时，优先使用该命令。",
        risk_level="medium",
        agent_callable=False,
    ),
    priority=priority,
    block=True,
)

__helpers__ = [clear_chat.__helper__]

__all__ = ["clear_chat", "__helpers__"]
