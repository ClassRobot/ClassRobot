from __future__ import annotations

import json
import hashlib
from enum import StrEnum
from datetime import datetime
from typing import Any, Union, Literal, Iterator, TypeAlias

from pydantic import Field, BaseModel

from .typings import ChatCompletionMessage, ChatCompletionMessageParam


class LLMRole(StrEnum):
    """定义大模型消息在对话上下文中的角色类型。"""

    user = "user"
    tool = "tool"
    system = "system"
    assistant = "assistant"


class Content(BaseModel):
    """表示一段消息内容，可承载文本、图片或文件引用。"""

    type: Literal["text", "image", "file"] = Field(description="消息类型")
    value: str = Field(description="消息内容，如果不是 text 类型则为 URL")

    def __len__(self) -> int:
        """返回当前内容值的长度。"""

        return len(self.value)


ContentType: TypeAlias = str | list[Content] | Content


class ContextSchema(BaseModel):
    """描述消息上下文的基础字段，供具体消息对象扩展。"""

    role: LLMRole = Field(description="消息角色")
    content: ContentType = Field(description="消息内容")


class Context(ContextSchema):
    """表示对话中的一条消息，并记录工具调用等附加信息。"""

    tool_call_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    context_md5: str | None = None

    @property
    def md5(self) -> str:
        """返回当前消息内容的摘要值。"""

        if self.context_md5 is None:
            payload = json.dumps(
                self.model_dump(mode="json", include={"role", "content"}),
                ensure_ascii=False,
                default=str,
            )
            self.context_md5 = hashlib.md5(payload.encode("utf-8")).hexdigest()
        return self.context_md5

    async def multi_modal(self) -> str | list[dict[str, Any]]:
        """将当前消息转换为多模态模型可接收的内容结构。"""

        if isinstance(self.content, str):
            return self.content
        data = []
        for msg in [self.content] if isinstance(self.content, Content) else self.content:
            if msg.type == "image":
                data.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": msg.value,
                        },
                    }
                )
            elif msg.type == "text":
                data.append({"type": "text", "text": msg.value})
            if msg.type != "text":
                data.append({"type": "text", "text": f"![{msg.type}]({msg.value})"})
        return data

    def single_modal(self) -> str:
        """将当前消息压平为单模态字符串表示。"""

        if isinstance(self.content, str):
            return self.content

        data = []
        for msg in [self.content] if isinstance(self.content, Content) else self.content:
            if msg.type == "text":
                data.append(msg.value)
            else:
                data.append(f"![{msg.type}]({msg.value})")
        return "\n".join(data)

    def text_only(self) -> bool:
        """判断当前消息是否只包含文本内容。"""

        if isinstance(self.content, str):
            return True
        if isinstance(self.content, Content):
            return self.content.type == "text"
        return all(msg.type == "text" for msg in self.content)

    def __len__(self) -> int:
        """返回消息内容的长度。"""

        if isinstance(self.content, str):
            return len(self.content.encode("utf-8"))
        return sum(len(msg) for msg in self.content)

    def model_dump(self, *args, **kwargs) -> dict:
        """导出适用于模型请求的消息字典。"""

        data = super().model_dump(
            *args,
            **(kwargs | {"include": {"role", "content"}}),
        )
        if self.role == LLMRole.tool:
            data["tool_call_id"] = self.tool_call_id
        return data

    def __eq__(self, value: object) -> bool:
        """比较两条消息的角色与内容是否一致。"""

        if not isinstance(value, Context):
            return False
        return self.md5 == value.md5


class Messages(BaseModel):
    """封装多轮对话消息集合，并提供筛选、追加与格式转换能力。"""

    messages: list[Context | ChatCompletionMessage] = Field(default_factory=list)

    async def build_messages(self, is_multi_modal: bool = False) -> list[ChatCompletionMessageParam]:
        """将消息集合转换为模型接口需要的消息列表。"""

        messages = []
        message_count = len(self.messages)
        for index, ctx in enumerate(self.messages):
            msg_dict = None
            if isinstance(ctx, Context):
                msg_dict = ctx.model_dump()
                msg_dict["content"] = ctx.single_modal()
                if index == message_count - 1 and is_multi_modal:
                    msg_dict["content"] = await ctx.multi_modal()
            messages.append(msg_dict or ctx)
        return messages

    def get(self, *role: LLMRole) -> "Messages":
        """筛选指定角色的消息。"""

        return Messages(messages=[msg for msg in self.messages if isinstance(msg, Context) and msg.role in role])

    def get_exclude(self, *role: LLMRole) -> "Messages":
        """排除指定角色后返回其余消息。"""

        return Messages(messages=[msg for msg in self.messages if not (isinstance(msg, Context) and msg.role in role)])

    def text_only(self) -> bool:
        """判断整个消息集合是否只包含文本消息。"""

        for msg in self.messages:
            if isinstance(msg, Context) and not msg.text_only():
                return False
        return True

    def extend(self, messages: Union["Messages", list[Context | ChatCompletionMessage]]) -> None:
        """向当前集合追加另一组消息。"""

        if isinstance(messages, Messages):
            messages = messages.messages
        self.messages.extend(messages)

    def char_length(self, *role: LLMRole) -> int:
        """统计消息字符长度。"""

        return sum(
            len(message)
            for message in self.messages
            if isinstance(message, Context) and (not role or message.role in role)
        )

    def remove(self, obj: int | Context | ChatCompletionMessage) -> None:
        """移除指定消息或索引位置的消息。"""

        if isinstance(obj, Context) and obj.role == LLMRole.system:
            return
        if isinstance(obj, int):
            self.messages.pop(obj)
        else:
            self.messages.remove(obj)

    def add_message(
        self,
        role: LLMRole,
        content: ContentType,
        tool_call_id: str | None = None,
    ) -> Context:
        """添加一条标准上下文消息。"""

        context = Context(role=role, content=content, tool_call_id=tool_call_id)
        self.messages.append(context)
        return context

    def add_tool(self, context: ChatCompletionMessage) -> None:
        """追加模型返回的工具调用消息。"""

        self.messages.append(context)

    def user_message(self, content: ContentType) -> Context:
        """添加用户消息。"""

        return self.add_message(role=LLMRole.user, content=content)

    def system_message(self, content: ContentType) -> Context:
        """添加系统消息。"""

        return self.add_message(role=LLMRole.system, content=content)

    def assistant_message(self, content: ContentType) -> Context:
        """添加助手消息。"""

        return self.add_message(role=LLMRole.assistant, content=content)

    def tool_message(self, tool_call_id: str, content: str) -> Context:
        """添加工具消息。"""

        return self.add_message(role=LLMRole.tool, content=content, tool_call_id=tool_call_id)

    def __repr__(self) -> str:
        """返回调试字符串表示。"""

        return self.messages.__repr__()

    def __str__(self) -> str:
        """返回字符串表示。"""

        return self.__repr__()

    def __getitem__(self, item: int) -> Context | ChatCompletionMessage:
        """按索引获取消息。"""

        return self.messages[item]

    def clear(self) -> None:
        """清空当前消息集合。"""

        self.messages.clear()

    def __bool__(self) -> bool:
        """返回布尔值。"""

        return bool(self.messages)

    def __iter__(self) -> Iterator[Context | ChatCompletionMessage]:
        """返回消息集合的迭代器。"""

        return self.messages.__iter__()
