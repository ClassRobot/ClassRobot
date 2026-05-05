from __future__ import annotations

from collections.abc import Iterator

from nonebot import logger

from .spec import CommandSpec


class CommandRegistry:
    """维护进程内命令注册表。

    注册表为帮助菜单、Agent 工具目录和管理端命令清单提供统一索引。
    它不负责执行命令，只保存稳定的命令元数据。
    """

    def __init__(self) -> None:
        """初始化空命令注册表。"""

        self._specs: list[CommandSpec] = []
        self._index: dict[str, CommandSpec] = {}

    def clear(self) -> None:
        """清空全部已注册命令。

        该方法主要用于测试或重新加载命令元数据。
        """

        self._specs.clear()
        self._index.clear()

    def register(self, spec: CommandSpec) -> CommandSpec:
        """注册命令元数据并建立命令名索引。

        Args:
            spec: 待注册的命令元数据。

        Returns:
            CommandSpec: 实际生效的命令元数据；若已存在同名命令，则返回旧对象。
        """

        current = self._index.get(spec.name)
        if current is spec:
            return spec
        if current is not None:
            logger.warning("命令元数据 {} 已经注册，保留现有定义", spec.name)
            return current

        self._specs.append(spec)
        for command_name in spec.commands:
            if command_name in self._index:
                logger.warning("命令名称 {} 已经注册，跳过该别名绑定", command_name)
                continue
            self._index[command_name] = spec
        return spec

    def get(self, command_name: str) -> CommandSpec | None:
        """按主命令或别名查询命令元数据。

        Args:
            command_name: 主命令名称或别名。

        Returns:
            CommandSpec | None: 命中时返回命令元数据，否则返回 ``None``。
        """

        return self._index.get(command_name.strip())

    def by_plugin(self, plugin_module: str) -> list[CommandSpec]:
        """查询指定插件模块下的命令。

        Args:
            plugin_module: 插件模块路径。

        Returns:
            list[CommandSpec]: 归属于该插件模块的命令列表。
        """

        return [spec for spec in self._specs if spec.plugin_module == plugin_module]

    def __iter__(self) -> Iterator[CommandSpec]:
        """按注册顺序迭代命令元数据。"""

        yield from self._specs

    def __len__(self) -> int:
        """返回已注册命令数量。"""

        return len(self._specs)


command_registry = CommandRegistry()
