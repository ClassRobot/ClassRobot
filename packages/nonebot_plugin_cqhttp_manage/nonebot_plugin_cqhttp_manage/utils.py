from base64 import b64encode
from pathlib import Path
from pprint import pprint
from typing import Optional, Union
import yaml
from .config import cqhttp_path, FilePath


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


class BotConfigFile:
    def __init__(self, file: Optional[Union[str, Path]] = None):
        self.config: dict = self.load_yaml(file)
    
    @classmethod
    def bulk_edit(
        cls, 
        new_data: dict
    ):
        """批量修改

        Args:
            new_data (dict): 修改的数据
        """
        for file_dir in cqhttp_path.iterdir():
            cls.edit(file_dir, new_data)

    @classmethod
    def edit(
        cls, 
        bot_qq: Union[int, str, Path], 
        new_data: dict
    ):
        """修改bot信息

        Args:
            bot_qq (Union[int, str, Path]): 机器人qq
            new_data (dict): 用于update
        """
        config_file = (bot_qq if isinstance(bot_qq, Path) else (cqhttp_path / str(bot_qq))) / "config.yml"
        if config_file.exists():
            cls.save_yaml(
                config_file,
                cls.load_yaml(config_file) | new_data
            )

    @staticmethod
    def load_yaml(file: Optional[Union[str, Path]] = None) -> dict:
        """读取yaml文件进行修改

        Args:
            file (Optional[Union[str, Path]], optional): 文件路径，不填写则为默认配置文件. Defaults to None.

        Returns:
            dict: 内容
        """
        file = file or (FilePath.staticfile / "config.yml")
        with open(file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @staticmethod
    def save_yaml(file: Union[str, Path], data: Union[list, dict]):
        with open(file, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

    def save(self) -> Optional[Path]:
        if self.username:
            file = cqhttp_path / str(self.username)
            file.mkdir(parents=True, exist_ok=True)
            file /= "config.yml"
            self.save_yaml(file, self.config)
            return file

    @property
    def username(self) -> Union[None, int]:
        return self.config["account"]["uin"]

    @property
    def password(self) -> str:
        return self.config["account"]["password"]

    def set_user(self, username: int, password: str) -> "BotConfigFile":
        """设置用户账号密码

        Args:
            username (int): 账号
            password (str): 密码
        """
        self.config["account"]["uin"] = username
        self.config["account"]["password"] = password
        return self

