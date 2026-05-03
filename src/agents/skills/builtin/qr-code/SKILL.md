---
name: qr-code
description: Use this skill when the project needs to generate QR codes from text or decode QR codes from images.
---

# QR Code

Use this skill for QR generation and parsing instead of hand-writing `qrcode` or `pyzbar` calls in feature modules.

## Workflow

1. Use `src.agents.skills.qr_code_skill.encode(...)` to generate a QR image from text.
2. Use `src.agents.skills.qr_code_skill.decode(...)` to parse all QR values in an image.
3. Use `src.agents.skills.qr_code_skill.decode_one(...)` when only the first QR result is needed.

## Notes

- The runtime implementation centralizes both generation and decoding.
- This skill is reused by task export and document download flows.
