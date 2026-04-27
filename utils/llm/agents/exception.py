from typing import Any


class AgentException(Exception):
    """表示智能体exception异常。"""

    ...


class AgentResult(AgentException):
    """表示智能体result异常。"""

    result: Any

    def __init__(self, result: Any, *args: object) -> None:
        """初始化实例。

        参数:
            result (Any): result。
            args (*object): 可变位置参数。
        """
        super().__init__(*args)
        self.result = result


class SkipAgentException(AgentResult):
    """表示skip智能体exception异常。"""

    ...


class FinishAgentException(AgentResult):
    """表示finish智能体exception异常。"""

    ...
