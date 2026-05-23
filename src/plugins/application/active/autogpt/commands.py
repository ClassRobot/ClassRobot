from src.platform.commands import CommandBinding, on_agent_command
from src.platform.config import priority
from src.platform.helper import HelperScope
from src.core.auth import UserRole

clear_chat = on_agent_command(
    "清空聊天",
    aliases={"重置聊天", "聊天清空", "聊天重置"},
    binding=CommandBinding(
        description="清空当前用户与机器人的对话上下文，用于重新开始聊天。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        risk_level="medium",
        agent_callable=False,
    ),
    priority=priority,
    block=True,
)

__helpers__ = [clear_chat.__helper__]

__all__ = ["clear_chat", "__helpers__"]
