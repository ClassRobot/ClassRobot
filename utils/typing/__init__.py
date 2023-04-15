from typing import List, Optional, Tuple, Union, overload
from django.db.models.manager import BaseManager
from httpx import AsyncClient
from nonebot.adapters.onebot.v11 import Message

from ..localstore import LocalStore
from ..orm import Teacher, StudentInfo, ClassTable, StudentUnion
from ..manages import User
from ..manages.config import ClassCadre


class BaseAuth:
    _class_count: Optional[int] = None
    _start_index = 0
    _teacher_class: Optional[BaseManager[ClassTable]] = None
    class_cader_list = ClassCadre.to_list()

    def __init__(self, user: User) -> None:
        self.user: User = user
    
    @property
    def is_cader(self) -> bool:
        """是否为班干部

        Returns:
            bool: True or False
        """
        if isinstance(self.user, StudentInfo):
            return self.user.position in self.class_cader_list
        return False

    @property
    def is_cader_or_teacher(self) -> bool:
        """是否为班干部或教师

        Returns:
            bool: True or False
        """
        if isinstance(self.user, StudentInfo):
            return self.user.position in self.class_cader_list
        return True

    async def is_union(self) -> bool:
        """是否为学生会干部"""
        return await StudentUnion.objects.filter(pk=self.user.qq).aexists()

    @property
    def is_teacher(self) -> bool:
        return isinstance(self.user, Teacher)

    @property
    def is_student(self) -> bool:
        return isinstance(self.user, StudentInfo)

    @property
    def teacher_class(self) -> BaseManager[ClassTable]:
        if self._teacher_class is None:
            self._teacher_class = ClassTable.objects.filter(teacher=self.user)
        return self._teacher_class
    
    @overload
    async def teacher_class_names(
        self, 
        join_str: None, 
        index: bool =True, 
        start: int = 0
    )-> List[str]: ...
    @overload
    async def teacher_class_names(
        self, 
        join_str: str = "\n", 
        index: bool =True, 
        start: int = 0
    )-> str: ...
    async def teacher_class_names(
        self, 
        join_str: Optional[str] ="\n", 
        index: bool =True, 
        start: int = 0
    ) -> Union[List[str], str]:
        """教师所管理班级的名字

        Args:
            join_str (Optional[str], optional): join的字符. Defaults to "\n".
            index (bool, optional): 是否需要索引. Defaults to True.
            start (int, optional): 索引的起始数. Defaults to 0.

        Returns:
            Union[List[str], str]: 当join_str为None时返回List[str]
        """
        self._start_index = start
        names = [i["class_name"] async for i in self.teacher_class.values("class_name")]
        if join_str is not None:
            if index:
                return join_str.join(f"{i}.{v}" for i, v in enumerate(names, start=start))
            return join_str.join(names)
        return names

    async def teacher_class_count(self) -> int:
        if self._class_count is None:
            self._class_count = await self.teacher_class.acount()
        return self._class_count

    async def select_class(
        self, 
        class_name: str, 
        start: Optional[int] = None
    ) -> Optional[ClassTable]:
        """教师选择需要的班级

        Args:
            class_name (str): 班级名称或索引
            start (int): 索引查找时索引的起始

        Returns:
            Optional[ClassTable]: 班级信息
        """
        if class_name:
            if class_name.isdigit():
                try:
                    return self.teacher_class[
                        int(class_name) - (self._start_index if start is None else start)
                    ]
                except IndexError:
                    return
            elif class_table := await self.teacher_class.filter(class_name=class_name).afirst():
                return class_table


class SaveFile:
    _files: Optional[List[str]] = None
    _urls: Optional[List[str]] = None
    local_store: LocalStore = LocalStore("temp")
    duplicate_number: int = 0   # 文件重复次数

    @property
    def file_exists(self) -> bool:
        return bool(self.files)

    @property
    def files(self) -> List[str]:
        if self._files is None:
            self._files = []
        return self._files

    @property
    def urls(self) -> List[str]:
        if self._urls is None:
            self._urls = []
        return self._urls
    
    def file_duplicate(self, file: str) -> bool:
        """文件是否重复

        Args:
            file (str): 文件名

        Returns:
            bool: 是否重复
        """
        return file in self.files

    def add_file(self, message: Message) -> bool:
        """向添加的任务添加文件
            如果是重复文件会被过滤掉，并且被记录一次重复

        Args:
            message (Message): 消息内容
        """
        _append = False # 是否有添加文件
        for msg in message.get("image"):
            _append = True
            file = msg.data['file'].split(".")[0]
            if not self.file_duplicate(file):
                self.files.append(file)
                self.urls.append(msg.data["url"])
            else:
                self.duplicate_number += 1
        return _append

    @property
    def first_file(self) -> Tuple[str, str]:
        return self.files[0], self.urls[0]

    async def save(self, all_file=False):
        """保存文件
            会对url里的文件进行下载，然后保存

        Args:
            all_file (bool, optional): 是否保存全部文件. Defaults to False.
        """
        if self.files:
            self.local_store.mkdir()
            async with AsyncClient() as client:
                if all_file:
                    for file, url in zip(self.files, self.urls):
                        self.local_store.joinpath(file).write_bytes(
                            (await client.get(url)).read()
                        )
                else:
                    file, url = self.first_file
                    self.local_store.joinpath(file).write_bytes(
                        (await client.get(url)).read()
                    )


__all__ = [
    "BaseAuth"
]
