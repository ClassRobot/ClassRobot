from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
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

    @property
    def required(self) -> bool:
        """判断结构化 Agent 调用中该参数是否必填。

        Returns:
            bool: 如果参数不是可选或零个以上模式，则返回 ``True``。
        """

        return self.mode not in {ParamMode.OPTIONAL, ParamMode.ZERO_OR_MORE}
