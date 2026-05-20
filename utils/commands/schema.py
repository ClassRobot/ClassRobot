from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, root_validator
from utils.helper import ParamMode

CommandRiskLevel = Literal["low", "medium", "high"]
CommandExecutionMode = Literal["service", "matcher", "interactive", "disabled"]


class CommandParam(BaseModel):
    """描述一条命令参数的统一元数据。

    该模型会同时被帮助菜单、命令声明和 Agent 工具 schema 复用，
    因此参数名称、数量模式和类型信息都应在这里保持一致。
    """

    name: str
    description: str = ""
    mode: ParamMode | None = None
    value_type: str = "string"
    multiple: bool = False
    source_name: str | None = None
    required: bool = True

    @root_validator(pre=True)
    def infer_required_from_mode(cls, values):
        """未显式声明时，根据参数数量模式推断是否必填。"""

        if values.get("required") is None:
            mode = values.get("mode")
            values["required"] = mode not in {ParamMode.OPTIONAL, ParamMode.ZERO_OR_MORE, "?", "*"}
        return values
