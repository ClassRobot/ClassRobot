from os import urandom
from pathlib import Path
from hashlib import pbkdf2_hmac
from binascii import hexlify, unhexlify

from nonebot import logger, get_driver
from nonebot_plugin_localstore import get_config_dir

from .config import EncryptConfig

plugin_config = EncryptConfig.parse_obj(get_driver().config.dict())
config_salt: Path = get_config_dir("encrypt") / "salt.txt"


if plugin_config.encrypt_salt is None:
    if config_salt.exists():
        plugin_config.encrypt_salt = config_salt.read_text()
    else:
        plugin_config.encrypt_salt = hexlify(urandom(32)).decode()
        config_salt.write_text(plugin_config.encrypt_salt)
    logger.warning(
        f'"Encrypt salt"未设置,已随机生成并保存在"{config_salt}"建议将其添加到`.env`中.'
    )


def pbkdf2_sha256(
    password: str, salt: bytes | None = None, iterations=100000
) -> tuple[str, str]:
    """
    ```python
    # Example usage:
    password = "your_password"
    hashed_password, salt = pbkdf2_sha256(password)
    print(f"Hashed Password: {hashed_password}")
    print(f"Salt: {salt}")
    """
    salt = urandom(32) if salt is None else unhexlify(salt)
    dk = pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return hexlify(dk).decode(), hexlify(salt).decode()


if __name__ == "__main__":
    password = "your_password"
    hashed_password, salt = pbkdf2_sha256(password)
    print(f"Hashed Password: {hashed_password}")
    print(f"Salt: {salt}")
    hashed_password, salt = pbkdf2_sha256(password, salt.encode())
    print(f"Hashed Password: {hashed_password}")
    print(f"Salt: {salt}")
