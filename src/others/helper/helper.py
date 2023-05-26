from typing import Optional, Union, Dict, List, Generator
from nonebot.log import logger
from pydantic import BaseModel

from .config import BaseHelper, env

InsertHelper = Union[dict, "Helper", List[Union[dict, "Helper"]], "HelperTags"]


def string(val) -> bool:
    return isinstance(val, str)


class Helper(BaseModel, BaseHelper):
    """帮助信息

    Args:
        cmd (str): 命令
        use (str): 命令使用范例
            (List[str]): 按照聊天顺序,先用户后bot
            (List[List[str]]): 对话方式展示,主要为
            (List[List[List[str]]]): 长对话方式,第一个list为用户聊天内容,后为bot
        docs (str): 命令的简要说明
        tags (List[str]): 命令的类型
        alias (List[str]): 命令的别名
        params (List[str]): 命令参数
    """

    cmd: str
    use: Union[str, List[Union[str, List[Union[List[str], str]]]]] = ""
    doc: str = ""
    tags: List[str] = []
    alias: List[str] = []
    params: List[str] = []

    async def to_string(self) -> str:
        """使用helper模板

        Returns:
            str: 返回html内容
        """
        helper_template = env.get_template("helper.jinja")
        return await helper_template.render_async(
            is_chat=isinstance(self.use, list),
            string=string,
            helper=self,
        )

    @staticmethod
    def make_missing_data(data: dict) -> dict:
        data = data.copy()
        data.setdefault("params", [])
        if isinstance(data["tags"], str):
            data["tags"] = data["tags"].split()
        if isinstance(data["params"], str):
            data["params"] = data["params"].split()
        if not data.get("use"):
            data["use"] = " ".join((data["cmd"], *data["params"]))
        return data


class HelperTags(BaseHelper):
    def __init__(self, helpers: Optional[InsertHelper] = None):
        self.helpers: List[Helper] = []
        if helpers is not None:
            self.append(helpers)

    def append(self, helpers: InsertHelper):
        if isinstance(helpers, dict):
            self.helpers.append(Helper(**helpers))
        elif isinstance(helpers, Helper):
            self.helpers.append(helpers)
        elif isinstance(helpers, (list, HelperTags)):
            for helper in helpers:
                self.append(helper)

    def __repr__(self) -> str:
        return self.helpers.__repr__()

    def __iter__(self) -> Generator[Helper, None, None]:
        yield from self.helpers

    def __getitem__(self, index: Union[int, slice]) -> Union[Helper, "HelperTags"]:
        if isinstance(index, int):
            return self.helpers[index]
        return HelperTags(self.helpers[index])  # type: ignore

    async def to_string(self) -> str:
        tags_template = env.get_template("helper_tags.jinja")
        return await tags_template.render_async(helpers=self)


class HelperMenu(HelperTags):
    def __init__(self, helpers: Optional[InsertHelper] = None):
        self.cmd: Dict[str, Helper] = {}
        self.tags: Dict[str, HelperTags] = {}
        super().__init__(helpers)

    def append(self, helpers: InsertHelper):
        if isinstance(helpers, (dict, Helper)):
            helper = (
                Helper(**Helper.make_missing_data(helpers))
                if isinstance(helpers, dict)
                else helpers
            )
            self.helpers.append(helper)
            for key in (*helper.alias, helper.cmd):
                if key in self.cmd:
                    logger.warning(f'"{key}" 命令重复！')
                else:
                    self.cmd[key] = helper
            for tag in helper.tags:
                self.tags.setdefault(tag, HelperTags()).append(helper)
        elif isinstance(helpers, (list, HelperTags)):
            for helper in helpers:
                self.append(helper)

    def get(self, key: str) -> Optional[Union[Helper, HelperTags]]:
        """获取帮助内容

        Args:
            key (str): 命令的名称或者类型

        Returns:
            Optional[Union[Helper, HelperTags]]: 先从命令检索，命令检索错误从tag检索
        """
        if key:
            if helper := self.cmd.get(key):
                return helper
            return self.tags.get(key)
        return self
