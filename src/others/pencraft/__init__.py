from utils import Emoji
from nonebot import logger
from pypandoc import convert_text
from src.agents.skills import markdown_to_image_skill, qr_code_skill
from utils.tools.cos import upload_file
from utils.llm import Messages, client_create
from utils.llm.util import uni_message_to_contents
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

    try:
        html = await markdown_to_image_skill.to_html(content)
        document_bytes = convert_text(
            source=html,
            to="docx",
            format="html",
            outputfile="-",  # 输出到标准输出
            extra_args=["--standalone"],  # 根据需要添加额外参数
        )
        if isinstance(document_bytes, str):
            document_bytes = document_bytes.encode("utf-8")
        download_qrcode = qr_code_skill.encode(await upload_file(document_bytes, suffix=".docx"))
        html += footer(download_qrcode)
        await matcher.finish(
            UniMessage.text(Emoji.success + "生成成功！图片预览，图片右下角扫码免费下载！")
            + UniMessage.image(
                raw=await markdown_to_image_skill.html_to_image(html, viewport={"width": 1080, "height": 10})
            )
        )
    except Exception as error:
        logger.exception(error)
        await matcher.finish(Emoji.error + "文档生成失败，请稍后重试。")
