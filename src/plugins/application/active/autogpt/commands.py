from src.core.auth import UserRole
from src.platform.config import priority
from src.platform.helper import HelperScope
from src.platform.commands import CommandBinding, on_agent_command

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

__all__ = ["clear_chat"]
