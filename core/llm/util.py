import json
import re
from typing import Iterable

from nonebot import logger
from nonebot_plugin_alconna import File, Image, Reply, Text, UniMessage

from .message import Content


def uni_message_to_contents(
    messages: Iterable[str | Image | Text] | UniMessage | str,
) -> list[Content]:
    """将统一消息转换为内容列表。"""

    if isinstance(messages, UniMessage):
        messages = messages.replace("<reference_message>", "").replace("</reference_message>", "")
    if isinstance(messages, str):
        return [Content(type="text", value=messages)]

    contexts = []
    for msg in messages:
        if isinstance(msg, str):
            contexts.append(Content(type="text", value=msg))
        elif isinstance(msg, Text):
            contexts.append(Content(type="text", value=msg.text))
        elif isinstance(msg, Image) and msg.url:
            contexts.append(Content(type="image", value=msg.url))
        elif isinstance(msg, File) and msg.url:
            contexts.append(Content(type="file", value=msg.url))
        elif isinstance(msg, Reply):
            if msg.msg is None:
                continue
            contexts.append(Content(type="text", value="<reference_message>"))
            if isinstance(msg.msg, str):
                contexts.append(Content(type="text", value=msg.msg))
            else:
                contexts.extend(uni_message_to_contents(messages=UniMessage.generate_sync(message=msg.msg)))
            contexts.append(Content(type="text", value="</reference_message>"))
    return contexts


def contents_to_uni_message(contents: list[Content]) -> UniMessage:
    """将内容列表转换为统一消息。"""

    messages = UniMessage()
    for content in contents:
        if content.type == "text":
            messages += UniMessage.text(content.value)
        elif content.type == "image":
            messages += UniMessage.image(content.value)
        elif content.type == "file":
            messages += UniMessage.file(content.value)
        else:
            logger.warning(f"未知的消息类型: {content.type}")
    return messages


def escape_backslashes(content: str) -> str:
    """转义 JSON 字符串中的反斜杠。"""

    return re.sub(r"\\(?![nrtbfv](?![a-zA-Z]))", r"\\\\", content)


def load_json_object(content: str) -> dict:
    """解析 JSON 字符串，必要时补做反斜杠兼容处理。"""

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return json.loads(escape_backslashes(content))


def json_loads(content: str) -> dict:
    """解析大语言模型返回的 JSON 数据。"""

    try:
        return load_json_object(content)
    except json.decoder.JSONDecodeError as error:
        contents = content[content.find("{") :].split("}")
        for index in range(len(contents), 0, -1):
            candidate = "}".join(contents[:index]).strip() + "}"
            if not candidate:
                continue
            try:
                return load_json_object(candidate)
            except Exception:
                continue
        raise error
