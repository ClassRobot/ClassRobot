---
name: image-generation
description: Use this skill when the user needs text-to-image or image-guided image generation, such as posters, illustrations, style changes, or creative visual drafts.
---

# Image Generation

Use this skill when the request is to generate a new image from text, or to generate a new image based on an uploaded image plus editing instructions.

## Workflow

1. Prefer `core.skills.image_generation_skill.generate(...)` as the canonical runtime entry.
2. Let the caller decide whether to upload the returned image to COS, CDN, OSS, or another permanent storage service.
3. Keep prompt expansion, style planning, and result selection in the Agent layer instead of hard-coding them into the skill itself.

## Notes

- This skill is the canonical image generation entry inside the project.
- The current runtime implementation calls the configured Gemini image generation API.
- The runtime implementation lives in `core/skills/runtime.py`.
