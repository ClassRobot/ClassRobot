from aiohttp import ClientSession
from pandas import DataFrame, Series
from datetime import datetime, timedelta
from typing import List, Optional, Generator, Any, Union, overload
import re

SHEET_DATE: datetime = datetime(1899, 12, 30)
docs_url = "https://docs.qq.com/dop-api/opendoc"
headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/94.0.4606.61 Safari/537.36 ",
    "content-type": "application/javascript; charset=utf-8",
    "referer": "https://docs.qq.com/sheet",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
    "content-encoding": "gzip",
    "appName": "Opera"
}


class ExtractError(Exception): ...
class ExtractDataError(ExtractError): ...
class InitialAttributedTextError(ExtractError): ...


def re_docs(text: str) -> Optional[str]:
    """获取文字中的表格链接

    Args:
        text (str): 文字

    Returns:
        Optional[str]: 表格链接
    """
    if url := re.search(r"https://docs.qq.com/sheet/\S[^\"']+", str(text).replace("\\", ""), re.I):
        return url.group()


class GetDocsSheet:
    def __init__(self, url: str):
        self.columns: int = 0
        self.rows: int = 0
        self.raw_data: dict = {}
        self.base_data = DataFrame()
        self.data = DataFrame()
        self.url: str = url

    @property
    def params(self) -> dict:
        """提取URL所需params"""
        params = {
            "outformat": 1,
            "normal": 1
        }
        url = self.url.split("/")[-1]
        param = re.findall(r"^\w+|tab=\w+", url)
        params["id"] = param[0]
        if len(param) > 1:
            params["tab"] = param[1].replace("tab=", "")
        return params

    async def get(self) -> dict:
        async with ClientSession(headers=headers) as session:
            async with session.get(docs_url, params=self.params) as res:
                return await res.json()

    @staticmethod
    def extract(data: dict) -> Optional[list]:
        if data := data["clientVars"]["collab_client_vars"].get("initialAttributedText"):
            for values in data["text"][0]:
                for value in values:
                    try:
                        if isinstance(value["c"][1], dict):
                            for i in value:
                                if isinstance(value[i], list):
                                    return value[i]
                    except IndexError:
                        continue
            else:
                raise ExtractDataError("No data found")
        else:
            raise InitialAttributedTextError("Table data extraction failed")

    def __repr__(self) -> str:
        return repr(self.data)

    def convert2d(self) -> List[list]:
        """
        转换为二维列表
        从列表第一位开始取，按照长度推算出后面内容的序号
        然后按照序号去循环，推导出内容
            如果序号存在就查看序号内是否有值，取出值
            不存在则全部替换为空
        """
        data = []
        keys = list(self.raw_data.keys())
        length, index = len(keys), 0
        while index < length:
            key = int(keys[index])
            if not key % self.columns:
                arr = []
                for k in range(key, key + self.columns):
                    if values := self.raw_data.get(str(k)):
                        index += 1
                        value = values.get("2")
                        arr.append(value[1] if value else value)
                        continue 
                    arr.append(values)
                data.append(arr)
            else:
                index += 1
        return data

    def data_frame(self) -> DataFrame:
        """
        找出columns所在位置
        """
        # 清除空行空列
        self.base_data = DataFrame(self.convert2d(), dtype=str).apply(lambda x: x.str.strip())
        self.base_data.dropna(axis=0, how='all', inplace=True)
        self.base_data.dropna(axis=1, how='all', inplace=True)
        for i, v in (j for j in self.base_data.iterrows() if all(j[1])):
            return self.base_data.loc[i+1:].rename(columns=v)   # type: ignore
        return DataFrame()

    async def __aenter__(self) -> "GetDocsSheet":
        if data := self.extract(await self.get()):
            self.columns: int = data[0][-1] + 1
            self.rows: int = data[0][-3] + 1
            self.raw_data: dict = data[1]
            self.data = self.data_frame()
        return self

    def __await__(self) -> Generator[Any, None, "GetDocsSheet"]:
        return self.__aenter__().__await__()

    @staticmethod
    def get_excel_date(date_int: Union[str, int]) -> Optional[str]:
        """对于excel日期进行转换，以便写入数据"""
        return str((SHEET_DATE + timedelta(int(date_int) + 1)).date()) if date_int else None

    @overload
    def reset_date(self, colunm: str = "出生日期", inplace: bool = True) -> None: ...
    @overload
    def reset_date(self, colunm: str = "出生日期", inplace: bool = False) -> Series: ...
    def reset_date(self, colunm: str = "出生日期", inplace: bool = False) -> Optional[Series]:
        """重置表格日期表格"""
        try:
            if not self.data.empty:
                item: Generator = (self.get_excel_date(i) for i in self.data[colunm])
                if not inplace:
                    return Series(item)
                self.data[colunm] = item
        except IndexError:
            ...
    
    def __bool__(self) -> bool:
        return not self.data.empty

    async def __aexit__(self, *_):
       ...
