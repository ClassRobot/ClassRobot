from base64 import b64encode
from pathlib import Path
from typing import Optional, Union
from .config import cqhttp_path


def get_qrcode(user_id: Union[str, int, Path]) -> Optional[str]:
    """获取登录二维码

    Args:
        user_id (Union[str, int, Path]): 机器人id或者二维码文件位置

    Returns:
        Optional[bytes]: 二维码数据
    """
    qrcode = user_id if isinstance(user_id, Path) else cqhttp_path / str(user_id) / "qrcode.png"
    if qrcode.exists():
        return b64encode(qrcode.read_bytes()).decode()

