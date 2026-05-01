from datetime import datetime

from nonebot import logger
from pandas import DataFrame
from utils.models import User, Classes
from nonebot_plugin_alconna import UniMessage
from utils.llm import Messages, client_create
from src.plugins.find_at.util import students_to_df
from utils.llm.typings import ChatCompletionToolParam
from utils.send import push_user_message, push_group_message
from utils.llm.util import json_loads, contents_to_uni_message, uni_message_to_contents

from .prompt import prompt
from .schema import Notice, Notices, NoticeGroup, NoticePrivate


def classes_to_df(classes: list[Classes]) -> DataFrame:
    """将班级对象列表转换为 DataFrame。"""
    data = []
    for cls in classes:
        info = {
            "classes_id": cls.id,
            "classes_name": cls.name,
            "group_id": cls.group_id,
        }
        for bind in cls.group.group_binds:
            info[bind.platform_id] = bind.channel_id
        data.append(info)
    return DataFrame(data)


async def notice_work(notice: Notice, creator: User | None = None):
    """发送通知

    在通知发送结束后删除通知

    参数:
        notice (Notice): 通知内容
        creator (User | None, optional): 创建者. Defaults to None.
    """
    try:
        if creator is None:
            creator = await notice.get_creator()

        if creator is None:
            logger.error("遭遇错误，无法获取通知创建者")
            return

        message = UniMessage(
            f"**有您的通知消息**\n\n**发送人用户ID: {creator.id} | {creator.nickname}**\n\n"
        ) + contents_to_uni_message(notice.messages)

        users = await notice.get_notice_users()
        groups = await notice.get_notice_groups()

        for user in users:
            await push_user_message(user, message)

        for group in groups:
            await push_group_message(group, message)
    finally:
        await notice.remove_job()


class NoticeSession:
    """封装通知会话状态与行为。"""

    functools: list[ChatCompletionToolParam] = [
        {
            "type": "function",
            "function": {
                "name": "get_self_id",
                "description": "调用该方法可以获取当前用户的信息.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_classmates",
                "description": "调用该方法可以获取该用户相关的其它同学信息,机器人可以在得到同学信息后获取指定的同学`user_id`.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_classes",
                "description": "调用该方法可获取该用户的所有班级信息,机器人可以在得到班级信息后获取指定的班级`group_id`.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
    ]

    def __init__(self, user: User):
        """初始化实例。

        参数:
            user (User): 当前用户对象。
        """
        self.user = user
        self.messages = Messages()
        self.messages.system_message(prompt + f"\n当前时间: {datetime.now()}\n当前用户ID: {user.id}")
        self.user_ids = [self.user.id]
        self.group_ids = []
        self.student_df: DataFrame | None = None
        self.classes_df: DataFrame | None = None

    async def call(self, message: UniMessage) -> Notices | None:
        """处理调用相关逻辑。

        参数:
            message (UniMessage): 消息对象。

        返回:
            Notices | None: 返回处理结果。
        """
        try:
            self.messages.user_message(uni_message_to_contents(message))
            content = await self.run_notice_agent()

            if content:
                print(content)
                notices = Notices.parse_obj(json_loads(content))
                self.filter_notices(notices)
                self.messages.assistant_message(notices.json(ensure_ascii=False))
                return notices
        except Exception as e:
            logger.exception(e)
            return None

    async def run_notice_agent(self, max_steps: int = 4) -> str | None:
        """运行通知解析模型，并按需处理多轮工具调用。"""

        for _ in range(max_steps):
            response = await client_create(self.messages, functools=self.functools, tool_choice="auto")
            assistant_message = response.choices[0].message
            if not assistant_message.tool_calls:
                return assistant_message.content

            self.messages.add_tool(assistant_message)
            for tool_call in assistant_message.tool_calls:
                self.messages.tool_message(tool_call.id, await self.call_tool(tool_call.function.name))
        logger.warning("notice llm tool calls reached max steps")
        return None

    async def call_tool(self, name: str) -> str:
        """执行通知解析阶段允许的本地工具。"""

        match name:
            case "get_self_id":
                return await self.get_self_id()
            case "get_classmates":
                return await self.get_classmates()
            case "get_classes":
                return await self.get_classes()
            case _:
                logger.warning(f"unknown notice tool: {name}")
                return f"未知工具: {name}"

    def filter_notices(self, notices: Notices) -> Notices:
        """过滤掉于用户本身无关联的用户

        参数:
            notices (Notices): 通知。

        返回:
            Notices: 返回处理结果。
        """
        for notice in notices.notices.copy():
            for obj in notice.recipients.copy():
                if isinstance(obj, NoticeGroup):
                    if obj.group_id not in self.group_ids:
                        notice.recipients.remove(obj)
                elif isinstance(obj, NoticePrivate):
                    if obj.user_id not in self.user_ids:
                        notice.recipients.remove(obj)
            if not notice.recipients:
                notices.remove(notice)
        return notices

    async def get_self_id(self) -> str:
        """获取selfid。"""
        return f"user_id: {self.user.id}"

    async def get_classmates(self):
        """获取同班同学列表。"""
        students = []
        if self.user.student:
            students += await self.user.student.get_classmates()
        if self.user.teacher:
            students += await self.user.teacher.get_students()
        self.students_df = students_to_df(students).drop_duplicates()
        self.user_ids = self.students_df["user_id"].tolist() + [self.user.id]
        return self.students_df.to_json(orient="records", force_ascii=False)

    async def get_classes(self):
        """获取班级。"""
        if self.classes_df is not None:
            return self.classes_df.to_json(orient="records", force_ascii=False)
        classes = []
        if self.user.student:
            classes.append(self.user.student.classes)
        if self.user.teacher:
            classes += self.user.teacher.classes
        self.classes_df = classes_to_df(classes).drop_duplicates()
        self.group_ids = self.classes_df["group_id"].tolist()
        return self.classes_df.to_json(orient="records", force_ascii=False)
