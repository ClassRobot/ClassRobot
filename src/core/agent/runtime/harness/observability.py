from __future__ import annotations

from typing import Literal
from dataclasses import field, dataclass
from collections.abc import Callable, Sequence, Awaitable

from nonebot import logger

from ..schema import PromptStageMetric, ObservabilityStage, AgentObservabilityMetrics

ProgressReporter = Callable[[str], Awaitable[None]]
ProgressStage = Literal["thinking", "route", "memory", "extract", "rag", "plan"]


@dataclass(slots=True)
class ProgressFeedbackHarness:
    """聚合面向用户的阶段反馈与轻量可观测性逻辑。"""

    trace_id: str = ""
    progress_reporter: ProgressReporter | None = None
    _last_progress: str = field(default="", init=False, repr=False)
    _metrics: AgentObservabilityMetrics = field(default_factory=AgentObservabilityMetrics, init=False, repr=False)

    def __post_init__(self) -> None:
        """初始化默认可观测指标。"""

        self._metrics.trace_id = self.trace_id

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
        """把内部阶段提示转换成用户可见的自然语言。"""

        text = message.strip()
        if not text:
            return ""
        if stage in {"route", "extract", "plan"}:
            return ""
        prefixes = ("route: ", "extract: ", "plan: ", "rag: ", "memory: ", "thinking: ")
        for prefix in prefixes:
            if text.startswith(prefix):
                return text.removeprefix(prefix).strip()
        return text

    def record_prompt_stage(
        self,
        stage: ObservabilityStage,
        *,
        prompt_char_length: int,
        recalled_commands: Sequence[str] = (),
        recalled_skills: Sequence[str] = (),
        selected_commands: Sequence[str] = (),
    ) -> PromptStageMetric:
        """记录某个 Prompt 阶段的输入规模与能力召回结果。"""

        normalized_commands = self.normalize_names(recalled_commands)
        normalized_skills = self.normalize_names(recalled_skills)
        normalized_selected_commands = self.normalize_names(selected_commands)
        metric = PromptStageMetric(
            stage=stage,
            prompt_char_length=max(prompt_char_length, 0),
            recalled_commands=normalized_commands,
            recalled_command_count=len(normalized_commands),
            recalled_skills=normalized_skills,
            recalled_skill_count=len(normalized_skills),
            selected_commands=normalized_selected_commands,
        )
        for index, current in enumerate(self._metrics.prompt_stages):
            if current.stage == stage:
                self._metrics.prompt_stages[index] = metric
                return metric
        self._metrics.prompt_stages.append(metric)
        return metric

    def record_planner_candidate_commands(self, commands: Sequence[str]) -> None:
        """记录 Planner 阶段产出的候选命令集合。"""

        self._metrics.planner_candidate_commands = self.normalize_names(commands)

    def record_final_hit_commands(self, commands: Sequence[str]) -> None:
        """记录最终通过校验、可真正执行的命令集合。"""

        self._metrics.final_hit_commands = self.normalize_names(commands)

    def build_metrics(self) -> AgentObservabilityMetrics:
        """导出当前轮次的结构化可观测指标快照。"""

        self._metrics.trace_id = self.trace_id
        return self._metrics.model_copy(deep=True)

    @staticmethod
    def normalize_names(names: Sequence[str]) -> list[str]:
        """清理名称列表中的空值，保持原有顺序。"""

        normalized: list[str] = []
        for name in names:
            text = str(name).strip()
            if text:
                normalized.append(text)
        return normalized
