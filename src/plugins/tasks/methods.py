from pathlib import Path
from asyncio import sleep
from zipfile import ZIP_DEFLATED, ZipFile
from typing import Dict, List, Tuple, Union, Optional

from utils.auth import User
from utils.localstore import LocalStore
from django.db.models.functions import Now
from utils.typings import BaseAuth, SaveFile
from utils.tools import run_sync, html_to_image
from django.db.models.manager import BaseManager
from utils.orm import Student, Teacher, TaskFiles, ClassTable, ClassTasks

from .config import TaskFinder, env

local_store = LocalStore("task_file")


class BaseTask(BaseAuth):
    _tasks: Optional[BaseManager[ClassTasks]] = None

    def __init__(self, user: User) -> None:
        super().__init__(user)
        self._class_size: Dict[ClassTable, int] = {}

    async def exists(self) -> bool:
        """检查用户是否存在任务

        Returns:
            bool: 是否存在
        """
        return await self.tasks.aexists()

    async def task_exists(
        self, title: str, class_table: Optional[ClassTable] = None
    ) -> bool:
        """检查该任务是否在班级中重复

        Args:
            title (str): 任务标题
            class_table (ClassTable): 班级

        Returns:
            bool: 是否存在
        """
        if self.is_student:
            return await self.tasks.filter(
                title=title,
            ).aexists()
        return await ClassTasks.objects.filter(
            class_table=class_table,
            title=title,
        ).aexists()

    @property
    def tasks(self) -> BaseManager[ClassTasks]:
        """获取教师或学生所在班级的所有任务，避免任务冲突

        Returns:
            BaseManager[ClassTasks]: 任务列表
        """
        if self._tasks is None:
            if isinstance(self.user, Teacher):
                self._tasks = ClassTasks.objects.filter(
                    class_table__in=self.teacher_class
                )
            else:
                self._tasks = ClassTasks.objects.filter(
                    class_table=self.user.class_table
                )
        return self._tasks

    async def tasks_to_image(self, msg: Optional[str] = None) -> bytes:
        """将任务列表以图片的方式展示出来

        Args:
            msg (Optional[str], optional): 标题. Defaults to None.

        Returns:
            bytes: 图片数据
        """
        template = env.get_template("tasklist.html")
        tasks = [i async for i in self.tasks]
        tasks_size = [
            await TaskFiles.objects.filter(task=task).acount() for task in tasks
        ]  # 获取任务提交数量
        return await html_to_image(
            await template.render_async(
                zip=zip,
                msg=msg,
                tasks=tasks,
                class_size=self.class_size,
                tasks_size=tasks_size,
            )
        )

    def class_size(self, class_table: ClassTable) -> int:
        """获取班级学生数量

        Args:
            class_table (ClassTable): 班级

        Returns:
            int: 数量
        """
        if size := self._class_size.get(class_table):
            return size
        else:
            self._class_size[class_table] = Student.objects.filter(
                class_table=class_table
            ).count()
            return self._class_size[class_table]

    def query_task(self, title: Union[str, TaskFinder]) -> BaseManager[ClassTasks]:
        """查询自己的task

        Args:
            title (str): task标题

        Returns:
            BaseManager[ClassTasks]: task
        """
        if isinstance(title, TaskFinder):
            return self.tasks.filter(title.to_Q())
        return self.tasks.filter(**{"task_id" if title.isdigit() else "title": title})

    def check_task_name(self, title: str) -> Optional[str]:
        """检查任务名返回相应警告

        Args:
            title (str): 任务名称

        Returns:
            Optional[str]: 如果是 None 表示没有问题，如果是str表示有警告
        """
        if not title:
            return "标题不能为空"
        elif title.isdigit():
            return "不能是纯数字"
        elif " " in title:
            return "不能包含空格"

    def split_title(self, title: str) -> List[str]:
        """切割任务名
        在AddTask中对任务名的检查已经不允许任务名中添加空格
        以便切割任务名的时候使用

        Args:
            title (str): 任务名

        Returns:
            List[str]: 多个任务名
        """
        return title.split()


class AddTask(BaseTask):
    async def add_task(self, title: str, class_table: ClassTable):
        title = title.strip()
        if not await self.task_exists(title, class_table):
            return await ClassTasks.objects.acreate(
                title=title,
                type="image",
                class_table=class_table,
                initiate=self.user.qq,
                create_time=Now(),
            )


