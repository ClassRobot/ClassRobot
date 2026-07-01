import re
from pathlib import Path
from dataclasses import dataclass

FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)


@dataclass(frozen=True)
class SkillManifest:
    """描述单个 skill 的基础元数据。"""

    name: str
    description: str
    root: Path
    skill_file: Path
    body: str


def parse_skill_manifest(skill_file: Path) -> SkillManifest:
    """解析 skill 的 `SKILL.md` 文件。

    参数:
        skill_file (Path): skill 文档文件路径。

    返回:
        SkillManifest: 解析后的 skill 元数据对象。
    """
    content = skill_file.read_text("utf-8").strip()
    matched = FRONTMATTER_RE.match(content)
    if matched is None:
        raise ValueError(f"{skill_file} 缺少合法的 frontmatter")

    frontmatter_text, body = matched.groups()
    frontmatter: dict[str, str] = {}
    for line in frontmatter_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or line.startswith((" ", "\t")):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip("'\"")

    name = frontmatter.get("name")
    description = frontmatter.get("description")
    if not name or not description:
        raise ValueError(f"{skill_file} 缺少必填字段 `name` 或 `description`")

    return SkillManifest(
        name=name,
        description=description,
        root=skill_file.parent,
        skill_file=skill_file,
        body=body.strip(),
    )


def discover_skill_manifests(skills_root: Path) -> dict[str, SkillManifest]:
    """扫描并加载仓库内的全部 skill。

    参数:
        skills_root (Path): skill 根目录。

    返回:
        dict[str, SkillManifest]: 以 skill 名称为键的 manifest 映射。
    """
    manifests: dict[str, SkillManifest] = {}
    if not skills_root.exists():
        return manifests

    for skill_root in sorted(path for path in skills_root.iterdir() if path.is_dir()):
        skill_file = skill_root / "SKILL.md"
        if not skill_file.exists():
            continue
        manifest = parse_skill_manifest(skill_file)
        manifests[manifest.name] = manifest
    return manifests


class BaseProjectSkill:
    """定义项目内 skill 运行时对象的统一基类。"""

    skill_name: str = ""

    def __init__(self, manifest: SkillManifest) -> None:
        """初始化 skill 运行时对象。

        参数:
            manifest (SkillManifest): skill 的元数据对象。
        """
        self.manifest = manifest

    @property
    def name(self) -> str:
        """返回 skill 名称。"""
        return self.manifest.name

    @property
    def description(self) -> str:
        """返回 skill 描述。"""
        return self.manifest.description

    @property
    def root(self) -> Path:
        """返回 skill 根目录。"""
        return self.manifest.root
