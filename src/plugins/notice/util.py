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
from .schema import Notice, Notices


def classes_to_df(classes: list[Classes]) -> DataFrame:
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

    Args:
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
            f"[有您的通知消息]\n[发送人用户ID: {creator.id} | {creator.nickname}]\n"
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
    functools: list[ChatCompletionToolParam] = [
        {
            "type": "function",
            "function": {
                "name": "get_self_id",
                "description": "调用该方法可以获取当前用户的信息.",
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_classmates",
                "description": "调用该方法可以获取该用户相关的其它同学信息,机器人可以在得到同学信息后获取指定的同学`user_id`.",
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_classes",
                "description": "调用该方法可获取该用户的所有班级信息,机器人可以在得到班级信息后获取指定的班级`group_id`.",
            },
        },
    ]

    def __init__(self, user: User):
        self.user = user
        self.messages = Messages()
        self.messages.system_message(
            prompt + f"\n当前时间: {datetime.now()}\n当前用户ID: {user.id}"
        )

    async def call(self, message: UniMessage) -> Notices | None:
        try:
            self.messages.user_message(uni_message_to_contents(message))
            response = await client_create(self.messages, tools=self.functools)
            content = response.choices[0].message.content
            if response.choices[0].message.tool_calls:
                self.messages.add_tool(response.choices[0].message)
                for tool in response.choices[0].message.tool_calls:
                    match (tool.function.name):
                        case "get_self_id":
                            self.messages.tool_message(
                                tool.id, await self.get_self_id()
                            )
                        case "get_classmates":
                            self.messages.tool_message(
                                tool.id, await self.get_classmates()
                            )
                        case "get_classes":
                            self.messages.tool_message(
                                tool.id, await self.get_classes()
                            )
                response = await client_create(self.messages)
                content = response.choices[0].message.content

            if content:
                print(content)
                notices = Notices.parse_obj(json_loads(content))
                self.messages.assistant_message(notices.json(ensure_ascii=False))
                return notices
        except Exception as e:
            logger.exception(e)
            return None

    async def get_self_id(self) -> str:
        return f"user_id: {self.user.id}"

    async def get_classmates(self):
        students = []
        if self.user.student:
            students += await self.user.student.get_classmates()
        if self.user.teacher:
            students += await self.user.teacher.get_students()
        return students_to_df(students).drop_duplicates().to_markdown()

    async def get_classes(self):
        classes = []
        if self.user.student:
            classes.append(self.user.student.classes)
        if self.user.teacher:
            classes += self.user.teacher.classes
        return classes_to_df(classes).drop_duplicates().to_markdown()