class ShowTask(BaseTask):
    async def show_task(self, task_title_or_id: str):
        task_title_or_id = task_title_or_id.strip()
        if task := await self.query_task(task_title_or_id).afirst():
            task_collects = TaskFiles.objects.filter(task=task)
            yield await self.committed(task_collects)
            await sleep(1)
            yield await self.uncommitt(task.class_table, task_collects)
        else:
            yield "没有这个任务哎！"

    async def committed(self, task_collects: BaseManager[TaskFiles]) -> str:
        """已经提交的学生

        Args:
            task_collects (BaseManager[TaskFiles]): 已提交任务

        Returns:
            str: 回复消息
        """
        if await task_collects.aexists():
            return "已提交\n" + (
                "\n".join(
                    [f"{v.student.name} | {v.push_time}" async for v in task_collects]
                )
            )
        return "还没人提交过呢"

    async def uncommitt(
        self,
        class_table: ClassTable,
        task_collects: BaseManager[TaskFiles],
    ) -> str:
        """未提交人的姓名

        Args:
            task (ClassTable): 班级
            task_collects (BaseManager[TaskFiles]): 已提交任务

        Returns:
            str: 回复消息
        """
        uncommitt = Student.objects.filter(class_table=class_table).exclude(
            pk__in=[i.student async for i in task_collects]
        )
        if await uncommitt.aexists():
            return "未提交\n" + (
                " ".join([i["name"] async for i in uncommitt.values("name")])
            )
        return "都提交了💯"


class DelTask(BaseTask):
    async def del_task(self, title: str) -> bool:
        title = title.strip()
        delete_ok = False
        if task_finder := TaskFinder(title):
            async for task in self.query_task(task_finder):
                await self.delete_task_files(task)
                task.delete()
                delete_ok = True
        return delete_ok

    async def delete_task_files(self, task: ClassTasks):
        task_store = local_store.mkdir(str(task.class_table.group_id))
        async for collect in TaskFiles.objects.filter(task=task).values("file"):
            file_path = task_store.joinpath(collect["file"])
            if file_path.exists():
                file_path.unlink(True)


class PushTask(BaseTask):
    user: Student

    def __init__(self, user: User) -> None:
        super().__init__(user)
        self.save_file = SaveFile()

    async def task_file_exists(self, file: str) -> bool:
        """任务文件是否存在"""
        return await TaskFiles.objects.filter(file=file).aexists()

    async def push_task(self, title: str) -> str:
        title = title.strip()
        if task := await self.query_task(title).afirst():
            file = self.save_file.files[0]
            if not await self.task_file_exists(file):  # 检查文件是否重复
                reply = "OK"
                self.save_file.local_store = local_store.mkdir(
                    str(self.user.class_table.group_id)
                )
                if task_collect := await TaskFiles.objects.filter(
                    task=task, qq=self.user.qq
                ).afirst():
                    self.save_file.local_store.remove(task_collect.file_md5)  # 删除原本文件
                    task_collect.file_md5 = file
                    task_collect.save()
                    reply = "文件修改成功！"
                else:
                    await TaskFiles.objects.acreate(
                        title=task.title,
                        task=task,
                        qq=self.user.qq,
                        user_name=self.user.name,
                        class_table=self.user.class_table,  # type: ignore
                        file=file,
                        push_time=Now(),
                    )
                await self.save_file.save()
                return reply
            else:
                return "你的文件和别人的重复了哦！"
        else:
            return "任务不存在！"


class ExportTask(BaseTask):
    def __init__(self, user: User) -> None:
        super().__init__(user)
        self.zip_files: List[Tuple[Path, str]] = []

    async def export_task(self, title: str):
        title = title.strip()
        for i in self.split_title(title):
            if task := await self.query_task(i).afirst():
                task_store = local_store.mkdir(str(task.class_table.group_id))
                zip_name = task.title + ".zip"
                zip_path = task_store.joinpath(zip_name)
                with ZipFile(zip_path, "w", ZIP_DEFLATED) as file:
                    async for collect in TaskFiles.objects.filter(task=task):
                        file.write(
                            task_store.joinpath(collect.file_md5),
                            f"{collect.student.name}{collect.student.qq}.jpg",
                        )
                self.zip_files.append((zip_path, zip_name))
                yield zip_path, zip_name

    async def delete_zip_file(self, filepath: Path):
        """清理掉压缩文件

        Args:
            filepath (Path): 文件路径
        """
        try:
            await run_sync(filepath.unlink)(True)
        except PermissionError:
            ...


class ClearTask(BaseTask):
    async def clear_task(self, class_table: ClassTable) -> bool:
        clear_ok = True
        await self.tasks.filter(class_table=class_table).adelete()
        task_store = local_store[str(class_table.group_id)]
        if task_store.exists():
            for file in task_store.listdir():
                try:
                    await run_sync(file.unlink)()
                except PermissionError:
                    clear_ok = False
        return clear_ok
