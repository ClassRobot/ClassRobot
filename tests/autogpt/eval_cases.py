from pydantic import BaseModel, Field


class RouteEvalCase(BaseModel):
    """描述一条路由回归样例。"""

    name: str
    query: str
    expected_intent: str
    expected_command: str


class ToolEvalCase(BaseModel):
    """描述一条命令召回回归样例。"""

    name: str
    query: str
    expected_command: str
    limit: int = 1


class ArgEvalCase(BaseModel):
    """描述一条参数抽取回归样例。"""

    name: str
    query: str
    expected_command: str
    expected_params: list[str] = Field(default_factory=list)


class EvalGateReport(BaseModel):
    """汇总一类评测样例的通过情况。"""

    category: str
    total: int = 0
    passed: int = 0
    failures: list[str] = Field(default_factory=list)

    def record(self, case_name: str, passed: bool, detail: str = "") -> None:
        """登记一条样例结果。"""

        self.total += 1
        if passed:
            self.passed += 1
            return
        failure = case_name if not detail else f"{case_name}: {detail}"
        self.failures.append(failure)


ROUTE_EVAL_CASES = [
    RouteEvalCase(
        name="self-info-route",
        query="我的身份是管理员吗",
        expected_intent="command",
        expected_command="我的信息",
    ),
    RouteEvalCase(
        name="owned-class-route",
        query="我有创建班级吗",
        expected_intent="command",
        expected_command="查询班级",
    ),
    RouteEvalCase(
        name="tomorrow-schedule-route",
        query="我明天有什么课",
        expected_intent="command",
        expected_command="查询课表",
    ),
]


TOOL_EVAL_CASES = [
    ToolEvalCase(
        name="notify-tool-recall",
        query="帮我发一个班级通知",
        expected_command="创建通知",
    ),
    ToolEvalCase(
        name="schedule-tool-recall",
        query="查看我的课表",
        expected_command="查询课表",
    ),
    ToolEvalCase(
        name="self-info-tool-recall",
        query="我现在是什么身份",
        expected_command="我的信息",
    ),
]


ARG_EVAL_CASES = [
    ArgEvalCase(
        name="tomorrow-arg",
        query="我明天有什么课",
        expected_command="查询课表",
        expected_params=["1"],
    ),
    ArgEvalCase(
        name="day-after-tomorrow-arg",
        query="我后天有什么课",
        expected_command="查询课表",
        expected_params=["2"],
    ),
    ArgEvalCase(
        name="yesterday-arg",
        query="我昨天有什么课",
        expected_command="查询课表",
        expected_params=["-1"],
    ),
]
