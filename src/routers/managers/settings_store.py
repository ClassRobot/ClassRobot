from __future__ import annotations

import json
import math
import shutil
from pathlib import Path
from typing import Any

from nonebot import get_driver

from utils.config import project_root
from utils.cache.config import plugin_config as cache_config
from utils.llm.config import plugin_config as llm_config
from utils.llm.config import LLMConfig
from utils.tools.cos.config import plugin_config as cos_config
from utils.encrypt.config import EncryptConfig

from .service import mask_secret


driver = get_driver()
ENV_PATH = project_root / ".env"
VALID_COS_SCHEMES = {"http", "https"}
SENSITIVE_ENV_KEYWORDS = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "PWD",
    "KEY",
    "SALT",
    "AUTH",
    "CREDENTIAL",
    "PRIVATE",
)

# 前端设置请求按分组字段提交；这里负责映射到真实的 .env 键名。
FIELD_TO_ENV = {
    "base": {
        "global_proxy": "GLOBAL_PROXY",
        "wsl_share_dir": "WSL_SHARE_DIR",
        "teacher_max_classes": "TEACHER_MAX_CLASSES",
    },
    "ai": {
        "googleapis_key": "GOOGLEAPIS_KEY",
        "ragflow_url": "RAGFLOW_URL",
        "ragflow_key": "RAGFLOW_KEY",
    },
    "cache": {
        "cache_host": "CACHE_HOST",
        "cache_port": "CACHE_PORT",
    },
    "cos": {
        "cos_secret_id": "COS_SECRET_ID",
        "cos_secret_key": "COS_SECRET_KEY",
        "region": "REGION",
        "bucket": "BUCKET",
        "scheme": "SCHEME",
    },
    "security": {
        "encrypt_salt": "ENCRYPT_SALT",
    },
    "models": {
        "llm_configs": "llm_configs",
        "llm_timeout": "llm_timeout",
    },
}


def _encrypt_config() -> EncryptConfig:
    """从当前 NoneBot 配置构造加密配置对象。

    Returns:
        EncryptConfig: 解析后的加密配置。
    """
    return EncryptConfig.parse_obj(driver.config.dict())


def _model_configs_payload(mask: bool = True) -> list[dict[str, Any]]:
    """序列化模型配置列表。

    Args:
        mask: 是否对模型 API key 做脱敏。

    Returns:
        list[dict[str, Any]]: 模型配置列表。
    """
    configs = []
    for config in llm_config.llm_configs:
        item = config.dict()
        if mask:
            item["key"] = mask_secret(item.get("key"))
        configs.append(item)
    return configs


def get_settings() -> dict[str, Any]:
    """读取设置页需要的完整配置 payload。

    Returns:
        dict[str, Any]: 按页面分组组织的设置数据。
    """
    driver_config = driver.config
    encrypt_config = _encrypt_config()
    return {
        "base": {
            "global_proxy": getattr(driver_config, "global_proxy", None),
            "wsl_share_dir": str(getattr(driver_config, "wsl_share_dir", "") or "") or None,
            "teacher_max_classes": getattr(driver_config, "teacher_max_classes", 6),
        },
        "ai": {
            "googleapis_key": mask_secret(getattr(driver_config, "googleapis_key", None)),
            "ragflow_url": getattr(driver_config, "ragflow_url", None),
            "ragflow_key": mask_secret(getattr(driver_config, "ragflow_key", None)),
        },
        "cache": {
            "cache_host": cache_config.cache_host,
            "cache_port": cache_config.cache_port,
        },
        "cos": {
            "cos_secret_id": mask_secret(cos_config.cos_secret_id),
            "cos_secret_key": mask_secret(cos_config.cos_secret_key),
            "region": cos_config.region,
            "bucket": cos_config.bucket,
            "scheme": cos_config.scheme,
        },
        "security": {
            "encrypt_salt": mask_secret(encrypt_config.encrypt_salt),
        },
        "models": {
            "llm_timeout": llm_config.llm_timeout,
            "llm_configs": _model_configs_payload(),
        },
    }


