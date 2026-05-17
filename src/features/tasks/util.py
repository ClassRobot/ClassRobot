import shutil
from hashlib import md5
from pathlib import Path
from zipfile import ZipFile
from typing import List, Literal, Annotated

from pydantic import BaseModel
from nonebot.matcher import Matcher
from nonebot.adapters import Message
from utils.tools.sync import run_sync
from nonebot.params import Arg, Depends
from utils.tools.cos import upload_file
from nonebot.adapters import Bot as BaseBot
from utils.models.depends import UserDepends
from utils.tools import StringCard, download_file
from utils.models import User, Files, Tasks, Student
from nonebot.adapters.onebot.v11 import Bot as V11Bot
from utils.config import task_dir, cache_dir, global_config
from nonebot_plugin_alconna import File, Image, Other, UniMessage

TaskFile = File | Image | Other


class FileData(BaseModel):
    """封装任务附件的字节数据与本地路径，并提供读写能力。"""
    name: str
    data: bytes | None = None
    path: Path | None = None

    def save_data(self, file_path: Path, new: bool = True):
        """保存数据，将数据迁移或者保存到指定文件

        参数:
            file_path (Path): 文件路径。
            new (bool): new。
        """
        if self.data is None and self.path is None:
            raise ValueError("data and path cannot be None at the same time")

        if self.path and self.path != file_path:
            shutil.move(self.path, file_path)
            self.path = file_path if new else self.path
        elif self.data:
            file_path.write_bytes(self.data)
            self.path = file_path if new else self.path

    def get_data(self) -> bytes:
        """获取data。"""
        if self.path is None and self.data is None:
            raise ValueError("data and path cannot be None at the same time")

        if self.data is None:
            self.data = self.path.read_bytes()  # type: ignore
        return self.data

    def __bool__(self) -> bool:
        """返回布尔值。"""
        return bool(self.data or self.path)


class QueryTasks:
    """按当前用户身份汇总并查询可访问的任务。"""
    def __init__(self, user: User):
        """初始化实例。

        参数:
            user (User): 当前用户对象。
        """
        self.user = user
        self._student_tasks: list[Tasks] = []
        self._teacher_tasks: list[Tasks] = []

    async def get_student_tasks(self) -> List[Tasks]:
        """获取学生任务。"""
        if self._student_tasks:
            return self._student_tasks

        if self.user.student:
            return await self.user.student.classes.get_tasks()
        return self._student_tasks

    async def get_teacher_tasks(self) -> List[Tasks]:
        """获取教师任务。"""
        if self._teacher_tasks:
            return self._teacher_tasks

        if self.user.teacher:
            for classes in self.user.teacher.classes:
                self._teacher_tasks.extend(await classes.get_tasks())
        return self._teacher_tasks

    async def get_student_task(self, task_id: int | str) -> Tasks | None:
        """获取学生任务。

        参数:
            task_id (int | str): 任务标识。

        返回:
            Tasks | None: 返回处理结果。
        """
        for task in await self.get_student_tasks():
            if isinstance(task_id, int) and task.id == task_id:
                return task
            elif isinstance(task_id, str) and task.name == task_id:
                return task

    async def get_teacher_task(self, task_id: int | str) -> list[Tasks]:
        """或许教师相关班级任务(以为多个班级可能存在重复任务)

        参数:
            task_id (int | str): 任务标识。

        返回:
            list[Tasks]: 返回处理结果。
        """
        tasks = []
        for task in await self.get_teacher_tasks():
            if isinstance(task_id, int) and task.id == task_id:
                tasks.append(task)
            elif isinstance(task_id, str) and task.name == task_id:
                tasks.append(task)
        return tasks


class PushTaskCommit(QueryTasks):
    """定义任务提交流程的抽象基类。"""
    async def task_commit(self, task: Tasks):
        """提交任务记录。

        参数:
            task (Tasks): 任务对象。
        """
        ...


