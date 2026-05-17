import hashlib
from io import BytesIO
from typing import Annotated

from utils.config import temp_dir
from nonebot.params import Depends
from nonebot_plugin_alconna import File
from pandas import DataFrame, read_excel
from utils.tools import download_file, get_url_suffix, get_file_suffix

from .util import rename


async def import_dataframe(import_file: File) -> DataFrame | None:
    """将导入文件解析为 DataFrame。"""
    if not import_file.url:
        return None
    data = await download_file(import_file.url)
    md5 = hashlib.md5(data).hexdigest()
    suffix = get_url_suffix(import_file.url) or get_file_suffix(data)
    to_path = temp_dir / (f"{md5}.{suffix}" if suffix else md5)
    await download_file(data, to_path=to_path)
    df = read_excel(BytesIO(data))
    df.columns = df.columns.map(rename)
    return df


ImportDataFrame = Annotated[DataFrame, Depends(import_dataframe)]