def _config_group_label(key: str) -> str:
    """根据配置项名称生成管理端展示分组。

    Args:
        key: 配置项名称。

    Returns:
        str: 用于前端分组展示的中文标签。
    """
    upper_key = key.upper()
    if upper_key in {
        "HOST",
        "PORT",
        "DRIVER",
        "ENV",
        "DEBUG",
        "LOG_LEVEL",
        "API_TIMEOUT",
        "SUPERUSERS",
        "NICKNAME",
        "COMMAND_START",
        "COMMAND_SEP",
        "SESSION_EXPIRE_TIMEOUT",
        "ACCESS_TOKEN",
        "SECRET",
    }:
        return "NoneBot 核心"
    if upper_key.startswith(("COS_", "BUCKET", "REGION", "SCHEME")):
        return "对象存储"
    if upper_key.startswith(("RAGFLOW", "GOOGLE", "LLM", "MODEL")) or "OPENAI" in upper_key:
        return "AI 服务"
    if upper_key.startswith(("CACHE", "REDIS")):
        return "缓存"
    if upper_key.startswith(("DB", "DATABASE", "SQLALCHEMY")):
        return "数据库"
    if any(keyword in upper_key for keyword in ("TOKEN", "SECRET", "PASSWORD", "SALT", "AUTH")):
        return "安全"
    if upper_key.startswith(("HOST", "PORT", "ENV", "LOG", "GLOBAL", "WSL", "TEACHER")):
        return "运行"
    if upper_key.startswith(("PLUGIN", "ADAPTER", "BOT")):
        return "插件与适配器"
    return "其他"


def _is_sensitive_config_key(key: str) -> bool:
    """判断配置项名称是否可能包含敏感信息。

    Args:
        key: 配置项名称。

    Returns:
        bool: 命中敏感关键词时返回 ``True``。
    """
    upper_key = key.upper()
    return any(keyword in upper_key for keyword in SENSITIVE_ENV_KEYWORDS)


def _dump_driver_config() -> dict[str, Any]:
    """导出当前 NoneBot driver 的完整配置字典。

    Returns:
        dict[str, Any]: ``driver.config`` 的字典表示。
    """
    config = driver.config
    if hasattr(config, "model_dump"):
        return config.model_dump()  # type: ignore[return-value]
    if hasattr(config, "dict"):
        return config.dict()  # type: ignore[return-value]
    return dict(config)


