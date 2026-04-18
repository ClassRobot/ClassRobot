# 项目结构说明

## 顶层目录

- `src/`: NoneBot 插件与路由
- `utils/`: 跨插件共享的配置、模型、会话、LLM 和工具
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
- `tools/`: OCR、文档转图、COS 等工具能力
- `template/`: 渲染 prompt 和 HTML 模板的统一入口

## 当前整理原则

- 源码和资源文件分离，避免模型和模板散落在代码目录里
- 明显拼写错误直接收敛到统一命名，避免同义目录和文件长期并存
- 优先做低风险收敛，再考虑后续把 `utils/` 进一步拆成更清晰的领域模块
