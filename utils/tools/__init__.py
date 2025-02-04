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
        self.head_corner: str = self.lt + self.h * self.hr_len
        self.foot_corner: str = self.lb + self.h * self.hr_len
        self.card = []
        if title:
            self.card.append(title)

    def text(self, *text: str, sep: str = " "):
        self.card.append(f"{self.v} {sep.join(text)}")
        return self

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
