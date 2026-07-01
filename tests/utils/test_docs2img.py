import pytest
from src.shared.tools.docs2img import to_img


def test_comtypes_client_requires_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """非 Windows 环境不应尝试加载 COM 转换能力。"""
    monkeypatch.setattr(to_img.sys, "platform", "linux")
    monkeypatch.setattr(to_img, "_comtypes_client", None)

    with pytest.raises(RuntimeError, match="Windows COM"):
        to_img.get_comtypes_client()
