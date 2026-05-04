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


ENV_PATH = project_root / ".env"
VALID_COS_SCHEMES = {"http", "https"}

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
    return EncryptConfig.parse_obj(get_driver().config.dict())


def _model_configs_payload(mask: bool = True) -> list[dict[str, Any]]:
    configs = []
    for config in llm_config.llm_configs:
        item = config.dict()
        if mask:
            item["key"] = mask_secret(item.get("key"))
        configs.append(item)
    return configs


def get_settings() -> dict[str, Any]:
    driver_config = get_driver().config
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


def _stringify_env_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _validate_string(value: Any, field: str, *, allow_blank: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Setting `{field}` must be a string")
    if not allow_blank and not value.strip():
        raise ValueError(f"Setting `{field}` must not be blank")
    return value


def _validate_int(value: Any, field: str, *, minimum: int | None = None, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Setting `{field}` must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"Setting `{field}` must be greater than or equal to {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"Setting `{field}` must be less than or equal to {maximum}")
    return value


def _validate_float(value: Any, field: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Setting `{field}` must be a number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"Setting `{field}` must be a finite number")
    if minimum is not None and normalized < minimum:
        raise ValueError(f"Setting `{field}` must be greater than or equal to {minimum}")
    return normalized


def _validate_model_configs(value: Any, field: str) -> list[dict[str, Any]]:
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
    if not ENV_PATH.exists():
        return None
    backup_path = ENV_PATH.with_suffix(f".env.manager-backup")
    shutil.copy2(ENV_PATH, backup_path)
    return backup_path


def update_settings(payload: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
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
