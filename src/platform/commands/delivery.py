from __future__ import annotations

from nonebot_plugin_alconna import UniMessage

from .result import CommandResult


def command_result_text(result: CommandResult) -> str:
    """把命令结果转换成用户可见纯文本。"""

    if result.visible_outputs:
        return "\n".join(result.visible_outputs)
    return result.summary or "命令执行完成。"


async def send_command_result(matcher, result: CommandResult) -> None:
    """通过当前 matcher 发送统一命令结果并结束处理。"""

    await matcher.finish(UniMessage(command_result_text(result)))