class TaskList(list[Tasks]):
    """表示任务集合，并提供卡片渲染等展示能力。"""
    def __init__(self, *args, **kwargs):
        """初始化实例。

        参数:
            args (*Any): 可变位置参数。
            kwargs (**Any): 可变关键字参数。
        """
        super().__init__(*args, **kwargs)

    async def to_card(self, title: str | None = None):
        """渲染为卡片内容。

        参数:
            title (str | None): title。
        """
        card = StringCard(title)
        for task in self:
            creator = task.creator
            if creator.student:
                nickname = creator.student.name
            elif creator.teacher:
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
        """初始化实例。

        参数:
            user (User): 当前用户对象。
        """
        self.user: User = user
        self.select_name: str | None = None  # 选择的任务名称
        self._select_task: Tasks | None = None
        self.submit_tasks: TaskList = TaskList()  # 可提交任务
        self.not_submit_tasks: TaskList = TaskList()  # 不可提交任务

    @property
    def select_task(self) -> Tasks:
        """选择任务。"""
        assert self._select_task, "未选择任务"
        return self._select_task

    @select_task.setter
    def select_task(self, task: Tasks | None):
        """选择任务。

        参数:
            task (Tasks | None): 任务对象。
        """
        self._select_task = task

    @property
    def tasks(self) -> TaskList:
        """返回当前用户可见的全部任务集合。"""
        tasks: dict[int, Tasks] = {}
        for task in self.submit_tasks + self.not_submit_tasks:
            tasks[task.id] = task
        return TaskList(tasks.values())

    async def select(self, task_name: str) -> bool:
        """选择当前数据。

        参数:
            task_name (str): 任务名称。

        返回:
            bool: 表示是否成功。
        """
        self.select_name = task_name
        self.select_task = None
        if self.tasks:
            # Prefer the in-memory snapshot gathered earlier in the matcher lifecycle;
            # only fall back to database lookups when no task list was preloaded.
            # 如果已经填入了任务，则在任务列表中查找
            for task in self.tasks:
                if task_name.isdigit() and task.id == int(task_name):
                    self.select_task = task
                elif task.name == task_name:
                    self.select_task = task
                if self._select_task:
                    return True
        else:
            # 如果没有任务列表，则在数据库中查找
            task_name_or_id = int(task_name) if task_name.isdigit() else task_name
            if self.user.student:
                if select_task := await self.user.student.classes.get_task(task_name_or_id):
                    self.select_task = select_task
                    return True
            if self.user.teacher:
                for classes in self.user.teacher.classes:
                    if select_task := await classes.get_task(task_name_or_id):
                        self.select_task = select_task
                        return True
        return False

    async def build_task(self) -> None | str:
        """构建任务。"""
        commits = await self.select_task.get_commits()
        if not commits:
            return None
        # Export writes a temporary zip to local storage, uploads it, then removes the
        # archive immediately so task exports do not accumulate on disk.
        zip_path = task_dir / f"{self.select_task.classes.name}-{self.select_task.name}.zip"
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(zip_path, "w") as zip_file:
            for commit in commits:
                await run_sync(zip_file.write)(
                    commit.file.path,
                    f"{self.select_task.classes.name}-{self.select_task.name}/{commit.student.name}-{commit.file.file_name}",
                )
        download_url = await upload_file(zip_path.read_bytes(), zip_path.name)
        zip_path.unlink(True)  # 上传完成后删除本地文件
        return download_url

    @property
    def is_select(self) -> bool:
        """是否选择了任务"""
        return self._select_task is not None

    async def commits(self, task: Tasks | None = None) -> tuple[tuple[Student, ...], tuple[Student, ...]]:
        """r任务已提交和未提交的学生

        参数:
            task_id (int | str): 任务ID或任务名称

        返回:
            tuple[tuple[Student, ...], tuple[Student, ...]]: 已提交, 未提交
        """
        task = task or self.select_task
        students = tuple(await task.classes.get_students())
        if not students:  # 如果没有学生则直接返回
            return tuple(), tuple()
        submitted = tuple(commit.student for commit in await task.get_commits())
        submitted_names = tuple(student.name for student in submitted)
        not_submitted = tuple(student for student in students if student.name not in submitted_names)
        return submitted, not_submitted

    async def delete(self, task: Tasks | None = None):
        """删除任务

        参数:
            task (Tasks | None): 任务对象。
        """
        task = task or self.select_task
        return await task.delete()

    def __bool__(self) -> bool:
        """返回布尔值。"""
        return any((self.submit_tasks, self.not_submit_tasks))

    async def check_file_exists(self, file_md5: str | bytes) -> bool:
        """检查文件是否已存在。

        参数:
            file_md5 (str | bytes): 文件MD5 值。

        返回:
            bool: 表示是否成功。
        """
        if isinstance(file_md5, bytes):
            # 文件校验
            file_md5 = md5(file_md5).hexdigest()
        return await Files.file_duplicate(file_md5)  # type: ignore


class PushTaskManager(TaskManager):
    """负责push任务manager的管理与调度。"""
    task_file: TaskFile | None = None

    def set_task_file(self, message: UniMessage | TaskFile | Message) -> bool:
        """设置提交的任务文件，只会拿第一次提交的文件

        参数:
            message (UniMessage | TaskFile): 用户消息

        返回:
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
        """返回任务附件上传后的访问链接。"""
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

    参数:
        role (Literal[&quot;student&quot;, &quot;teacher&quot;] | None, optional): 角色. Defaults to None.
            只获取学生任务或教师任务
    """

    async def _(
        matcher: Matcher,
        user: UserDepends,
        task_name: str | None = None,
    ) -> TaskManager | None:
        """构造任务管理器依赖并缓存到匹配器状态中。"""
        if task_manager := matcher.state.get("_task_manager"):
            return task_manager

        # 既不是学生也不是教师
        if user is None or (not user.student and not user.teacher):
            await matcher.finish()

        # Cache the manager on matcher.state so subsequent `.got()` handlers keep
        # working against the same task snapshot within one conversation.
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
    """获取文件data。"""
    task_manager.set_task_file(task_file)
    if isinstance(task_manager.task_file, Other) and isinstance(bot, V11Bot):
        if task_manager.task_file.origin.type != "file":
            return None
        file_id: str = task_manager.task_file.origin.data["file_id"]
        res = await bot.get_file(file_id=file_id)
        file_id = file_id.replace("\\", "").replace("/", "")
        file_path = Path(res["file"])

        # OneBot V11 reports uploaded files as local paths, so move them into our
        # cache dir first; in WSL mode that path must be resolved from the shared dir.
        if global_config.wsl_share_dir and global_config.wsl_share_dir.exists():
            file_path = global_config.wsl_share_dir / file_path.name

        new_path = cache_dir / file_id
        shutil.move(file_path, new_path)
        file_path.unlink(True)
        return FileData(
            name=file_id,
            path=new_path,
        )
    elif isinstance(task_manager.task_file, File | Image) and task_manager.task_file.url:
        return FileData(
            name=task_manager.task_file.name,
            data=await download_file(task_manager.task_file.url),
        )


TaskManagerDepends = Annotated[TaskManager, task_manager_depends()]
FileDataDepends = Annotated[FileData | None, Depends(get_file_data)]
