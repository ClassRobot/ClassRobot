from datetime import datetime
from typing import Literal, TypeAlias

from strenum import StrEnum
from pydantic import Field, BaseModel
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam


class Role(StrEnum):
    user = "user"
    system = "system"
    assistant = "assistant"


class Content(BaseModel):
    type: Literal["text", "image"]
    value: str

    def __len__(self):
        return len(self.value.encode("utf-8"))


ContentType: TypeAlias = str | list[Content]


class Context(BaseModel):
    role: Role
    content: str | list[Content]
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
        return super().dict(include={"role", "content"})


class Messages(BaseModel):
    messages: list[Context]
    priority: list[int] = []

    def build_messages(
        self, is_multi_modal: bool = False
    ) -> list[ChatCompletionMessageParam]:
        messages = []
        msg_len = len(self.messages)
        for i, ctx in enumerate(self.messages):
            msg_dict = ctx.dict()
            msg_dict["content"] = ctx.single_modal()
            if i == msg_len - 1 and is_multi_modal:  # 最后一条消息
                msg_dict["content"] = ctx.multi_modal()
            messages.append(msg_dict)
        return messages

    def get(self, *role: Role) -> "Messages":
        return Messages(messages=[msg for msg in self.messages if msg.role in role])

    def text_only(self) -> bool:
        """是否只有文本消息"""
        return self.messages[-1].text_only()

    @property
    def max_length(self) -> int:
        return 12 * 1024

    def char_length(self) -> int:
        return sum(len(message) for message in self.messages)

    def remove(self, obj: int | Context):
        if isinstance(obj, int):
            index = obj
            context = self.messages.pop(obj)
        else:
            index = self.messages.index(obj)
            context = self.messages.pop(index)

        # 如果是用户的消息，说明下面一条或多条可能是机器人的消息，需要向下搜索知道下一条为用户消息，在这之间的消息都是机器人的消息需要删除
        pop_role = Role.user if context.role == Role.assistant else Role.assistant
        next_index = int(context.role == Role.assistant)
        while (
            len(self.messages) > (index := index - next_index)
            and self.messages[index].role == pop_role
        ):
            self.messages.pop(index)

    def add_message(self, role: Role, content: str | list, priority: int = 1):
        char_length = self.char_length()
        if char_length > self.max_length:
            self.delete_messages(0.5)

        # 按照优先级排序
        if priority in self.priority:
            """如果已经存在的优先级，则不添加"""
        elif not self.priority:
            self.priority.append(priority)
        elif priority < self.priority[-1]:
            self.priority.append(priority)
        elif priority > self.priority[0]:
            self.priority.insert(0, priority)

        self.messages.append(Context(role=role, content=content, priority=priority))

    def delete_messages(self, per: float = 0.5):
        """删除一定比例的消息"""
        char_length = self.char_length()
        remaining_length = char_length - int(char_length * per)
        # 需要删除到剩余数量
        while self.char_length() > remaining_length:
            # 按照priority排序，删除优先级低的消息
            if self.priority:
                priority = self.priority.pop()
            for ctx in self.get(Role.assistant).messages:
                if ctx.priority == priority:
                    self.remove(ctx)

    def user_message(self, content: ContentType, priority: int = 1):
        self.add_message(role=Role.user, content=content, priority=priority)

    def system_message(self, content: ContentType, priority: int = 1):
        self.add_message(role=Role.system, content=content, priority=priority)

    def assistant_message(self, content: ContentType, priority: int = 1):
        self.add_message(role=Role.assistant, content=content, priority=priority)
        print(self.char_length())

    def __repr__(self) -> str:
        return str(self.get(Role.user, Role.assistant).messages)
