import re
import json
from typing import Iterable

from nonebot import logger
from nonebot_plugin_alconna import File, Text, Image, Reply, UniMessage

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
                contexts.extend(uni_message_to_contents(messages=UniMessage.of(msg.msg)))
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


def strip_json_code_fence(content: str) -> str:
    """移除模型常见的 Markdown JSON 代码块包装。"""

    stripped = content.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) < 3 or lines[-1].strip() != "```":
        return stripped
    return "\n".join(lines[1:-1]).strip()


def extract_first_json_object(content: str) -> str | None:
    """从混杂文本中提取首个括号平衡的 JSON 对象。"""

    start = content.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(content[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return content[start : index + 1]

    return None


def repair_truncated_json_object(content: str) -> str | None:
    """尝试修复末尾截断的 JSON 对象。"""

    start = content.find("{")
    if start < 0:
        return None

    candidate = content[start:].strip()
    if not candidate:
        return None

    depth = 0
    in_string = False
    escaped = False
    for char in candidate:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth = max(depth - 1, 0)

    if in_string:
        candidate += '"'
    candidate = re.sub(r",\s*$", "", candidate)
    candidate = re.sub(r",\s*}", "}", candidate)
    candidate += "}" * depth
    return candidate


def load_json_object(content: str) -> dict:
    """解析 JSON 字符串，必要时补做反斜杠兼容处理。"""

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return json.loads(escape_backslashes(content))


def json_loads(content: str) -> dict:
    """解析大语言模型返回的 JSON 数据。"""

    normalized = strip_json_code_fence(content)
    try:
        return load_json_object(normalized)
    except json.decoder.JSONDecodeError as error:
        candidates = [
            extract_first_json_object(normalized),
            repair_truncated_json_object(normalized),
        ]
        for candidate in candidates:
            if not candidate:
                continue
            try:
                return load_json_object(candidate)
            except Exception:
                continue
        raise error
