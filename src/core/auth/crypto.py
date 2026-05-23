from __future__ import annotations

from os import urandom
from pathlib import Path
from hashlib import pbkdf2_hmac
from binascii import hexlify, unhexlify

from nonebot import logger, get_driver
from pydantic import Extra, BaseModel
from nonebot_plugin_localstore import get_config_dir


class EncryptConfig(BaseModel, extra=Extra.ignore):
    """描述密码散列与加密盐配置。"""

    encrypt_salt: str | None = None


plugin_config = EncryptConfig.parse_obj(get_driver().config.dict())
config_salt: Path = get_config_dir("encrypt") / "salt.txt"

if plugin_config.encrypt_salt is None:
    if config_salt.exists():
        plugin_config.encrypt_salt = config_salt.read_text()
    else:
        plugin_config.encrypt_salt = hexlify(urandom(32)).decode()
        config_salt.write_text(plugin_config.encrypt_salt)
    logger.warning(f'"Encrypt salt"未设置，已随机生成并保存在"{config_salt}"，建议将其添加到`.env`中。')


def pbkdf2_sha256(password: str, salt: bytes | None = None, iterations: int = 100000) -> tuple[str, str]:
    """使用 PBKDF2-SHA256 生成密码散列。

    Args:
        password: 原始密码。
        salt: 十六进制编码的盐；未提供时自动生成。
        iterations: 迭代次数。

    Returns:
        tuple[str, str]: 密码散列与十六进制盐。
    """

    salt_bytes = urandom(32) if salt is None else unhexlify(salt)
    derived_key = pbkdf2_hmac("sha256", password.encode(), salt_bytes, iterations)
    return hexlify(derived_key).decode(), hexlify(salt_bytes).decode()
