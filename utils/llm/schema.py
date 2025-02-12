from datetime import datetime
from typing import Literal, TypeAlias

from nonebot import logger
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
        return len(self.value.encode("utf-8"))


ContentType: TypeAlias = str | list[Content]


class Context(BaseModel):
    role: Role
    content: str | list[Content]
    tool_call_id: str | None = None
    priority: int = 10
    created_at: datetime = Field(default_factory=datetime.now)

    def multi_modal(self) -> ContentType:
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
            elif msg.type == "image":
                # 采用md的img格式
                content.append(f"![image]({msg.value})")
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
    priority: dict[int, int] = {}

    def build_messages(
        self, is_multi_modal: bool = False
    ) -> list[ChatCompletionMessageParam]:
        messages = []
        msg_len = len(self.messages)
        for i, ctx in enumerate(self.messages):
            msg_dict = None
            if isinstance(ctx, Context):
                msg_dict = ctx.dict()
                msg_dict["content"] = ctx.single_modal()
                if i == msg_len - 1 and is_multi_modal:  # 最后一条消息
                    msg_dict["content"] = ctx.multi_modal()
            messages.append(msg_dict or ctx)
        return messages

    def get(self, *role: Role) -> "Messages":
        """通过角色获取消息"""
        return Messages(
            messages=[
                msg
                for msg in self.messages
                if isinstance(msg, Context) and msg.role in role
            ]
        )

    def text_only(self) -> bool:
        """是否只有文本消息"""
        if isinstance(self.messages[-1], Context):
            return self.messages[-1].text_only()
        return True

    @property
    def max_length(self) -> int:
        return 12 * 1024

    def char_length(self, *role: Role) -> int:
        return sum(
            len(message)
            for message in self.messages
            if isinstance(message, Context) and (not role or message.role in role)
        )

    def rollback(self):
        """回滚消息"""
        self.pop()

    def remove(self, obj: int | Context):
        if isinstance(obj, int):
            index = obj
            context = self.pop(obj)
        else:
            index = self.messages.index(obj)
            context = self.pop(index)

        # 如果是用户的消息，说明下面一条或多条可能是机器人的消息，需要向下搜索知道下一条为用户消息，在这之间的消息都是机器人的消息需要删除
        pop_role = Role.user if context.role == Role.assistant else Role.assistant
        next_index = int(context.role == Role.assistant)
        while (
            len(self.messages) > (index := index - next_index)
            and isinstance(self.messages[index], Context)
            and self.messages[index].role == pop_role  # type: ignore
        ):
            msg = self.pop(index)
            logger.info("超出长度，删除消息: %s", msg)

    def pop(self, index: int = -1) -> Context:
        context = self.pop(index)
        self.priority[context.priority] -= 1
        if self.priority[context.priority] <= 0:
            self.priority.pop(context.priority)
        return context

    def add_message(
        self,
        role: Role,
        content: str | list,
        tool_call_id: str | None = None,
        priority: int = 1,
    ):
        if self.char_length() > self.max_length:  # 超出长度
            self.delete_messages(0.5)

        self.priority.setdefault(priority, 0)
        self.priority[priority] += 1
        self.messages.append(
            Context(
                role=role, content=content, priority=priority, tool_call_id=tool_call_id
            )
        )
        print(self.char_length(), role, self)

    def add_tool(self, context: ChatCompletionMessage):
        self.messages.append(context)

    def delete_messages(self, per: float = 0.5):
        """删除一定比例的消息"""
        char_length = self.char_length()
        remaining_length = char_length - int(char_length * per)
        # 需要删除到剩余数量
        while char_length > remaining_length:
            # 按照priority排序，删除优先级低的消息
            if self.priority:
                priority = sorted(self.priority.keys())[0]
                for ctx in self.get(Role.assistant).messages:
                    if isinstance(ctx, Context) and ctx.priority == priority:
                        self.remove(ctx)
            _length = self.char_length()
            if _length == char_length:
                break

    def user_message(self, content: ContentType, priority: int = 1):
        self.add_message(role=Role.user, content=content, priority=priority)

    def system_message(self, content: ContentType, priority: int = 1000):
        self.add_message(role=Role.system, content=content, priority=priority)

    def assistant_message(self, content: ContentType, priority: int = 1):
        self.add_message(role=Role.assistant, content=content, priority=priority)

    def tool_message(self, tool_call_id: str, content: str, priority: int = 1):
        self.add_message(
            role=Role.tool,
            content=content,
            tool_call_id=tool_call_id,
            priority=priority,
        )

    def __repr__(self) -> str:
        return self.get(Role.user, Role.assistant, Role.tool).messages.__repr__()

    def __str__(self) -> str:
        return self.__repr__()
