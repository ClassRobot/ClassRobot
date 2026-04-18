from utils import Emoji
from nonebot import logger
from pypandoc import convert_text
from utils.tools.cos import upload_file
from utils.llm import Messages, client_create
from nonebot_plugin_htmlrender import html_to_pic
from utils.llm.util import uni_message_to_contents
from utils.tools import md_to_html, text_to_qrcode
from nonebot_plugin_alconna import Image, UniMessage, AlconnaMatcher

from .util import footer
from .prompt import plugin_prompt
from .commands import text_gen_cmd


@text_gen_cmd.handle()
async def _(matcher: AlconnaMatcher, values: list[str | Image]):
    """处理当前命令或事件逻辑。"""
    await matcher.send(Emoji.loading + "正在生成文档，请稍等...")
    messages = Messages()
    messages.system_message(plugin_prompt)
    contents = uni_message_to_contents(values)
    messages.user_message(contents)
    try:
        chat = await client_create(messages, max_tokens=8192)
    except Exception as e:
        logger.exception(e)
        await matcher.finish(Emoji.error + "生成失败!")

    if not (content := chat.choices[0].message.content):
        await matcher.finish(Emoji.error + "生成失败!")

    html = await md_to_html(content)
    document_bytes = convert_text(
        source=html,
        to="docx",
        format="html",
        outputfile="-",  # 输出到标准输出
        extra_args=["--standalone"],  # 根据需要添加额外参数
    )
    if isinstance(document_bytes, str):
        document_bytes = document_bytes.encode("utf-8")
    download_qrcode: bytes = text_to_qrcode(await upload_file(document_bytes, suffix=".docx"))
    html += footer(download_qrcode)
    await matcher.finish(
        UniMessage.text(Emoji.success + "生成成功！图片预览，图片右下角扫码免费下载！")
        + UniMessage.image(raw=await html_to_pic(html, viewport={"width": 1080, "height": 10}))
    )
