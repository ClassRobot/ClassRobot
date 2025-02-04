from typing import Annotated

from nonebot.params import Depends
from utils.tools import StringCard
from nonebot.matcher import Matcher
from utils.models import User, Tasks, Student
from utils.models.annotated import UserDepends


class TaskList(list[Tasks]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def to_card(self, title: str | None = None):
        card = StringCard(title)
        for task in self:
            creator = task.creator
            if task.creator_role == "student":
                nickname = creator.student.name
            elif task.creator_role == "teacher":
                nickname = creator.teacher.name
            else:
                nickname = creator.nickname
            (
                card.hr()
                .text("任务ID:", str(task.id))
                .text("任务名称:", task.name)
                .text("创建用户:", nickname)
                .text("所属班级:", task.classes.name)
                .text("创建日期:", task.created_at.strftime("%Y-%m-%d"))
                .text(
                    "已提交数:",
                    f"{len(await task.get_commits())}/{len(await task.classes.get_students())}",
                )
            )
        return card.render()


class TaskManager:
    """任务管理器

    任务分两种，可以提交任务于不可提交任务

    学生身份下的班级任务可以提交，教师身份下的班级任务不可提交
    """

    def __init__(self, user: User):
        self.user: User = user
        self.select_name: str | None = None  # 选择的任务名称
        self._select_task: Tasks | None = None
        self.submit_tasks: TaskList = TaskList()  # 可提交任务
        self.not_submit_tasks: TaskList = TaskList()  # 不可提交任务

    @property
    def select_task(self) -> Tasks:
        assert self._select_task, "未选择任务"
        return self._select_task

    @select_task.setter
    def select_task(self, task: Tasks | None):
        self._select_task = task

    @property
    def tasks(self) -> TaskList:
        return TaskList(dict.fromkeys(self.submit_tasks + self.not_submit_tasks))

    async def select(self, task_name: str) -> bool:
        self.select_name = task_name
        self.select_task = None
        if self.tasks:
            # 如果已经填入了任务，则在任务列表中查找
            for task in self.tasks:
                if task_name.isdigit() and task.id == int(task_name):
                    self.select_task = task
                elif task.name == task_name:
                    self.select_task = task
                if self.select_task:
                    return True
        else:
            # 如果没有任务列表，则在数据库中查找
            task_name_or_id = int(task_name) if task_name.isdigit() else task_name
            if self.user.student:
                if select_task := await self.user.student.classes.get_task(
                    task_name_or_id
                ):
                    self.select_task = select_task
                    return True
            if self.user.teacher:
                for classes in self.user.teacher.classes:
                    if select_task := await classes.get_task(task_name_or_id):
                        self.select_task = select_task
                        return True
        return False

    @property
    def is_select(self) -> bool:
        """是否选择了任务"""
        return self._select_task is not None

    async def commits(
        self, task: Tasks | None = None
    ) -> tuple[tuple[Student, ...], tuple[Student, ...]]:
        """r任务已提交和未提交的学生

        Args:
            task_id (int | str): 任务ID或任务名称

        Returns:
            tuple[tuple[Student, ...], tuple[Student, ...]]: 已提交, 未提交
        """
        task = task or self.select_task
        students = tuple(await task.classes.get_students())
        if not students:  # 如果没有学生则直接返回
            return tuple(), tuple()
        submitted = tuple(commit.student for commit in await task.get_commits())
        submitted_names = tuple(student.name for student in submitted)
        not_submitted = tuple(
            student for student in students if student.name not in submitted_names
        )
        return submitted, not_submitted

    async def delete(self, task: Tasks | None = None):
        """删除任务"""
        task = task or self.select_task
        return await task.delete()

    def __bool__(self) -> bool:
        return any((self.submit_tasks, self.not_submit_tasks))


async def task_manager_depends(
    matcher: Matcher, task_name: str | None, user: UserDepends
) -> TaskManager | None:
    if task_manager := matcher.state.get("_task_manager"):
        return task_manager
    if user is None or (not user.student and not user.teacher):
        await matcher.finish()

    task_manager = TaskManager(user)
    # 当没有填写任务名时，返回所有任务
    if task_name is None:
        if user.student:
            task_manager.submit_tasks.extend(await user.student.classes.get_tasks())
        if user.teacher:
            for classes in user.teacher.classes:
                task_manager.not_submit_tasks.extend(await classes.get_tasks())
        return task_manager
    return task_manager


TaskManagerDepends = Annotated[TaskManager, Depends(task_manager_depends)]
