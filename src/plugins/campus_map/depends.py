import json
from typing import Annotated

from utils.models import User
from nonebot.params import Depends
from utils.llm.util import json_loads
from utils.tools.sync import run_sync
from utils.llm import Messages, client_create
from utils.models.depends import UserOrCreatedDepends
from utils.template import get_prompts, template_to_pic
from utils.tools import text_to_qrcode, bytes_to_base64

from .config import map_list_path


class CampusMap:
    def __init__(self, user: User) -> None:
        self.user = user
        self.messages = Messages()
        self.location: dict = json.loads(map_list_path[0].read_text("utf-8"))
        self.location_keys = list(self.location.keys())

    async def parse_location(self, message: str) -> dict[str, str]:
        self.messages.user_message(message)
        response = await client_create(messages=self.messages)
        if content := response.choices[0].message.content:
            location = json_loads(content)["location"]
            return {self.location_keys[i]: self.location[self.location_keys[i]] for i in location}
        return {}

    async def to_pic(self, location: dict[str, str]) -> bytes:
        address = [
            {"name": i, "image": bytes_to_base64(await run_sync(text_to_qrcode)(v))} for i, v in location.items()
        ]
        return await template_to_pic("campus_map.html", {"address": address})

    @staticmethod
    async def depends(user: UserOrCreatedDepends) -> "CampusMap":
        campus_map = CampusMap(user)
        content = campus_map.messages.system_message(
            await get_prompts("campus_map.jinja", {"address": campus_map.location_keys})
        )
        print(content.content)
        return campus_map


CampusMapDepends = Annotated[CampusMap, Depends(CampusMap.depends)]
