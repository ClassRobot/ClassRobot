from typing import Any


class AgentException(Exception):
    ...


class AgentResult(AgentException):
    result: Any

    def __init__(self, result: Any, *args: object) -> None:
        super().__init__(*args)
        self.result = result


class SkipAgentException(AgentResult):
    ...


class FinishAgentException(AgentResult):
    ...
