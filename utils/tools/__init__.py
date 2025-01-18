corner = ["┌", "┐", "└", "┘", "─", "│", "├"]


class StringCard:
    def __init__(self, title: str | None = None, hr_len: int = 10) -> None:
        self.hr_len: int = hr_len
        self.head_corner: str = corner[0] + corner[4] * self.hr_len
        self.foot_corner: str = corner[2] + corner[4] * self.hr_len
        self.card = []
        if title:
            self.card.append(title)

    def text(self, text: str):
        self.card.append(f"{corner[5]} {text}")
        return self

    def hr(self, text: str | None = None):
        if text and len(text) > self.hr_len:
            raise ValueError("text is too long")
        # 让文本居中
        if text:
            text = text.center(self.hr_len, corner[4])
        else:
            text = corner[4] * self.hr_len
        self.card.append(f"{corner[6] if len(self.card) > 0 else corner[0]}{text}")
        return self

    def render(self):
        return "\n".join(self.card + [self.foot_corner])

    def __str__(self) -> str:
        return self.render()

    def __repr__(self) -> str:
        return self.render()
