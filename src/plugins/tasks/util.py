import shutil
from hashlib import md5
from pathlib import Path
from typing import Literal, Annotated

from pydantic import BaseModel
from utils.tools import StringCard
from nonebot.matcher import Matcher
from nonebot.adapters import Message
from nonebot.params import Arg, Depends
from nonebot.adapters import Bot as BaseBot
from utils.models.annotated import UserDepends
from utils.config import cache_dir, global_config
from nonebot_plugin_htmlrender import get_new_page
from nonebot.adapters.onebot.v11 import Bot as V11Bot
from utils.models import User, Tasks, Student, TaskCommits
from nonebot_plugin_alconna import File, Image, Other, UniMessage

TaskFile = File | Image | Other


class FileData(BaseModel):
    name: str
    data: bytes | None = None
    path: Path | None = None

    def save_data(self, file_path: Path, new: bool = True):
        """保存数据，将数据迁移或者保存到指定文件"""
        if self.data is None and self.path is None:
            raise ValueError("data and path cannot be None at the same time")

        if self.path and self.path != file_path:
            shutil.move(self.path, file_path)
            self.path = file_path if new else self.path
        elif self.data:
            file_path.write_bytes(self.data)
            self.path = file_path if new else self.path

    def get_data(self) -> bytes:
        """获取数据，如果data为None就从path中读取"""
        if self.path is None and self.data is None:
            raise ValueError("data and path cannot be None at the same time")

        if self.data is None:
            self.data = self.path.read_bytes()  # type: ignore
        return self.data

    def __bool__(self) -> bool:
        return bool(self.data or self.path)


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

    async def check_file_exists(self, file_md5: str | bytes) -> bool:
        if isinstance(file_md5, bytes):
            # 文件校验
            file_md5 = md5(file_md5).hexdigest()
        return await TaskCommits.filter(file_md5=file_md5).exists()

    async def download_file(self, url: str) -> bytes:
        async with get_new_page() as page:
            response = await page.request.get(url)
            return await response.body()


class PushTaskManager(TaskManager):
    task_file: TaskFile | None = None

    def set_task_file(self, message: UniMessage | TaskFile | Message) -> bool:
        """设置提交的任务文件，只会拿第一次提交的文件

        Args:
            message (UniMessage | TaskFile): 用户消息

        Returns:
            bool: 是否提交成功
        """
        if self.task_file is not None:
            return True
        elif isinstance(message, TaskFile):
            self.task_file = message
            return True
        elif isinstance(message, Message):
            message = UniMessage.generate_sync(message=message)
        for file in message:
            if isinstance(file, TaskFile):
                self.task_file = file
                return True
        return False

    def task_file_url(self):
        if self.task_file is not None:
            if isinstance(self.task_file, File | Image):
                return self.task_file.url
            elif isinstance(self.task_file, Other):
                print(self.task_file.origin.data)


def task_manager_depends(
    role: Literal["student", "teacher"] | None = None,
    manager: type[TaskManager] | None = None,
):
    """任务管理器依赖

    Args:
        role (Literal[&quot;student&quot;, &quot;teacher&quot;] | None, optional): 角色. Defaults to None.
            只获取学生任务或教师任务
    """

    async def _(
        matcher: Matcher,
        user: UserDepends,
        task_name: str | None = None,
    ) -> TaskManager | None:
        if task_manager := matcher.state.get("_task_manager"):
            return task_manager

        # 既不是学生也不是教师
        if user is None or (not user.student and not user.teacher):
            await matcher.finish()

        task_manager = (manager or TaskManager)(user)
        # 当没有填写任务名时，返回所有任务
        if task_name is None:
            if (role is None or role == "student") and user.student:
                task_manager.submit_tasks.extend(await user.student.classes.get_tasks())
            if (role is None or role == "teacher") and user.teacher:
                for classes in user.teacher.classes:
                    task_manager.not_submit_tasks.extend(await classes.get_tasks())
        matcher.state["_task_manager"] = task_manager
        return task_manager

    return Depends(_)


async def get_file_data(
    bot: BaseBot,
    task_file: UniMessage = Arg(),
    task_manager: PushTaskManager = task_manager_depends("student", PushTaskManager),
) -> FileData | None:
    task_manager.set_task_file(task_file)
    if isinstance(task_manager.task_file, Other) and isinstance(bot, V11Bot):
        if task_manager.task_file.origin.type != "file":
            return None
        file_id: str = task_manager.task_file.origin.data["file_id"]
        res = await bot.get_file(file_id=file_id)
        file_id = file_id.replace("\\", "").replace("/", "")
        file_path = Path(res["file"])

        # 在wsl模式下将从共享目录中获取文件
        if global_config.wsl_share_dir and global_config.wsl_share_dir.exists():
            file_path = global_config.wsl_share_dir / file_path.name

        new_path = cache_dir / file_id
        shutil.move(file_path, new_path)
        file_path.unlink(True)
        return FileData(
            name=file_id,
            path=new_path,
        )
    elif (
        isinstance(task_manager.task_file, File | Image) and task_manager.task_file.url
    ):
        return FileData(
            name=task_manager.task_file.name,
            data=await task_manager.download_file(task_manager.task_file.url),
        )


TaskManagerDepends = Annotated[TaskManager, task_manager_depends()]
FileDataDepends = Annotated[FileData | None, Depends(get_file_data)]