def _normalize_config_value(value: Any) -> Any:
    """把运行配置值转换成可序列化的数据结构。

    Args:
        value: 原始配置值。

    Returns:
        Any: 适合写入 JSON 响应的标准化值。
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): _normalize_config_value(item) for key, item in value.items()}
    if isinstance(value, set):
        return [_normalize_config_value(item) for item in sorted(value, key=str)]
    if isinstance(value, (list, tuple)):
        return [_normalize_config_value(item) for item in value]
    if hasattr(value, "model_dump"):
        return _normalize_config_value(value.model_dump())
    if hasattr(value, "dict"):
        return _normalize_config_value(value.dict())
    return str(value)


def _stringify_snapshot_value(value: Any) -> str:
    """把标准化后的配置值渲染成前端展示与复制文本。

    Returns:
        str: 文本形式的配置值。
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def _config_value_type(value: Any) -> str:
    """返回配置值的人类可读类型标签。

    Args:
        value: 原始配置值。

    Returns:
        str: 前端展示用的值类型名称。
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, Path):
        return "path"
    if isinstance(value, bytes):
        return "bytes"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, (list, tuple, set)):
        return "list"
    return type(value).__name__


def get_runtime_config_snapshot() -> dict[str, Any]:
    """读取当前 ``driver.config`` 的完整运行配置快照。

    Returns:
        dict[str, Any]: 包含 driver 元信息与配置项列表的只读快照。
    """
    config_data = _dump_driver_config()
    items: list[dict[str, Any]] = []
    for key, raw_value in config_data.items():
        normalized_value = _normalize_config_value(raw_value)
        value_text = _stringify_snapshot_value(normalized_value)
        sensitive = _is_sensitive_config_key(key)
        items.append(
            {
                "key": key,
                "value": value_text,
                "masked_value": mask_secret(value_text) if sensitive else value_text,
                "sensitive": sensitive,
                "group": _config_group_label(key),
                "value_type": _config_value_type(raw_value),
                "empty": value_text == "",
            }
        )

    return {
        "driver": driver.__class__.__name__,
        "config_model": driver.config.__class__.__name__,
        "env_path": str(ENV_PATH),
        "env_exists": ENV_PATH.exists(),
        "total": len(items),
        "sensitive_total": sum(1 for item in items if item["sensitive"]),
        "items": items,
    }


def _stringify_env_value(value: Any) -> str:
    """把 Python 值转换成 dotenv 可写入的字符串。

    Args:
        value: 原始配置值。

    Returns:
        str: 适合写入 ``.env`` 的字符串形式。
    """
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _validate_string(value: Any, field: str, *, allow_blank: bool = True) -> str:
    """校验字符串设置项。

    Args:
        value: 待校验的值。
        field: 字段名，用于错误提示。
        allow_blank: 是否允许空白字符串。

    Returns:
        str: 通过校验的字符串值。

    Raises:
        ValueError: 当值类型或内容不合法时抛出。
    """
    if not isinstance(value, str):
        raise ValueError(f"Setting `{field}` must be a string")
    if not allow_blank and not value.strip():
        raise ValueError(f"Setting `{field}` must not be blank")
    return value


def _validate_int(value: Any, field: str, *, minimum: int | None = None, maximum: int | None = None) -> int:
    """校验整数设置项。

    Args:
        value: 待校验的值。
        field: 字段名，用于错误提示。
        minimum: 可选的最小值约束。
        maximum: 可选的最大值约束。

    Returns:
        int: 通过校验的整数值。

    Raises:
        ValueError: 当值不是合法整数或超出范围时抛出。
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Setting `{field}` must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"Setting `{field}` must be greater than or equal to {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"Setting `{field}` must be less than or equal to {maximum}")
    return value


