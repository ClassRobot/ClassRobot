from utils.typings import UserType

from .typings import Helper, HelperCategory


class HelperMenu:
    def __init__(self) -> None:
        self.category: dict[str, HelperCategory] = {}
        self.commands: dict[str, Helper] = {}
        self.aliases: dict[str, Helper] = {}

    def get(self, target: str) -> Helper | HelperCategory | None:
        """获取帮助信息"""
        if help_info := (self.commands.get(target) or self.aliases.get(target)):
            return help_info
        elif help_category := self.category.get(target):
            return help_category
        return None

    def add(self, help_info: Helper):
        """添加帮助信息"""
        for i in help_info.category:
            self.category.setdefault(i, HelperCategory(category=i)).add(help_info)
        self._add_command(help_info.command, help_info)
        for i in help_info.aliases:
            self._add_aliases(i, help_info)

    def _add_command(self, key: str, value: Helper) -> bool:
        """添加命令"""
        if key not in self.commands:
            self.commands[key] = value
            return True
        return False

    def _add_aliases(self, key: str, value: Helper):
        """添加命令别名"""
        if key not in self.aliases:
            self.aliases[key] = value
            return True
        return False

    def to_string(self):
        return "命令菜单：\n" + "\n".join(
            f"- `{i.command}` | {i.description}" for i in self.commands.values()
        )
