---
name: document-to-image
description: Use this skill when Word, PPT, or PDF files need to be normalized into images before OCR, multimodal understanding, or preview rendering.
---

# Document To Image

Use this skill when the input is a `.doc`, `.docx`, `.ppt`, `.pptx`, or `.pdf` file and downstream logic works better on page images than on the original binary document.

## Workflow

1. Prefer `core.skills.document_to_image_skill.convert(...)` when the source may be bytes, local paths, or remote URLs.
2. Prefer `core.skills.document_to_image_skill.convert_local_file(...)` when the source is already a local file and you need explicit output paths.
3. Reuse `utils.tools.docs2img` as the low-level converter implementation instead of duplicating Office/PDF conversion logic.

## Notes

- This skill is the canonical entry for document-to-image normalization inside the project.
- The runtime implementation lives in `core/skills/runtime.py`.
