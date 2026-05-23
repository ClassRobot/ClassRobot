from hashlib import md5
from datetime import datetime
from typing import List, Iterable

from nonebot import logger
from src.platform.config import leave_dir
from src.core.auth import StudentRole
from src.core.llm.message import Content
from src.core.llm.util import json_loads
from src.core.llm import Messages, client_create
from nonebot_plugin_alconna import Image, UniMessage
from src.platform.files import download_file
from src.shared.tools import get_url_suffix
from src.models import User, Files, Classes, Student, StudentLeave

from .schema import Leave
from .prompt import plugin_prompt


class BaseLeave:
    """定义请假流程共享的基础能力。"""

    def __init__(self, user: User) -> None:
        """初始化实例。

        参数:
            user (User): 当前用户对象。
        """
        self.user = user


class AddLeave:
    """负责发起请假申请的业务处理。"""

    def __init__(self, student: Student) -> None:
        """初始化实例。

        参数:
            student (Student): 当前学生对象。
        """
        self.student = student
        self.messages = Messages()
        self.messages.system_message(plugin_prompt + self.current_state)
        self.image_url: str | None = None
        self.content = []

    def get_message_image(self, messages: Iterable):
        """获取用户发送的消息中的图片

        参数:
            messages (Iterable): 消息列表。
        """
        for msg in messages:
            if isinstance(msg, Image) and msg.url:
                self.image_url = msg.url
                break

    @property
    def current_state(self):
        """返回当前请假流程所处的状态。"""
        return f"\n当前时间: {datetime.now()}"

    def add_message(self, messages: list[str | Image]):
        """添加一条消息。

        参数:
            messages (list[str | Image]): 消息列表。
        """
        self.get_message_image(messages)
        self.content.extend(
            (
                Content(type="image", value=msg.url)  # type: ignore
                if isinstance(msg, Image)
                else Content(type="text", value=str(msg))
            )
            for msg in messages
        )

    async def send_message(self) -> Leave | None:
        """发送消息。"""
        self.messages.user_message(content=self.content)
        try:
            chat = await client_create(messages=self.messages)
            if chat.choices[0].message.content:
                print(chat.choices[0].message.content)
                data = Leave.parse_obj(obj=json_loads(chat.choices[0].message.content))
                return data
        except Exception as error:
            logger.exception(error)
            return None

    async def save_student_leave(self, leave: Leave):
        """保存学生请假条

        参数:
            leave (Leave): 请假。
        """
        if not self.image_url:
            raise ValueError("未接收到用户发送的图片")
        suffix: str | None = None

        # 先尝试用url中获取后缀
        suffix = get_url_suffix(self.image_url)
        data = await download_file(self.image_url)
        file_md5 = md5(data).hexdigest()

        # 如果不能获取到文件则保存一下
        if (files := await Files.get_file(file_md5)) is None:
            files = await Files.parse_data(data, leave_dir, suffix=suffix, file_md5=file_md5)

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
        """将请假内容通知给班干部

        参数:
            leave (StudentLeave): 请假。
        """
        # if (leave_config := await LeaveConfig.filter(classes_id=self.student.classes_id).first()) is None:
        #     return None
        # notify_role: list[str] = json.loads(leave_config.notify_role)

        # students = await Student.filter(classes_id=self.student.classes_id, role__in=notify_role).all()
        # if students:
        #     logger.info("通知班干部")
        #     messages = UniMessage.text(f"学生`{self.student.name}`提交了请假申请:\n" f"申请理由: {leave.reason}")
        #     messages += UniMessage.image(path=leave_dir / leave.file.name)
        #     await wait([push_user_message(student.user, messages) for student in students])

    # 创建审批流程
    async def create_approval(self, leave: StudentLeave):
        """创建审批流程

        参数:
            leave (StudentLeave): 请假。
        """
        # if (leave_config := await LeaveConfig.filter(classes_id=self.student.classes_id).first()) is None:
        #     return None
        # notify_role: list[str] = json.loads(leave_config.notify_role)
        # students = await Student.filter(classes_id=self.student.classes_id, role__in=notify_role).all()
        # if students:
        #     logger.info("通知班干部")
        #     messages = UniMessage.text(f"学生`{self.student.name}`提交了请假申请:\n" f"申请理由: {leave.reason}")
        #     messages += UniMessage.image(path=leave_dir / leave.file.name)
        #     await wait([push_user_message(student.user, messages) for student in students])


class QueryLeave(BaseLeave):
    """负责查询请假记录与审批状态的业务处理。"""

    async def get_student_leave(self) -> List[StudentLeave] | None:
        """获取学生的全部请假条"""
        if self.user.student:
            return await self.user.student.get_leaves()

    async def get_classes_leave(self, classes: Classes | None = None) -> List[StudentLeave] | None:
        """获取以班级未单位的全部请假条

        参数:
            classes (Classes | None, optional): 班级表. Defaults to None.

        返回:
            List[StudentLeave] | None: 请假条列表
        """
        if classes is None:
            if self.user.student:
                return await self.user.student.classes.get_leaves()
        else:
            return await classes.get_leaves()

    async def get_teacher_classes_leave(self) -> List[StudentLeave] | None:
        """获取教师所管理的全部请假条"""
        if self.user.teacher:
            leaves = []
            for classes in self.user.teacher.classes:
                leaves.extend(await classes.get_leaves())
            return leaves

    @property
    def is_student(self) -> bool:
        """判断是否为学生"""
        return self.user.student is not None

    @property
    def is_classes_admin(self) -> bool:
        """判断是否为班干部"""
        return self.user.student is not None and self.user.student.role in StudentRole._member_names_

    @property
    def is_teacher(self) -> bool:
        """判断是否为教师"""
        return self.user.teacher is not None

    def leave_to_messages(self, leave_list: list[StudentLeave]) -> list[UniMessage]:
        """处理请假消息相关逻辑。

        参数:
            leave_list (list[StudentLeave]): 请假列表。

        返回:
            list[UniMessage]: 返回处理结果。
        """
        today = datetime.now().timestamp()
        # 已结束的请假申请
        end_leave = [leave for leave in leave_list if leave.end_date.timestamp() < today]
        # 未结束的请假申请
        not_end_leave = [leave for leave in leave_list if leave.end_date.timestamp() >= today]

        messages = []
        if not_end_leave:
            messages.append(UniMessage.text("请假申请:"))
            for leave in not_end_leave:
                messages[-1] += self.to_message(leave)
        if end_leave:
            messages.append(UniMessage.text("已结束的请假申请:"))
            for leave in end_leave:
                messages[-1] += self.to_message(leave)
        return messages

    @staticmethod
    def to_message(leave: StudentLeave):
        """处理消息相关逻辑。

        参数:
            leave (StudentLeave): 请假。
        """
        return UniMessage.text(
            f"\n申请ID: {leave.id}\n"
            f"申请学生: [UID:{leave.student.user.id}] {leave.student.name}\n"
            f"所属班级: {leave.classes.name}\n"
            f"请假时间:\n\t开始: {leave.start_date}\n\t结束: {leave.end_date}\n"
            f"请假理由: {leave.reason}"
        ) + UniMessage.image(path=leave.file.path)
