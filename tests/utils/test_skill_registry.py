def test_skill_registry_reads_manifests_from_resources(loaded_plugins):
    from src.core.skills import skill_registry
    from src.platform.config import skills_dir

    manifest = skill_registry.manifests["document-to-image"]

    assert manifest.root == skills_dir / "document-to-image"
    assert manifest.skill_file == skills_dir / "document-to-image" / "SKILL.md"


def test_skill_registry_loads_runtime_from_core_builtin(loaded_plugins):
    from src.core.skills import get_document_to_image_skill, skill_registry
    from src.platform.config import skill_runtime_dir

    skill = get_document_to_image_skill()
    runtime_dir = skill_registry.resolve_runtime_dir(skill.manifest.root)

    assert skill.name == "document-to-image"
    assert runtime_dir == skill_runtime_dir / "document-to-image"
    assert (runtime_dir / "runtime.py").exists()
