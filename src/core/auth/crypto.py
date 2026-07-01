from __future__ import annotations

from os import urandom
from pathlib import Path
from hmac import compare_digest
from hmac import new as hmac_new
from binascii import hexlify, unhexlify
from hashlib import sha256, pbkdf2_hmac
from base64 import urlsafe_b64decode, urlsafe_b64encode

from nonebot import logger, get_driver
from pydantic import BaseModel, ConfigDict
from nonebot_plugin_localstore import get_config_dir


class EncryptConfig(BaseModel):
    """描述密码散列与加密盐配置。"""

    model_config = ConfigDict(extra="ignore")

    encrypt_salt: str | None = None


plugin_config = EncryptConfig.model_validate(get_driver().config.model_dump())
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


def encrypt_text(value: str) -> str:
    """加密需要落库保存的短文本。

    当前主要用于保存第三方平台 token。实现使用项目统一的
    ``encrypt_salt`` 派生密钥，并为每次加密生成随机 nonce，避免同一
    token 多次加密得到相同密文。

    Args:
        value: 需要加密的原始文本。

    Returns:
        str: 带版本前缀的密文。
    """

    plaintext = value.encode()
    nonce = urandom(16)
    key = _crypto_key()
    cipher = _xor_with_stream(plaintext, key, nonce)
    tag = hmac_new(key, nonce + cipher, sha256).digest()
    payload = urlsafe_b64encode(nonce + tag + cipher).decode()
    return f"v1:{payload}"


def decrypt_text(value: str) -> str:
    """解密由 :func:`encrypt_text` 生成的短文本密文。

    Args:
        value: 带版本前缀的密文。

    Returns:
        str: 解密后的原始文本。

    Raises:
        ValueError: 密文格式不正确或校验失败。
    """

    if not value.startswith("v1:"):
        raise ValueError("unsupported encrypted text format")
    try:
        payload = urlsafe_b64decode(value[3:].encode())
    except Exception as e:
        raise ValueError("invalid encrypted text payload") from e
    if len(payload) < 48:
        raise ValueError("invalid encrypted text payload")

    nonce = payload[:16]
    tag = payload[16:48]
    cipher = payload[48:]
    key = _crypto_key()
    expected_tag = hmac_new(key, nonce + cipher, sha256).digest()
    if not compare_digest(tag, expected_tag):
        raise ValueError("encrypted text signature mismatch")
    return _xor_with_stream(cipher, key, nonce).decode()


def _crypto_key() -> bytes:
    """从项目加密盐派生固定长度密钥。"""

    salt = plugin_config.encrypt_salt or ""
    try:
        salt_bytes = unhexlify(salt)
    except Exception:
        salt_bytes = salt.encode()
    return sha256(salt_bytes + b":classrobot:token").digest()


def _xor_with_stream(data: bytes, key: bytes, nonce: bytes) -> bytes:
    """使用 HMAC 派生字节流并与数据异或。"""

    chunks: list[bytes] = []
    counter = 0
    produced = 0
    while produced < len(data):
        counter_bytes = counter.to_bytes(4, "big")
        chunk = hmac_new(key, nonce + counter_bytes, sha256).digest()
        chunks.append(chunk)
        produced += len(chunk)
        counter += 1
    stream = b"".join(chunks)[: len(data)]
    return bytes(left ^ right for left, right in zip(data, stream))
