from datetime import datetime

from pandas import DataFrame
from utils.models import User, Classes
from nonebot_plugin_alconna import UniMessage
from utils.llm import Messages, client_create
from src.plugins.find_at.util import students_to_df
from utils.llm.typings import ChatCompletionToolParam
from utils.llm.util import json_loads, uni_message_to_contents

from .prompt import prompt
from .schema import Notices


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


class NoticeSession:
    functions: list[ChatCompletionToolParam] = [
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
            prompt + f"当前时间: {datetime.now()}\n当前用户ID: {user.id}"
        )
        self.messages.assistant_message("{reply: '好的，我会严格按照您的邀请去编写通知任务,并以json格式返回给您'}")

    async def call(self, message: UniMessage) -> Notices | None:
        self.messages.user_message(uni_message_to_contents(message))
        response = await client_create(self.messages, tools=self.functions)
        content = response.choices[0].message.content
        if response.choices[0].message.tool_calls:
            self.messages
            for tool in response.choices[0].message.tool_calls:
                match (tool.function.name):
                    case "get_self_id":
                        self.messages.tool_message(tool.id, await self.get_self_id())
                    case "get_classmates":
                        self.messages.tool_message(tool.id, await self.get_classmates())
                    case "get_classes":
                        self.messages.tool_message(tool.id, await self.get_classes())
            response = await client_create(self.messages)
            content = response.choices[0].message.content

        if content:
            print(content)
            return Notices.parse_obj(json_loads(content))

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
