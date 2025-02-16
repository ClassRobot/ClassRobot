from nonebot import logger
from utils.models.models import User, Group
from nonebot_plugin_alconna import Target, UniMessage, SupportAdapter, get_bot


class StringCard:
    left_top = "┌"
    right_top = "┐"
    left_bottom = "└"
    right_bottom = "┘"
    horizontal = "─"
    vertical = "│"
    left_vertical = "├"

    lt = left_top
    rt = right_top
    lb = left_bottom
    rb = right_bottom
    h = horizontal
    v = vertical
    lv = left_vertical

    hr_len: int = 10

    def __init__(self, title: str | None = None, hr_len: int = 10) -> None:
        self.hr_len: int = hr_len
        self.title = title
        self.card: list[str] = []
        if self.title:
            self.card.append(self.title)

    @property
    def foot_corner(self) -> str:
        return self.lb + self.h * self.hr_len

    def text(self, *text: str, sep: str = " ", inplace: bool = True):
        value = f"{self.v} {sep.join(str(i) for i in text)}"
        if inplace:
            self.card.append(value)
            return self
        else:
            card = StringCard(self.title, self.hr_len)
            card.card = self.card.copy()
            card.card.append(value)
            return card

    def hr(self, text: str | None = None):
        if text and len(text) > self.hr_len:
            raise ValueError("text is too long")
        # 让文本居中
        if text:
            text = text.center(self.hr_len, self.h)
        else:
            text = self.h * self.hr_len
        self.card.append(f"{self.lv if len(self.card) > 0 else self.lt}{text}")
        return self

    def render(self):
        return "\n".join(self.card + [self.foot_corner])

    def __str__(self) -> str:
        return self.render()

    def __repr__(self) -> str:
        return self.render()

    def __bool__(self) -> bool:
        return bool(self.card)


# 推送给用户消息
async def push_user_message(user: User, message: UniMessage):
    """推送给用户所绑定的所有平台发送消息"""
    for bind in user.binds:
        adapter_name = SupportAdapter[bind.platform_id.split(".")[0]]
        for bot in await get_bot(adapter=adapter_name):
            try:
                await Target(bind.account_id, private=True).send(message, bot)
            except Exception as e:
                logger.exception(e)


async def push_group_message(group: Group, message: UniMessage):
    """推送给群所绑定的所有平台发送消息"""
    for bind in group.group_binds:
        adapter_name = SupportAdapter[bind.platform_id.split(".")[0]]
        for bot in await get_bot(adapter=adapter_name):
            try:
                await Target(
                    id=bind.channel_id,
                    channel=bool(bind.guild_id),
                    parent_id=bind.guild_id,
                ).send(message, bot)
            except Exception as e:
                logger.exception(e)


if __name__ == "__main__":
    card = StringCard("用户信息")
    card.hr()
    card.text("UID: 1")
    print(card.text("昵称: 小明", inplace=False))
    card.text("账号: xiaoming")
    print(card)
