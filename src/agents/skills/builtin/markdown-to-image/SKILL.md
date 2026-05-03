---
name: markdown-to-image
description: Use this skill when Markdown content must be rendered into HTML or image output for chat previews, long replies, or rich document screenshots.
---

# Markdown To Image

Use this skill when Markdown should become user-visible rich output instead of plain text.

## Workflow

1. Use `src.agents.skills.markdown_to_image_skill.to_html(...)` when you need editable HTML output.
2. Use `src.agents.skills.markdown_to_image_skill.to_image(...)` when Markdown can be rendered directly to an image.
3. Use `src.agents.skills.markdown_to_image_skill.html_to_image(...)` when HTML has been post-processed before rendering.

## Notes

- This skill is the canonical entry for Markdown preview rendering.
- Existing feature modules should call the runtime skill instead of assembling renderer calls ad hoc.