def _validate_float(value: Any, field: str, *, minimum: float | None = None) -> float:
    """校验浮点数设置项。

    Args:
        value: 待校验的值。
        field: 字段名，用于错误提示。
        minimum: 可选的最小值约束。

    Returns:
        float: 通过校验的浮点值。

    Raises:
        ValueError: 当值不是有限数字或超出范围时抛出。
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Setting `{field}` must be a number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"Setting `{field}` must be a finite number")
    if minimum is not None and normalized < minimum:
        raise ValueError(f"Setting `{field}` must be greater than or equal to {minimum}")
    return normalized


def _validate_model_configs(value: Any, field: str) -> list[dict[str, Any]]:
    """校验模型配置列表。

    Args:
        value: 前端提交的模型配置列表。
        field: 字段名，用于错误提示。

    Returns:
        list[dict[str, Any]]: 通过校验并标准化后的模型配置列表。

    Raises:
        ValueError: 当任一模型配置不合法时抛出。
    """
    if not isinstance(value, list):
        raise ValueError(f"Setting `{field}` must be a list")

    names: set[str] = set()
    items: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"Setting `{field}[{index}]` must be an object")
        try:
            config = LLMConfig.parse_obj(item)
        except Exception as error:  # noqa: BLE001
            raise ValueError(f"Setting `{field}[{index}]` is invalid: {error}") from error
        for key in ("name", "key", "url", "model"):
            raw_value = getattr(config, key)
            if not isinstance(raw_value, str) or not raw_value.strip():
                raise ValueError(f"Setting `{field}[{index}].{key}` must not be blank")
        if not config.url.startswith(("http://", "https://")):
            raise ValueError(f"Setting `{field}[{index}].url` must start with http:// or https://")
        if config.name in names:
            raise ValueError(f"Setting `{field}` contains duplicate model name `{config.name}`")
        names.add(config.name)
        items.append(config.dict())
    return items


def _validate_value(group: str, key: str, value: Any) -> Any:
    """按设置分组分派字段校验逻辑。

    Args:
        group: 设置分组名称。
        key: 分组内字段名。
        value: 待校验的值。

    Returns:
        Any: 通过校验后的标准化值。
    """
    field = f"{group}.{key}"
    if group == "base":
        if key in {"global_proxy", "wsl_share_dir"}:
            return _validate_string(value, field)
        if key == "teacher_max_classes":
            return _validate_int(value, field, minimum=1)
    if group == "ai":
        if key in {"googleapis_key", "ragflow_url", "ragflow_key"}:
            return _validate_string(value, field)
    if group == "cache":
        if key == "cache_host":
            return _validate_string(value, field, allow_blank=False)
        if key == "cache_port":
            return _validate_int(value, field, minimum=1, maximum=65535)
    if group == "cos":
        if key in {"cos_secret_id", "cos_secret_key", "region", "bucket"}:
            return _validate_string(value, field)
        if key == "scheme":
            scheme = _validate_string(value, field, allow_blank=False).lower()
            if scheme not in VALID_COS_SCHEMES:
                raise ValueError(f"Setting `{field}` must be one of: {', '.join(sorted(VALID_COS_SCHEMES))}")
            return scheme
    if group == "security":
        if key == "encrypt_salt":
            return _validate_string(value, field, allow_blank=False)
    if group == "models":
        if key == "llm_timeout":
            return _validate_float(value, field, minimum=0.1)
        if key == "llm_configs":
            return _validate_model_configs(value, field)
    return value


def _backup_env() -> Path | None:
    """备份当前 ``.env`` 文件。

    Returns:
        Path | None: 备份文件路径；如果源文件不存在则返回 ``None``。
    """
    if not ENV_PATH.exists():
        return None
    backup_path = ENV_PATH.with_suffix(f".env.manager-backup")
    shutil.copy2(ENV_PATH, backup_path)
    return backup_path


def update_settings(payload: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    """校验并写入设置到 ``.env``。

    Args:
        payload: 前端提交的分组设置更新数据。

    Returns:
        dict[str, Any]: 保存结果、是否需要重启以及变更字段列表。

    Raises:
        RuntimeError: 当缺少 ``python-dotenv`` 依赖时抛出。
        ValueError: 当字段名不支持或字段值校验失败时抛出。
    """
    try:
        from dotenv import set_key
    except Exception as error:  # noqa: BLE001
        raise RuntimeError("python-dotenv is required to update .env settings") from error

    changed_keys: list[str] = []
    invalid_keys: list[str] = []
    normalized_payload: dict[str, dict[str, Any]] = {}

    for group, values in payload.items():
        if not values:
            continue
        allowed = FIELD_TO_ENV.get(group, {})
        normalized_group: dict[str, Any] = {}
        for key, value in values.items():
            if key not in allowed:
                invalid_keys.append(f"{group}.{key}")
                continue
            if value is None:
                continue
            changed_keys.append(allowed[key])
            normalized_group[key] = _validate_value(group, key, value)
        if normalized_group:
            normalized_payload[group] = normalized_group

    if invalid_keys:
        raise ValueError(f"Unsupported setting keys: {', '.join(invalid_keys)}")
    if not changed_keys:
        return {"saved": False, "restart_required": False, "changed_keys": []}

    _backup_env()
    ENV_PATH.touch(exist_ok=True)

    for group, values in normalized_payload.items():
        if not values:
            continue
        allowed = FIELD_TO_ENV[group]
        for key, value in values.items():
            set_key(str(ENV_PATH), allowed[key], _stringify_env_value(value), quote_mode="auto")

    return {
        "saved": True,
        "restart_required": True,
        "changed_keys": list(dict.fromkeys(changed_keys)),
    }
