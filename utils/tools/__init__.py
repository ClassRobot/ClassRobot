import re
import base64
from io import BytesIO
from pathlib import Path
from string import punctuation
from typing import Any, overload

from qrcode import QRCode
from filetype import guess_extension
from qrcode.image.pil import PilImage
from qrcode.image.pure import PyPNGImage
from nonebot_plugin_htmlrender import get_new_page
from nonebot_plugin_htmlrender.data_source import env, markdown, read_tpl


class StringCard:
    """按统一格式拼装文本卡片内容。"""
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
        """初始化实例。

        参数:
            title (str | None): title。
            hr_len (int): hrlen。
        """
        self.hr_len: int = hr_len
        self.title = title
        self.card: list[str] = []
        if self.title:
            self.card.append(self.title)

    @property
    def foot_corner(self) -> str:
        """添加页脚角标。"""
        return self.lb + self.h * self.hr_len

    def text(self, *text: str, sep: str = " ", inplace: bool = True):
        """处理文本相关逻辑。

        参数:
            sep (str): sep。
            inplace (bool): inplace。
            text (*str): 文本内容。
        """
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
        """处理hr相关逻辑。

        参数:
            text (str | None): 文本内容。
        """
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
        """渲染当前文本卡片内容。"""
        return "\n".join(self.card + [self.foot_corner])

    def __str__(self) -> str:
        """返回字符串表示。"""
        return self.render()

    def __repr__(self) -> str:
        """返回调试字符串表示。"""
        return self.render()

    def __bool__(self) -> bool:
        """返回布尔值。"""
        return bool(self.card)


@overload
async def download_file(
    uri: bytes,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    to_path: str | Path,
) -> bytes:
    """下载文件"""


@overload
async def download_file(
    uri: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    to_path: str | Path | None = None,
) -> bytes:
    """下载文件"""


async def download_file(
    uri: str | bytes,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    to_path: str | Path | None = None,
) -> bytes:
    """下载文件"""
    if not isinstance(uri, str):
        assert to_path, "to_path is required when uri is bytes"
        Path(to_path).write_bytes(uri)
        return uri
    async with get_new_page() as page:
        response = await page.request.get(uri, headers=headers, params=params)
        body = await response.body()
        if to_path:
            Path(to_path).write_bytes(body)
        return body


def get_file_suffix(file: bytes) -> str | None:
    """获取文件类型"""
    if kind := guess_extension(file):
        return str(kind).replace(".", "")


def get_url_suffix(url: str) -> str | None:
    """获取链接对应的文件后缀。"""
    url_split = url.split(".")
    if len(url_split) > 2 and re.match("^[a-zA-Z]+$", url_split[-1]):
        return url_split[-1]


async def md_to_html(md: str) -> str:
    """将 Markdown 转换为 HTML。"""
    template = env.get_template("markdown.html")
    md = markdown.markdown(
        md,
        extensions=[
            "pymdownx.tasklist",
            "tables",
            "fenced_code",
            "codehilite",
            "mdx_math",
            "pymdownx.tilde",
        ],
        extension_configs={"mdx_math": {"enable_dollar_delimiter": True}},
    )

    extra = ""
    if "math/tex" in md:
        katex_css = await read_tpl("katex/katex.min.b64_fonts.css")
        katex_js = await read_tpl("katex/katex.min.js")
        mhchem_js = await read_tpl("katex/mhchem.min.js")
        mathtex_js = await read_tpl("katex/mathtex-script-type.min.js")
        extra = (
            f'<style type="text/css">{katex_css}</style>'
            f"<script defer>{katex_js}</script>"
            f"<script defer>{mhchem_js}</script>"
            f"<script defer>{mathtex_js}</script>"
        )

    css = await read_tpl("github-markdown-light.css") + await read_tpl(
        "pygments-default.css",
    )

    html = await template.render_async(md=md, css=css, extra=extra)
    return html


def text_to_qrcode(text: str) -> bytes:
    """文字转二维码

    参数:
        text (str): 文字内容或url

    返回:
        bytes: 二维码图片
    """
    image_bytes = BytesIO()
    code_img = QRCode()
    code_img.add_data(text)
    code_img.make(fit=True)
    image: PilImage | PyPNGImage = code_img.make_image()
    image.save(image_bytes)
    return image_bytes.getvalue()


def bytes_to_base64(data: bytes) -> str:
    """bytes转base64

    参数:
        data (bytes): bytes数据

    返回:
        str: base64数据
    """
    return base64.b64encode(data).decode()


def check_punctuation(text: str, ignore: list[str] | None = None) -> bool:
    """检查文本中是否包含标点符号

    参数:
        text (str): 文本

    返回:
        bool: 是否包含标点符号
    """
    if ignore:
        return any(i in text for i in punctuation if i not in ignore)
    return any(i in text for i in punctuation)


if __name__ == "__main__":
    card = StringCard("用户信息")
    card.hr()
    card.text("UID: 1")
    print(card.text("昵称: 小明", inplace=False))
    card.text("账号: xiaoming")
    print(card)
