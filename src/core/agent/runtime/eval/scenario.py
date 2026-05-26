from __future__ import annotations

from typing import Literal

from pydantic import Field, BaseModel

EvalCategory = Literal[
    "turn_closure",
    "delegation",
    "observation_quality",
    "reply_safety",
]


class EvalScenario(BaseModel):
    """A reusable Agent behavior scenario for regression gates."""

    name: str
    category: EvalCategory
    query: str
    expected_agents: list[str] = Field(default_factory=list)
    expected_tools: list[str] = Field(default_factory=list)
    forbidden_outputs: list[str] = Field(default_factory=list)
    notes: str = ""


class EvalReport(BaseModel):
    """Compact report for a group of Agent evaluation scenarios."""

    category: EvalCategory
    total: int = 0
    passed: int = 0
    failures: list[str] = Field(default_factory=list)

    def record(self, scenario: EvalScenario, passed: bool, detail: str = "") -> None:
        self.total += 1
        if passed:
            self.passed += 1
            return
        suffix = f": {detail}" if detail else ""
        self.failures.append(f"{scenario.name}{suffix}")
