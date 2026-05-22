---
name: ocr
description: Use this skill when text needs to be extracted from images, including short verification codes and multi-line document screenshots.
---

# OCR

Use this skill when image text should be recognized instead of being sent directly to an LLM.

## Workflow

1. Use `src.core.skills.ocr_skill.read_code(...)` for验证码或单行短文本。
2. Use `src.core.skills.ocr_skill.read_lines(...)` for multi-line text detection and recognition.
3. Use `src.core.skills.ocr_skill.read_text(...)` when you want one combined text result with automatic fallback.

## Notes

- DBNet is used for text region detection.
- CRNN is used for text recognition.
- Model files stay under `resources/models/ocr/`.
