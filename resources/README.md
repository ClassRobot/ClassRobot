# 运行资源目录

`resources/` 用来存放项目运行时依赖、但不适合直接写进 Python 源码的静态资源。可以把它理解成“源码之外、但仍属于项目的一等资源层”。

## 当前目录

- `prompts/`
  - LLM、Agent、任务规划等场景使用的 Prompt 模板
- `agent/`
  - Agent Runtime 工作流编排配置和相关资源
- `skills/`
  - Skill 的 `SKILL.md` 资源定义文件
- `templates/`
  - HTML 渲染模板、卡片模板或其他展示层静态模板
- `models/ocr/`
  - OCR 检测与识别模型文件

## 维护约定

- 资源文件优先按用途归类，不要把模板、模型和示例文件混放在同一层
- Prompt 模板调整后，记得同步检查相关功能文档和测试
- 体积较大的模型文件、导出文件或临时调试产物，不要直接散落到 `resources/` 根目录
- 运行期动态状态不要随意写回 `resources/`，只有明确被定义为“项目化维护资源”的文件才放这里

## 关联文档

- 配置与运行环境：[配置说明](../docs/getting-started/configuration.md)
- Agent 与 Prompt 相关流程：[AutoGPT 智能能力改进方案](../docs/guides/agent-module.md)
