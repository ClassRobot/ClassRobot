import inspect
import importlib.util
from pathlib import Path
from typing import TypeVar, cast

from utils.config import skills_dir

from .base import SkillManifest, BaseProjectSkill, parse_skill_manifest, discover_skill_manifests

T = TypeVar("T", bound=BaseProjectSkill)


class SkillRegistry:
    """负责发现、注册并按名称提供项目内的 skill。"""

    def __init__(self, root: Path) -> None:
        """初始化 skill 注册表。

        参数:
            root (Path): skill 根目录。
        """
        self.root = root
        self.manifests = discover_skill_manifests(root)
        self._classes: dict[str, type[BaseProjectSkill]] = {}
        self._instances: dict[str, BaseProjectSkill] = {}

    def _ensure_manifest(self, skill_name: str, manifest: SkillManifest | None = None) -> SkillManifest:
        """确保指定 skill 对应的 manifest 已存在。"""
        if manifest is not None:
            self.manifests[manifest.name] = manifest
        if skill_name not in self.manifests:
            raise KeyError(f"未找到 skill `{skill_name}` 的 SKILL.md")
        return self.manifests[skill_name]

    def register(
        self,
        skill_cls: type[BaseProjectSkill],
        *,
        skill_dir: str | Path | None = None,
        manifest: SkillManifest | None = None,
    ) -> None:
        """注册一个 skill 运行时类。

        参数:
            skill_cls (type[BaseProjectSkill]): 需要注册的 skill 类型。
            skill_dir (str | Path | None): skill 所在目录，用于手动注册时补充 manifest。
            manifest (SkillManifest | None): 已解析的 skill manifest。
        """
        if not skill_cls.skill_name:
            raise ValueError(f"{skill_cls.__name__} 未定义 `skill_name`")
        if manifest is None and skill_dir is not None:
            manifest = parse_skill_manifest(Path(skill_dir) / "SKILL.md")
        self._ensure_manifest(skill_cls.skill_name, manifest)
        self._classes[skill_cls.skill_name] = skill_cls
        self._instances.pop(skill_cls.skill_name, None)

    def _load_runtime_module(self, skill_dir: Path):
        """加载 skill 目录中的运行时模块。"""
        runtime_file = skill_dir / "runtime.py"
        if not runtime_file.exists():
            return None

        module_name = f"classrobot_skill_{skill_dir.name.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, runtime_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"无法加载 skill 运行时模块: {runtime_file}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _collect_runtime_classes(self, module) -> list[type[BaseProjectSkill]]:
        """从 skill 运行时模块中提取可注册的 skill 类型。"""
        if hasattr(module, "__skills__"):
            return list(getattr(module, "__skills__"))
        if hasattr(module, "__skill__"):
            return [getattr(module, "__skill__")]

        classes: list[type[BaseProjectSkill]] = []
        for _, value in inspect.getmembers(module, inspect.isclass):
            if value is BaseProjectSkill or not issubclass(value, BaseProjectSkill):
                continue
            if value.__module__ != module.__name__:
                continue
            classes.append(value)
        return classes

    def load_skill(self, skill_dir: str | Path) -> tuple[type[BaseProjectSkill], ...]:
        """从单个 skill 目录自动加载 skill。

        参数:
            skill_dir (str | Path): skill 目录路径。

        返回:
            tuple[type[BaseProjectSkill], ...]: 自动注册的 skill 类型列表。
        """
        skill_path = Path(skill_dir)
        manifest = parse_skill_manifest(skill_path / "SKILL.md")
        self.manifests[manifest.name] = manifest

        module = self._load_runtime_module(skill_path)
        if module is None:
            return tuple()

        classes = self._collect_runtime_classes(module)
        for skill_cls in classes:
            self.register(skill_cls, manifest=manifest)
        return tuple(classes)

    def load_skills(self, root: str | Path | None = None) -> tuple[type[BaseProjectSkill], ...]:
        """从指定目录中自动发现并加载全部 skill。

        参数:
            root (str | Path | None): skill 根目录，默认使用注册表根目录。

        返回:
            tuple[type[BaseProjectSkill], ...]: 自动注册的 skill 类型列表。
        """
        skills_root = Path(root) if root is not None else self.root
        if not skills_root.exists():
            return tuple()

        loaded: list[type[BaseProjectSkill]] = []
        for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir()):
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            loaded.extend(self.load_skill(skill_dir))
        return tuple(loaded)

    def get(self, name: str, expected_type: type[T] | None = None) -> BaseProjectSkill | T:
        """按名称获取 skill 实例。

        参数:
            name (str): skill 名称。
            expected_type (type[T] | None): 期望的 skill 类型。

        返回:
            BaseProjectSkill | T: 对应的 skill 实例。
        """
        if name not in self._classes:
            raise KeyError(f"skill `{name}` 未注册")
        if name not in self._instances:
            manifest = self.manifests[name]
            self._instances[name] = self._classes[name](manifest)

        skill = self._instances[name]
        if expected_type is not None and not isinstance(skill, expected_type):
            raise TypeError(f"skill `{name}` 不是期望的类型 `{expected_type.__name__}`")
        return cast(T, skill)

    def all(self) -> tuple[BaseProjectSkill, ...]:
        """返回全部已注册 skill 实例。"""
        return tuple(self.get(name) for name in self._classes)

    def summaries(self) -> list[dict[str, str]]:
        """返回 skill 摘要列表。"""
        return [{"name": manifest.name, "description": manifest.description} for manifest in self.manifests.values()]


skill_registry = SkillRegistry(skills_dir)
skill_registry.load_skills()
