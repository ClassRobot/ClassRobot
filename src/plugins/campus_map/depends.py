import json
from typing import Annotated

from nonebot import logger
from utils.models import User
from nonebot.params import Depends
from utils.skills import qr_code_skill
from utils.llm.util import json_loads
from utils.tools.sync import run_sync
from utils.llm import Messages, client_create
from utils.template import Prompt, template_to_pic
from utils.models.depends import UserOrCreatedDepends
from utils.tools import bytes_to_base64

from .config import map_list_path


class CampusMap:
    """封装校园地图查询所需的上下文与目标信息。"""

    def __init__(self, user: User) -> None:
        """初始化实例。

        参数:
            user (User): 当前用户对象。
        """
        self.user = user
        self.messages = Messages()
        self.location: dict = json.loads(map_list_path[0].read_text("utf-8"))
        self.location_keys = list(self.location.keys())

    async def parse_location(self, message: str) -> dict[str, str]:
        """解析location。

        参数:
            message (str): 消息对象。

        返回:
            dict[str, str]: 返回处理结果。
        """
        self.messages.user_message(message)
        try:
            response = await client_create(messages=self.messages)
            if content := response.choices[0].message.content:
                data = json_loads(content)
                location = data.get("location", [])
                if not isinstance(location, list):
                    return {}
                return {
                    self.location_keys[index]: self.location[self.location_keys[index]]
                    for index in location
                    if isinstance(index, int) and 0 <= index < len(self.location_keys)
                }
        except Exception as error:
            logger.exception(error)
        return {}

    async def to_pic(self, location: dict[str, str]) -> bytes:
        """将地点结果渲染为带二维码的图片。

        参数:
            location (dict[str, str]): 地点名称到地图链接的映射。

        返回:
            bytes: 渲染后的图片字节数据。
        """
        address = [
            {"name": i, "image": bytes_to_base64(await run_sync(qr_code_skill.encode)(v))} for i, v in location.items()
        ]
        return await template_to_pic("campus_map.html", {"address": address})

    @staticmethod
    async def depends(user: UserOrCreatedDepends) -> "CampusMap":
        """处理依赖相关逻辑。

        参数:
            user (UserOrCreatedDepends): 当前用户对象。

        返回:
            'CampusMap': 返回处理结果。
        """
        campus_map = CampusMap(user)
        content = campus_map.messages.system_message(
            await Prompt("campus_map").render({"address": campus_map.location_keys})
        )
        print(content.content)
        return campus_map


CampusMapDepends = Annotated[CampusMap, Depends(CampusMap.depends)]
