import re
from datetime import datetime
from typing import Iterable

from hashlib import md5
from utils.llm.schema import Content
from utils.llm.util import json_loads
from utils.llm import Messages, client_create
from utils.models import User, Student, StudentLeave, Files
from nonebot_plugin_alconna import Image, UniMessage
from utils.tools import download_file, get_file_suffix, get_url_suffix
from utils.config import data_dir, leave_dir
from .schemes import Leave
from .prompt import plugin_prompt


class BaseLeave:
    def __init__(self, user: User) -> None:
        self.user = user


class AddLeave:
    def __init__(self, student: Student) -> None:
        self.student = student
        self.messages = Messages()
        self.messages.system_message(plugin_prompt + self.current_state)
        self.image_url: str | None = None

    def get_message_image(self, messages: Iterable):
        """获取用户发送的消息中的图片"""
        for msg in messages:
            if isinstance(msg, Image) and msg.url:
                self.image_url = msg.url
                break

    @property
    def current_state(self):
        return f"\n当前时间: {datetime.now()}"

    async def send_message(self, messages: list[str | Image]) -> Leave | None:
        # 接收用户消息时检查是否有提交图片
        self.get_message_image(messages)
        self.messages.user_message(
            [
                (
                    Content(type="text", value=msg)
                    if isinstance(msg, str)
                    else Content(type="image", value=msg.url)  # type: ignore
                )
                for msg in messages
            ]
        )
        chat = await client_create(messages=self.messages)
        if chat.choices[0].message.content:
            print(chat.choices[0].message.content)
            data = Leave.parse_obj(obj=json_loads(chat.choices[0].message.content))
            return data

    async def save_student_leave(self, leave: Leave) -> None:
        if not self.image_url:
            raise ValueError("未接收到用户发送的图片")
        suffix: str | None = None

        # 先尝试用url中获取后缀
        suffix = get_url_suffix(self.image_url)
        data = await download_file(self.image_url)

        # 如何没有获取到后缀则从文件中解析
        if suffix is None:
            suffix = get_file_suffix(data)

        file_md5 = md5(data).hexdigest()
        await Files(
            name=file_md5,
            file_md5=file_md5,
            file_path=str(leave_dir.relative_to(data_dir)),
            suffix=suffix,
        ).create()
        
