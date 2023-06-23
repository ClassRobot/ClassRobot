import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Union, Optional

from utils import run_sync
from nonebot import get_bot
from pandas import DataFrame
from imgkit import from_string
from nonebot.matcher import Matcher
from nb_cli.cli.utils import run_sync
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    GroupMessageEvent,
    PrivateMessageEvent,
)


def match_date(date_str: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    date_pattern = re.compile(r"(\d{4})?\s?(\d{1,2})?\s?(\d{1,2})?")
    match = date_pattern.match(date_str)
    if match:
        year, month, day = match.groups()
        return year, month, day
    return None, None, None


def query_date(
    string: str, key_name: str, default_now: bool = True
) -> Optional[Dict[str, int]]:
    """django查询的日期

    Args:
        string (str): 查询的字符串
        key_name (str): 键名
        default_now (bool, optional): 默认当前日期. Defaults to True.

    Returns:
        Optional[Dict[str, int]]: 查询
    """
    now_date = datetime.now()
    dates = match_date(string)
    query_date = {key_name + "__year": now_date.year} if default_now else {}
    if any(dates):
        return query_date | {
            f"{key_name}__{i}": int(v)
            for i, v in zip(["year", "month", "day"], dates)
            if v is not None
        }
    elif default_now:
        query_date[f"{key_name}__month"] = now_date.month
        return query_date


def check_data(
    raw_data: DataFrame,
    check_data: DataFrame,
    columns: Optional[Union[List[str], Dict[str, List[str]]]],
) -> DataFrame:
    """检查两组数据是否相同，返回不同的数据

    Args:
        raw_data (DataFrame): 原本的数据
        check_data (DataFrame): 需要进行检查的数据
        columns (Optional[Union[List[str], Dict[str, List[str]]]]): 需要检查的列
            当columns为None直接对raw_data进行检查
            当columns为List就从raw_data和check_data取出对应的columns进行检查
            当columns为Dict时候，就将columns的keys作为raw_data中需要取出来检查的那些列
                values的list作为对应key的别名，通过list检查check_data是否有这个key，如果有就将对应的column名字改为key的名字

    Returns:
        DataFrame: 不同的那几行数据
    """
    raw_data, check_data = raw_data.copy(), check_data.copy()
    if isinstance(columns, dict):
        rename = {i: k for k, v in columns.items() for i in [k, *v]}
        raw_data.rename(columns=rename, inplace=True)
        check_data.rename(columns=rename, inplace=True)
        columns = list(columns.keys())
    if isinstance(columns, list):
        raw_data = raw_data.loc[:, columns]
        check_data = check_data.loc[:, columns]
    return check_data[~raw_data.isin(raw_data)]


async def upload_file(
    event: MessageEvent,
    file: Path,
    name: Optional[str] = None,
    bot: Optional[Bot] = None,
):
    self_bot = get_bot(str(event.self_id)) if bot is None else bot
    name = file.name if name is None else name
    if isinstance(event, GroupMessageEvent):
        await self_bot.call_api(
            "upload_group_file", group_id=event.group_id, file=str(file), name=name
        )
    elif isinstance(event, PrivateMessageEvent):
        await self_bot.call_api(
            "upload_private_file", user_id=event.user_id, file=str(file), name=name
        )


async def html_to_image(html: str, options: Optional[dict] = None, width=600) -> bytes:
    return await run_sync(from_string)(  # type: ignore
        html,
        None,
        options={
            "width": width,
            "encoding": "UTF-8",
        }
        | (options or {}),
    )


class MessageArgs:
    """消息多参数获取"""

    def __init__(
        self, args: Union[list, dict], matcher: Matcher, reply: Union[list, str] = ""
    ):
        """消息参数获取

        Args:
            args (Union[list, dict]): 需要获取的参数名称
                dict:
                    key: 返回的对象的key
                    value: 回复内容
                    传递的参数为dict时，会将key作为最终返回的key而value作为返回消息的名称
                list:
                    如果参数为list会将key和value设置为同一个
            matcher (Matcher): 消息对象
            reply (Union[list, str], optional): 回复的消息. Defaults to "{}".
                当传入list会对回复消息于要获取的参数一一对应，当回复消息短时会保持取最后一个

        Docs:
            ma = MessageArgs({"key": "value"})
            kwargs = await ma(params)
        """
        self.args: dict = args if isinstance(args, dict) else {i: i for i in args}
        self.kwargs: Dict[str, Optional[str]] = {k: None for k in self.args.keys()}
        self.__reply: Union[list, str] = reply or "{}"
        self.matcher: Matcher = matcher

    @property
    def reply(self) -> str:
        if isinstance(self.__reply, str):
            return self.__reply
        if len(self.__reply) == 1:
            self.__reply = self.__reply.pop(0)
            return self.__reply
        return self.__reply.pop(0)

    def __format__(self, _: str) -> str:
        return self.reply.format(self.args)

    async def __call__(self, params: Union[List[str], str]) -> dict:
        """取出所需参数

        Args:
            params (Union[List[str], str]): 需要传入对应位置的参数

        Returns:
            dict: 当参数接收完成后，作为dict传递出去
        """
        if isinstance(params, str):
            params = params.split()
        for k in self.kwargs:
            if self.kwargs[k] is None:
                if params:
                    self.kwargs[k] = params.pop(0)
                else:
                    await self.matcher.reject(self.reply.format(self.args[k]))
        return self.kwargs
