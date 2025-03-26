import hashlib
from datetime import datetime
from typing import Union, Literal, Iterator, TypeAlias

from strenum import StrEnum
from pydantic import Field, BaseModel

from .typings import ChatCompletionMessage, ChatCompletionMessageParam

# from pydantic.json_schema import SkipJsonSchema


class Role(StrEnum):
    user = "user"
    tool = "tool"
    system = "system"
    assistant = "assistant"


class Content(BaseModel):
    """消息内容"""

    type: Literal["text", "image", "file"] = Field(description="消息类型")
    value: str = Field(description="消息内容,如果不是text类型,则为url")

    def __len__(self):
        return len(self.value)


ContentType: TypeAlias = str | list[Content]


class ContextSchema(BaseModel):
    role: Role = Field(description="消息角色")
    content: list[Content] | str | Content = Field(description="消息内容")


class Context(ContextSchema):
    """一段消息的上下文"""

    tool_call_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    context_md5: str | None = None

    @property
    def md5(self) -> str:
        if self.context_md5 is None:
            self.context_md5 = hashlib.md5(self.json(include={"role", "content"}).encode("utf-8")).hexdigest()
        return self.context_md5

    async def multi_modal(self) -> ContentType:
        """多模态消息"""
        if isinstance(self.content, str):
            return self.content
        elif isinstance(self.content, Content):
            content = [self.content]
        else:
            content = self.content
        data = []
        for msg in content:
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
        """单模态消息"""
        if isinstance(self.content, str):
            return self.content
        elif isinstance(self.content, Content):
            content = [self.content]
        else:
            content = self.content

        contents = []
        for msg in content:
            if msg.type == "text":
                contents.append(msg.value)
            else:
                # 采用md的img格式
                contents.append(f"![{msg.type}]({msg.value})")
        return "\n".join(contents)

    def text_only(self) -> bool:
        """是否只有文本消息"""
        if isinstance(self.content, str):
            return True
        elif isinstance(self.content, Content):
            return self.content.type == "text"
        for msg in self.content:
            if msg.type != "text":
                return False
        return True

    def __len__(self):
        if isinstance(self.content, str):
            return len(self.content.encode("utf-8"))
        return sum(len(msg) for msg in self.content)

    def dict(self):
        data = super().dict(include={"role", "content"})
        if self.role == Role.tool:
            data["tool_call_id"] = self.tool_call_id
        return data

    def __eq__(self, value: "Context") -> bool:
        return self.md5 == value.md5


print(Context.parse_obj({"role": "user", "content": {"type": "text", "value": "申请学校的半工半读"}}))


class Messages(BaseModel):
    messages: list[Context | ChatCompletionMessage] = []

    async def build_messages(self, is_multi_modal: bool = False) -> list[ChatCompletionMessageParam]:
        """打包消息

        Args:
            is_multi_modal (bool, optional): 是否多模态消息. Defaults to False.

        Returns:
            list[ChatCompletionMessageParam]: 消息列表
        """
        messages = []
        msg_len = len(self.messages)
        for i, ctx in enumerate(self.messages):
            msg_dict = None
            if isinstance(ctx, Context):
                msg_dict = ctx.dict()
                msg_dict["content"] = ctx.single_modal()
                if i == msg_len - 1 and is_multi_modal:  # 最后一条消息
                    msg_dict["content"] = await ctx.multi_modal()
            messages.append(msg_dict or ctx)
        return messages

    def get(self, *role: Role) -> "Messages":
        """通过角色获取消息"""
        return Messages(messages=[msg for msg in self.messages if isinstance(msg, Context) and msg.role in role])

    def get_exclude(self, *role: Role) -> "Messages":
        """通过角色排除消息"""
        return Messages(messages=[msg for msg in self.messages if not (isinstance(msg, Context) and msg.role in role)])

    def text_only(self) -> bool:
        """是否只有文本消息"""
        for msg in self.messages:
            if isinstance(msg, Context) and not msg.text_only():
                return False
        return True

    def extend(self, messages: Union["Messages", list[Context | ChatCompletionMessage]]):
        """扩展消息"""
        if isinstance(messages, Messages):
            messages = messages.messages
        self.messages.extend(messages)

    def char_length(self, *role: Role) -> int:
        return sum(
            len(message)
            for message in self.messages
            if isinstance(message, Context) and (not role or message.role in role)
        )

    def remove(self, obj: int | Context | ChatCompletionMessage):
        if isinstance(obj, Context) and obj.role == Role.system:
            return
        if isinstance(obj, int):
            self.messages.pop(obj)
        else:
            self.messages.remove(obj)

    def add_message(
        self,
        role: Role,
        content: str | list[Content],
        tool_call_id: str | None = None,
    ) -> Context:
        context = Context(role=role, content=content, tool_call_id=tool_call_id)
        self.messages.append(context)
        return context

    def add_tool(self, context: ChatCompletionMessage):
        """添加工具消息"""
        self.messages.append(context)

    def user_message(self, content: ContentType) -> Context:
        return self.add_message(role=Role.user, content=content)

    def system_message(self, content: ContentType) -> Context:
        return self.add_message(role=Role.system, content=content)

    def assistant_message(self, content: ContentType) -> Context:
        return self.add_message(role=Role.assistant, content=content)

    def tool_message(self, tool_call_id: str, content: str) -> Context:
        return self.add_message(role=Role.tool, content=content, tool_call_id=tool_call_id)

    def __repr__(self) -> str:
        return self.get(Role.user, Role.assistant, Role.tool).messages.__repr__()

    def __str__(self) -> str:
        return self.__repr__()

    def __getitem__(self, item: int) -> Context | ChatCompletionMessage:
        return self.messages[item]

    def clear(self):
        self.messages.clear()

    def __bool__(self) -> bool:
        return bool(self.messages)

    def __iter__(self) -> Iterator[Context | ChatCompletionMessage]:
        return self.messages.__iter__()
