from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field
from utils.helper import Helper, Helpers

from .spec import CommandSpec


class AvailabilityState(BaseModel):
    """描述命令或插件的软关闭状态。"""

    enabled: bool = True
    reason: str = ""
    updated_at: datetime = Field(default_factory=datetime.now)


class AvailabilityDecision(BaseModel):
    """描述一次命令可用性检查结果。"""

    available: bool = True
    reason: str = ""


class CommandAvailabilityService:
    """管理项目命令和插件的进程内软开关。

    NoneBot 可以在启动时加载插件，但没有稳定公开的任意插件卸载 API。
    因此这里实现的是运行时软关闭：matcher 仍可能存在，但 help、
    Agent 工具目录和统一执行器都会把该命令视为不可用。
    """

    def __init__(self) -> None:
        """初始化命令和插件软开关状态表。"""

        self._commands: dict[str, AvailabilityState] = {}
        self._plugins: dict[str, AvailabilityState] = {}

    def clear(self) -> None:
        """重置全部软开关状态。

        该方法主要用于测试或重新加载管理端配置。
        """

        self._commands.clear()
        self._plugins.clear()

    def set_command_enabled(self, command: str, enabled: bool, reason: str = "") -> AvailabilityState:
        """设置单条命令的软开关状态。

        Args:
            command: 主命令名称或别名。
            enabled: 是否启用。
            reason: 关闭或调整状态的原因。

        Returns:
            AvailabilityState: 更新后的状态对象。
        """

        state = AvailabilityState(enabled=enabled, reason=reason, updated_at=datetime.now())
        self._commands[command.strip()] = state
        return state

    def set_plugin_enabled(self, plugin_module: str, enabled: bool, reason: str = "") -> AvailabilityState:
        """设置插件模块的软开关状态。

        Args:
            plugin_module: 插件模块路径或模块前缀。
            enabled: 是否启用。
            reason: 关闭或调整状态的原因。

        Returns:
            AvailabilityState: 更新后的状态对象。
        """

        state = AvailabilityState(enabled=enabled, reason=reason, updated_at=datetime.now())
        self._plugins[plugin_module.strip()] = state
        return state

    def command_state(self, command: str) -> AvailabilityState:
        """读取命令软开关状态。

        Args:
            command: 主命令名称或别名。

        Returns:
            AvailabilityState: 命令状态；未显式配置时默认启用。
        """

        return self._commands.get(command.strip(), AvailabilityState())

    def plugin_state(self, plugin_module: str | None) -> AvailabilityState:
        """读取插件模块最匹配的软开关状态。

        Args:
            plugin_module: 插件模块路径。

        Returns:
            AvailabilityState: 插件状态；未显式配置时默认启用。
        """

        if not plugin_module:
            return AvailabilityState()
        candidates = [
            state
            for module, state in self._plugins.items()
            if plugin_module == module or plugin_module.startswith(f"{module}.")
        ]
        return candidates[-1] if candidates else AvailabilityState()

    def check(self, spec: CommandSpec | None, command: str | None = None) -> AvailabilityDecision:
        """检查命令当前是否可用。

        Args:
            spec: 新命令体系中的命令元数据；旧命令可传 ``None``。
            command: 旧命令名称或需要显式检查的命令名。

        Returns:
            AvailabilityDecision: 可用性检查结果。
        """

        command_name = command or (spec.name if spec else "")
        if spec and spec.execution_mode == "disabled":
            return AvailabilityDecision(available=False, reason="命令执行模式已禁用")

        command_names = spec.commands if spec else {command_name}
        for name in command_names:
            state = self.command_state(name)
            if not state.enabled:
                return AvailabilityDecision(available=False, reason=state.reason or f"命令 {name} 已关闭")

        plugin_state = self.plugin_state(spec.plugin_module if spec else None)
        if not plugin_state.enabled:
            return AvailabilityDecision(
                available=False,
                reason=plugin_state.reason or f"插件 {spec.plugin_module if spec else ''} 已关闭",
            )
        return AvailabilityDecision()

    def is_helper_available(self, helper: Helper) -> bool:
        """判断旧 Helper 在软开关过滤后是否仍可见。

        Args:
            helper: 旧帮助元数据对象。

        Returns:
            bool: 可见时返回 ``True``。
        """

        from .registry import command_registry

        spec = command_registry.get(helper.command)
        return self.check(spec, helper.command).available

    def filter_helpers(self, helpers: Helpers) -> Helpers:
        """过滤掉已软关闭命令对应的 Helper。

        Args:
            helpers: 当前用户角色过滤后的帮助集合。

        Returns:
            Helpers: 继续应用软关闭过滤后的帮助集合副本。
        """

        visible = Helpers()
        visible.active_roles = set(helpers.active_roles)
        visible.extend(helper for helper in helpers if self.is_helper_available(helper))
        return visible

    def command_states_payload(self) -> dict[str, dict]:
        """导出命令软开关状态。

        Returns:
            dict[str, dict]: 面向管理端和诊断接口的命令状态字典。
        """

        return {command: state.dict() for command, state in sorted(self._commands.items())}

    def plugin_states_payload(self) -> dict[str, dict]:
        """导出插件软开关状态。

        Returns:
            dict[str, dict]: 面向管理端和诊断接口的插件状态字典。
        """

        return {plugin: state.dict() for plugin, state in sorted(self._plugins.items())}


command_availability = CommandAvailabilityService()
