import hashlib
from datetime import datetime
from functools import lru_cache
from typing import Union, Literal, TypeAlias

from strenum import StrEnum
from pydantic import Field, BaseModel

from .typings import ChatCompletionMessage, ChatCompletionMessageParam


class Role(StrEnum):
    user = "user"
    tool = "tool"
    system = "system"
    assistant = "assistant"


class Content(BaseModel):
    type: Literal["text", "image", "file"]
    value: str

    def __len__(self):
        return len(self.value)


ContentType: TypeAlias = str | list[Content]


class Context(BaseModel):
    role: Role
    content: str | list[Content]
    tool_call_id: str | None = None
    priority: int = 10
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    @lru_cache
    def md5(self) -> str:
        return hashlib.md5(self.json(include={"role", "content"}).encode("utf-8")).hexdigest()

    async def multi_modal(self) -> ContentType:
        """多模态消息"""
        if isinstance(self.content, str):
            return self.content
        data = []
        for msg in self.content:
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

        content = []
        for msg in self.content:
            if msg.type == "text":
                content.append(msg.value)
            else:
                # 采用md的img格式
                content.append(f"![{msg.type}]({msg.value})")
        return "\n".join(content)

    def text_only(self) -> bool:
        """是否只有文本消息"""
        if isinstance(self.content, str):
            return True
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

    def text_only(self) -> bool:
        """是否只有文本消息"""
        if isinstance(self.messages[-1], Context):
            return self.messages[-1].text_only()
        return True

    def extend(self, messages: Union["Messages", list[Context | ChatCompletionMessage]]):
        """扩展消息"""
        if isinstance(messages, Messages):
            messages = messages.messages
        self.messages.extend(messages)

    @property
    def max_length(self) -> int:
        return 30000

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
        priority: int = 1,
    ) -> Context:
        if self.char_length() > self.max_length:  # 超出长度
            self.delete_messages(0.5)
        context = Context(role=role, content=content, priority=priority, tool_call_id=tool_call_id)
        self.messages.append(context)
        print(self.char_length(), role, self)
        return context

    def add_tool(self, context: ChatCompletionMessage):
        """添加工具消息"""
        self.messages.append(context)

    def delete_messages(self, per: float = 0.5):
        """删除一定比例的消息"""
        char_length = self.char_length()
        remaining_length = char_length - int(char_length * per)
        # 需要删除到剩余数量
        while char_length > remaining_length and len(self.messages) > 1:
            # 从后往前删除消息

            messages = self.messages.copy()
            messages.reverse()
            for ctx in messages:
                # 当删除到用户消息时停止
                if isinstance(ctx, Context) and ctx.role == Role.user:
                    self.remove(ctx)
                    break
                self.remove(ctx)

            char_length = self.char_length()

    def user_message(self, content: ContentType, priority: int = 1) -> Context:
        return self.add_message(role=Role.user, content=content, priority=priority)

    def system_message(self, content: ContentType, priority: int = 1000) -> Context:
        return self.add_message(role=Role.system, content=content, priority=priority)

    def assistant_message(self, content: ContentType, priority: int = 1) -> Context:
        return self.add_message(role=Role.assistant, content=content, priority=priority)

    def tool_message(self, tool_call_id: str, content: str, priority: int = 1) -> Context:
        return self.add_message(
            role=Role.tool,
            content=content,
            tool_call_id=tool_call_id,
            priority=priority,
        )

    def __repr__(self) -> str:
        return self.get(Role.user, Role.assistant, Role.tool).messages.__repr__()

    def __str__(self) -> str:
        return self.__repr__()

    def __getitem__(self, item: int) -> Context | ChatCompletionMessage:
        return self.messages[item]

    def __bool__(self) -> bool:
        return bool(self.messages)
