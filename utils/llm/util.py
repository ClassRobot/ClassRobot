import re
import json

from nonebot import logger
from nonebot_plugin_alconna import Text, Image, Reply, UniMessage

from .schema import Content


def uni_message_to_contents(messages: UniMessage | str) -> list[Content]:
    if isinstance(messages, str):
        return [Content(type="text", value=messages)]
    contexts = []
    for msg in messages:
        if isinstance(msg, Text):
            contexts.append(Content(type="text", value=msg.text))
        elif isinstance(msg, Image) and msg.url:
            contexts.append(Content(type="image", value=msg.url))
        elif isinstance(msg, Reply):
            if msg.msg is None:
                continue
            contexts.append(Content(type="text", value="<reference_message>"))
            if isinstance(msg.msg, str):
                contexts.append(Content(type="text", value=msg.msg))
            else:
                contexts.extend(
                    uni_message_to_contents(
                        messages=UniMessage.generate_sync(message=msg.msg)
                    )
                )
            contexts.append(Content(type="text", value="</reference_message>"))
    return contexts


def contents_to_uni_message(contents: list[Content]) -> UniMessage:
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
    # 使用正则表达式替换所有的反斜杠，但保留转义字符
    return re.sub(r"\\(?![nrtbfv](?![a-zA-Z]))", r"\\\\", content)


def json_loads(content: str) -> dict:
    """用于解析llm发送过来的json数据"""
    contents = content.split("\n")
    start, end = 0, len(contents)
    for i, v in enumerate(contents):
        if v.startswith("```json"):
            start = i + 1
        if v.endswith("```"):
            end = i
    content = "\n".join(contents[start:end]).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return json.loads(escape_backslashes(content))
