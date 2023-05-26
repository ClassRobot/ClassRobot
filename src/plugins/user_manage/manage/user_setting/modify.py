from typing import Dict, List, Optional
from utils.manages import User
from utils.tools import run_sync
from utils.orm import Teacher, StudentInfo

from .config import ModifiableColumns


class ModifyUserInfo:
    def __init__(self, user: User):
        self.user = user
        self.is_teacher = isinstance(user, Teacher)
        self.is_student = isinstance(user, StudentInfo)
        if self.is_teacher:
            self.keys = ModifiableColumns.teacher.copy()
        elif self.is_student:
            self.keys = ModifiableColumns.student.copy()
        else:
            self.keys = {}

    async def save(self):
        await run_sync(self.user.save)()

    def not_exist_fields(self, keys: List[str]) -> List[str]:
        """查看表中是否存在这个字段

        Args:
            keys (List[str]): 字段列表

        Returns:
            List[str]: 不存在的字段
        """
        return [key for key in keys if key not in self.keys]

    def modify(self, keys: List[str], values: List[str]) -> Optional[Dict[str, list]]:
        """修改字段内容

        Args:
            keys (List[str]): 需要修改的keys(字段的中文)
            values (List[str]): 字段的值

        Returns:
            Optional[Dict[str, list]]: 修改后的字段
                {
                    字段名: [修改前, 修改后]
                }
        """
        if self.keys:
            update_fields: Dict[str, list] = {}
            for key, value in zip(keys, values):
                if field := self.keys.get(key):  # 获取字段名
                    raw = getattr(self.user, field)
                    value = int(value) if isinstance(raw, int) else value
                    if raw != value:  # 修改数据与原本数据不相同
                        update_fields[key] = [raw, value]
                        setattr(self.user, field, value)
            return update_fields
