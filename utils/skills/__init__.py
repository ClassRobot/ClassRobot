from .base import BaseProjectSkill, SkillManifest
from .registry import SkillRegistry, skill_registry
from .runtime import DocumentToImageSkill, ImageGenerationSkill, MarkdownToImageSkill, OCRSkill, QRCodeSkill


class LazySkillProxy:
    """在首次使用时再解析真实 skill 实例的轻量代理。"""

    def __init__(self, getter) -> None:
        """初始化延迟代理。

        参数:
            getter (Callable[[], BaseProjectSkill]): 返回真实 skill 的函数。
        """
        self._getter = getter

    def __getattr__(self, item):
        """将属性访问转发到真实 skill 对象。"""
        return getattr(self._getter(), item)


def get_skill(name: str) -> BaseProjectSkill:
    """按名称获取项目内的 skill 实例。"""
    return skill_registry.get(name)


def load_skill(skill_dir: str) -> tuple[type[BaseProjectSkill], ...]:
    """从单个目录自动加载 skill。"""
    return skill_registry.load_skill(skill_dir)


def load_skills(root: str | None = None) -> tuple[type[BaseProjectSkill], ...]:
    """从目录中自动发现并加载全部 skill。"""
    return skill_registry.load_skills(root)


def register_skill(
    skill_cls: type[BaseProjectSkill],
    *,
    skill_dir: str | None = None,
    manifest: SkillManifest | None = None,
) -> None:
    """手动注册 skill 运行时类。"""
    skill_registry.register(skill_cls, skill_dir=skill_dir, manifest=manifest)


def get_document_to_image_skill() -> DocumentToImageSkill:
    """获取文档转图片 skill。"""
    return skill_registry.get("document-to-image", DocumentToImageSkill)


def get_ocr_skill() -> OCRSkill:
    """获取 OCR skill。"""
    return skill_registry.get("ocr", OCRSkill)


def get_qr_code_skill() -> QRCodeSkill:
    """获取二维码 skill。"""
    return skill_registry.get("qr-code", QRCodeSkill)


def get_markdown_to_image_skill() -> MarkdownToImageSkill:
    """获取 Markdown 转图片 skill。"""
    return skill_registry.get("markdown-to-image", MarkdownToImageSkill)


def get_image_generation_skill() -> ImageGenerationSkill:
    """获取图片生成 skill。"""
    return skill_registry.get("image-generation", ImageGenerationSkill)


document_to_image_skill = LazySkillProxy(get_document_to_image_skill)
ocr_skill = LazySkillProxy(get_ocr_skill)
qr_code_skill = LazySkillProxy(get_qr_code_skill)
markdown_to_image_skill = LazySkillProxy(get_markdown_to_image_skill)
image_generation_skill = LazySkillProxy(get_image_generation_skill)

__all__ = [
    "BaseProjectSkill",
    "DocumentToImageSkill",
    "ImageGenerationSkill",
    "MarkdownToImageSkill",
    "OCRSkill",
    "QRCodeSkill",
    "SkillManifest",
    "SkillRegistry",
    "document_to_image_skill",
    "get_document_to_image_skill",
    "get_image_generation_skill",
    "get_markdown_to_image_skill",
    "get_ocr_skill",
    "get_qr_code_skill",
    "get_skill",
    "image_generation_skill",
    "load_skill",
    "load_skills",
    "markdown_to_image_skill",
    "ocr_skill",
    "qr_code_skill",
    "register_skill",
    "skill_registry",
]
