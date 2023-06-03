from pathlib import Path
from nonebot import get_driver
from anyio import open_file
from shutil import rmtree
from typing import Union, Optional, Generator

StrPath = Union[str, Path]
driver = get_driver()
default_path = Path(
    Path.cwd().parent, driver.config.dict().get("localstore", "")
).resolve()
remove_error_files = Path(__file__).parent / "localstore_remove_error_files.txt"


class LocalStore:
    init_path: Path = default_path

    def __repr__(self) -> str:
        return str(self.store_path)

    def __str__(self) -> str:
        return str(self.store_path)

    def __init__(self, *args: StrPath, new_path: Optional[Path] = None, is_mkdir=False):
        self.store_path: Path = (
            self.init_path.joinpath(*args) if new_path is None else new_path
        )
        if is_mkdir:
            self.mkdir(parents=True, exist_ok=True)

    def join(self, *args: StrPath) -> "LocalStore":
        return LocalStore(new_path=self.store_path.joinpath(*args))

    def joinpath(self, *other: StrPath) -> Path:
        return self.store_path.joinpath(*other)

    def mkdir(self, *args: StrPath, parents=True, exist_ok=True) -> "LocalStore":
        store = self.join(*args)
        store.store_path.mkdir(parents=parents, exist_ok=exist_ok)
        return store

    # 切换路径
    def truediv(self, path: Union[str, Path]) -> "LocalStore":
        return LocalStore(new_path=self.joinpath(path))

    def __getitem__(self, other: Union[str, Path]) -> "LocalStore":
        return self.truediv(other)

    def __truediv__(self, other: Union[str, Path]) -> "LocalStore":
        return self.truediv(other)

    # 读写
    def read_text(self, *args: StrPath, encoding: Optional[str] = None) -> str:
        return self.joinpath(*args).read_text(encoding=encoding)

    def read_bytes(self, *args: StrPath) -> bytes:
        return self.joinpath(*args).read_bytes()

    def write_text(self, *args: StrPath, data: str, encoding: Optional[str] = None):
        self.joinpath(*args).write_text(data, encoding=encoding)

    def write_bytes(self, *args: StrPath, data: bytes):
        self.joinpath(*args).write_bytes(data)

    async def aread_text(self, *args: StrPath, encoding: Optional[str] = None) -> str:
        file = await open_file(self.joinpath(*args), "r", encoding=encoding)
        return await file.read()

    def remove(self, *args: StrPath) -> bool:
        """
        删除文件
        :param args: 文件路径
        :return: 返回是否删除成功
        """
        try:
            self.joinpath(*args).unlink(True)
            return True
        except FileNotFoundError:
            return False
        except Exception as err:
            with open(remove_error_files, "a", encoding="utf-8", newline="\n") as file:
                file.write(str(self.store_path))
            raise err

    def rmdir(self, *args: StrPath, tree: bool = False) -> bool:
        _dir = self.joinpath(*args)
        if _dir.exists():
            if tree:
                rmtree(_dir)
            else:
                _dir.rmdir()
            return True
        return False

    def listdir(self, *args: StrPath) -> Generator[Path, None, None]:
        """列出文件列表"""
        return self.joinpath(*args).iterdir()

    def exists(self, *args: StrPath) -> bool:
        return self.joinpath(*args).exists()
