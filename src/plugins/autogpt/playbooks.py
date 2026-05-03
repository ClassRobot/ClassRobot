from pydantic import Field, BaseModel


class WorkflowPlaybookStep(BaseModel):
    """描述工作流模板中的单个步骤。"""

    command: str
    """该步骤对应的项目命令。"""
    title: str
    """步骤标题。"""
    description: str = ""
    """步骤说明。"""


class WorkflowPlaybook(BaseModel):
    """描述一组可复用的项目内工作流模板。"""

    playbook_id: str
    """模板唯一标识。"""
    name: str
    """模板名称。"""
    description: str
    """模板用途说明。"""
    steps: list[WorkflowPlaybookStep] = Field(default_factory=list)
    """模板内的标准步骤。"""

    def matches(self, commands: list[str]) -> bool:
        """判断当前命令序列是否能命中该模板。"""

        if not commands or len(commands) > len(self.steps):
            return False

        index = 0
        for step in self.steps:
            if index >= len(commands):
                break
            if step.command == commands[index]:
                index += 1
        return index == len(commands)


class WorkflowPlaybookCatalog(BaseModel):
    """维护所有可供 Agent 选择的工作流模板。"""

    playbooks: list[WorkflowPlaybook] = Field(default_factory=list)

    @classmethod
    def default(cls) -> "WorkflowPlaybookCatalog":
        """返回项目内置的稳定模板集合。"""

        return cls(
            playbooks=[
                WorkflowPlaybook(
                    playbook_id="class_bootstrap_and_notice",
                    name="班级初始化并通知",
                    description="先创建班级，随后调整加入方式，并向成员发送通知。",
                    steps=[
                        WorkflowPlaybookStep(
                            command="添加班级",
                            title="创建班级",
                            description="先把班级建立起来，确保后续通知和加入方式配置有明确对象。",
                        ),
                        WorkflowPlaybookStep(
                            command="修改班级加入方式",
                            title="配置班级加入方式",
                            description="根据老师要求设置班级加入策略，减少后续入班管理成本。",
                        ),
                        WorkflowPlaybookStep(
                            command="创建通知",
                            title="发布班级通知",
                            description="将班级建立或调整结果同步给相关成员。",
                        ),
                    ],
                ),
                WorkflowPlaybook(
                    playbook_id="task_publish_and_notify",
                    name="创建任务并通知",
                    description="先创建任务，再通过通知能力同步给相关对象。",
                    steps=[
                        WorkflowPlaybookStep(
                            command="创建任务",
                            title="创建任务",
                            description="先建立任务主体，保证后续通知引用的对象已经存在。",
                        ),
                        WorkflowPlaybookStep(
                            command="创建通知",
                            title="发送任务通知",
                            description="把任务安排同步给班级或指定成员。",
                        ),
                    ],
                ),
                WorkflowPlaybook(
                    playbook_id="curriculum_setup",
                    name="课表初始化",
                    description="先录入课表，再设置当前周，确保查询结果可立即使用。",
                    steps=[
                        WorkflowPlaybookStep(
                            command="添加课表",
                            title="录入课表",
                            description="先把课程信息保存到系统中。",
                        ),
                        WorkflowPlaybookStep(
                            command="设置当前周",
                            title="设置当前周",
                            description="更新当前周后，查询课表时能直接得到正确结果。",
                        ),
                    ],
                ),
                WorkflowPlaybook(
                    playbook_id="join_request_review",
                    name="入班申请处理",
                    description="先查看申请列表，再逐条处理入班申请。",
                    steps=[
                        WorkflowPlaybookStep(
                            command="查询入班申请",
                            title="查看入班申请",
                            description="先拿到待处理的申请列表。",
                        ),
                        WorkflowPlaybookStep(
                            command="处理入班申请",
                            title="处理入班申请",
                            description="基于前一步结果批准或拒绝申请。",
                        ),
                    ],
                ),
            ]
        )

    def match_commands(self, commands: list[str]) -> WorkflowPlaybook | None:
        """按命令顺序匹配最合适的模板。"""

        candidates = [playbook for playbook in self.playbooks if playbook.matches(commands)]
        if not candidates:
            return None

        return sorted(
            candidates,
            key=lambda playbook: (
                len(playbook.steps) != len(commands),
                len(playbook.steps) - len(commands),
            ),
        )[0]


playbook_catalog = WorkflowPlaybookCatalog.default()
