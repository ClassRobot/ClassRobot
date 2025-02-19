import json
from hashlib import md5
from asyncio import wait
from datetime import datetime
from typing import List, Iterable

from utils.config import leave_dir
from utils.llm.schema import Content
from utils.llm.util import json_loads
from utils.models.models import Classes
from utils.llm import Messages, client_create
from utils.models.tool import push_user_message
from nonebot_plugin_alconna import Image, UniMessage
from utils.tools import download_file, get_url_suffix
from utils.models import User, Files, Student, StudentLeave, ClassesLeaveConfig

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

    def add_message(self, messages: list[str | Image]):
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

    async def send_message(self) -> Leave | None:
        chat = await client_create(messages=self.messages)
        if chat.choices[0].message.content:
            print(chat.choices[0].message.content)
            data = Leave.parse_obj(obj=json_loads(chat.choices[0].message.content))
            return data

    async def save_student_leave(self, leave: Leave):
        if not self.image_url:
            raise ValueError("未接收到用户发送的图片")
        suffix: str | None = None

        # 先尝试用url中获取后缀
        suffix = get_url_suffix(self.image_url)
        data = await download_file(self.image_url)
        file_md5 = md5(data).hexdigest()

        # 检查文件是否重复
        if await Files.file_duplicate(file_md5):
            return

        files = await Files.parse_data(data, leave_dir, suffix)

        student_leave = await StudentLeave(
            start_time=leave.start_time,
            end_time=leave.end_time,
            reason=leave.reason,
            classes=self.student.classes,
            student=self.student,
            file=files,
        ).create()
        return student_leave

    async def notice_leave(self, leave: StudentLeave):
        """将请假内容通知给班干部"""
        if (
            leave_config := await ClassesLeaveConfig.filter(
                classes_id=self.student.classes_id
            ).first()
        ) is None:
            return None
        notify_role: list[str] = json.loads(leave_config.notify_role)

        students = await Student.filter(
            classes_id=self.student.classes_id, role__in=notify_role
        ).all()
        messages = UniMessage.text(
            f"学生`{self.student.name}`提交了请假申请:\n" f"申请理由: {leave.reason}"
        )
        messages += UniMessage.image(path=leave_dir / leave.file.name)
        await wait([push_user_message(student.user, messages) for student in students])


class QueryLeave(BaseLeave):
    async def get_student_leave(self) -> List[StudentLeave] | None:
        if self.user.student:
            return await self.user.student.get_leaves()

    async def get_classes_leave(
        self, classes: Classes | None = None
    ) -> List[StudentLeave] | None:
        if classes is None:
            if self.user.student:
                return await self.user.student.classes.get_leaves()
        else:
            return await classes.get_leaves()
