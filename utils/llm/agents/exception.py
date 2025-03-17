class AgentException(Exception):
    ...


class SkipAgentException(AgentException):
    ...


class FinishAgentException(AgentException):
    ...
