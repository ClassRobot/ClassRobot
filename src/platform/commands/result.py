from __future__ import annotations

from typing import Any

from pydantic import Field, BaseModel


class CommandResult(BaseModel):
    """统一表示 service-style 命令处理结果。"""

    success: bool = True
    """命令是否执行成功。"""
    summary: str = ""
    """写入日志、Agent 观察和会话上下文的简短摘要。"""
    visible_outputs: list[str] = Field(default_factory=list)
    """面向最终用户展示的消息。"""
    context_outputs: list[str] = Field(default_factory=list)
    """面向会话上下文和 Agent 继续规划的紧凑输出。"""
    data: dict[str, Any] = Field(default_factory=dict)
    """供管理端或工作流使用的可选机器可读数据。"""
    requires_confirm: bool = False
    """是否因为需要用户确认而停止执行。"""
    followup_hint: str | None = None
    """提示调用方下一步可执行动作的可选说明。"""

    @classmethod
    def ok(
        cls,
        summary: str = "",
        *,
        visible_outputs: list[str] | None = None,
        context_outputs: list[str] | None = None,
        data: dict[str, Any] | None = None,
    ) -> "CommandResult":
        """构造成功命令结果。

        Args:
            summary: 执行摘要。
            visible_outputs: 用户可见输出列表。
            context_outputs: 会话上下文输出列表。
            data: 结构化数据。

        Returns:
            CommandResult: 成功结果对象。
        """

        return cls(
            success=True,
            summary=summary,
            visible_outputs=list(visible_outputs or ([] if not summary else [summary])),
            context_outputs=list(context_outputs or ([] if not summary else [summary])),
            data=dict(data or {}),
        )

    @classmethod
    def fail(cls, summary: str, *, visible_output: str | None = None) -> "CommandResult":
        """构造失败命令结果。

        Args:
            summary: 失败摘要。
            visible_output: 可选的用户可见失败文案。

        Returns:
            CommandResult: 失败结果对象。
        """

        return cls(
            success=False,
            summary=summary,
            visible_outputs=[visible_output or summary],
            context_outputs=[summary],
        )

    @property
    def observation_outputs(self) -> list[str]:
        """返回应写入 Agent 观察记录的输出。

        Returns:
            list[str]: 优先使用上下文输出，其次使用用户可见输出。
        """

        return self.context_outputs or self.visible_outputs or ([self.summary] if self.summary else [])
