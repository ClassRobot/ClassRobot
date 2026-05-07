from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Literal

from nonebot import logger

ProgressReporter = Callable[[str], Awaitable[None]]
ProgressStage = Literal["thinking", "route", "memory", "extract", "rag", "plan"]


@dataclass(slots=True)
class ProgressFeedbackHarness:
    """聚合面向用户的阶段反馈与轻量可观测性逻辑。"""

    trace_id: str = ""
    progress_reporter: ProgressReporter | None = None
    _last_progress: str = field(default="", init=False, repr=False)

    async def report_progress(self, message: str, stage: ProgressStage = "thinking") -> None:
        """发送去重后的阶段提示，失败时只记日志。"""

        formatted_message = self.format_progress_message(message, stage=stage)
        if not self.progress_reporter or not formatted_message or formatted_message == self._last_progress:
            return
        self._last_progress = formatted_message
        try:
            await self.progress_reporter(formatted_message)
        except Exception as error:
            logger.warning(f'AutoGPT trace "{self.trace_id}" progress feedback failed: {error}')

    @staticmethod
    def format_progress_message(message: str, stage: ProgressStage = "thinking") -> str:
        """为思考型反馈补上阶段前缀。"""

        text = message.strip()
        if not text:
            return ""
        prefix = f"{stage}: "
        if text.startswith(prefix):
            return text
        return prefix + text
