from strenum import StrEnum
from pydantic import BaseModel


class Role(StrEnum):
    user = "user"
    system = "system"
    assistant = "assistant"


class Context(BaseModel):
    role: Role
    content: str


class Messages(BaseModel):
    messages: list[Context]

    @property
    def max_length(self) -> int:
        return 20480

    def char_length(self) -> int:
        return sum(len(message.content) for message in self.messages)

    def delete_message(self, index: int):
        """删除消息

        如果当前删除的消息是user，那么需要检查下一条消息是否是assistant，如果是，则删除
        如果当前删除的消息是assistant，那么需要检查上一条消息是否是user，如果是，则删除
        当是system消息时，不能删除

        Args:
            index (int): 消息索引
        """
        if self.messages[index].role == Role.system:
            raise ValueError("不能删除系统消息")
        elif self.messages[index].role == Role.user:
            if (
                index + 1 < len(self.messages)
                and self.messages[index + 1].role == Role.assistant
            ):
                self.messages.pop(index + 1)
        else:
            if index - 1 >= 0 and self.messages[index - 1].role == Role.user:
                self.messages.pop(index - 1)
        self.messages.pop(index)

    def add_message(self, role: Role, content: str):
        char_length = self.char_length()
        if char_length > self.max_length:
            # 超出限制，删除一半的消息
            cl = char_length // 2
            for i, message in enumerate(self.messages):
                if (cl := cl - len(message.content)) <= 0:
                    self.messages = self.messages[i:]
                    break
        self.messages.append(Context(role=role, content=content))

    def user_message(self, content: str):
        self.add_message(role=Role.user, content=content)

    def system_message(self, content: str):
        self.add_message(role=Role.system, content=content)

    def assistant_message(self, content: str):
        self.add_message(role=Role.assistant, content=content)
        print(self.char_length())
