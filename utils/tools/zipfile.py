from pathlib import Path
from typing import List
from zipfile import ZipFile

temp_zip_files: List[Path] = []


async def delete_temp_zip_files():
    for file in temp_zip_files.copy():
        file.unlink(True)
        temp_zip_files.remove(file)


class TempZipFile(ZipFile):
    def __init__(self, file: Path, *args, **kwargs):
        super().__init__(file, *args, **kwargs)
        temp_zip_files.append(file)

