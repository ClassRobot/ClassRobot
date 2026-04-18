# 项目结构说明

## 顶层目录

- `src/`: NoneBot 插件与路由
- `utils/`: 跨插件共享的配置、模型、会话、LLM 和工具
- `skills/`: 符合 skill 规范的能力目录，每个能力以独立 `SKILL.md` 管理
- `resources/`: 非源码运行资源，例如 prompts、HTML 模板和 OCR 模型
- `scripts/`: 仓库级辅助脚本
- `migrations/`: 数据库迁移
- `docs/`: 使用和开发文档

## src 下的约定

- `src/managers/`: 班级、用户、权限等管理能力
- `src/plugins/`: 面向最终功能的主要插件
- `src/others/`: 额外实验性或外部集成能力
- `src/routers/`: 路由或路径相关模块

## utils 下的约定

- `config.py`: 全局配置和路径入口
- `models/`: ORM 模型与依赖
- `helper/`: 帮助系统与参数抽象
- `llm/`: 大模型客户端、消息结构和 Agent 能力
- `skills/`: skill 运行时注册层，负责把 `skills/` 元数据接到项目代码
- `tools/`: OCR、文档转图、COS 等工具能力
- `template/`: 渲染 prompt 和 HTML 模板的统一入口

## skills 下的约定

- `skills/<name>/SKILL.md`: AI 可读的 skill 元数据与使用说明
- `skills/<name>/runtime.py`: 可选的 skill 运行时入口，存在时可被自动加载
- 目前已经拆分的能力包括：
  - `document-to-image`
  - `ocr`
  - `qr-code`
  - `markdown-to-image`
- `skills/` 负责定义能力边界
- `utils/skills/` 负责运行时发现与调用
- `utils/skills/registry.py` 同时支持目录自动加载和手动注册两种模式
- `utils/tools/` 继续承载底层实现细节，例如 OCR 模型、Office 转图、二维码库封装等

## 当前整理原则

- 源码和资源文件分离，避免模型和模板散落在代码目录里
- 能力边界优先以 skill 表达，再决定底层代码落在 `utils/tools/` 还是其他共享模块
- 明显拼写错误直接收敛到统一命名，避免同义目录和文件长期并存
- 优先做低风险收敛，再考虑后续把 `utils/` 进一步拆成更清晰的领域模块
