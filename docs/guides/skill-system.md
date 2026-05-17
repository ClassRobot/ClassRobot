# Skill 结构说明

## 目标

项目里这类可复用的 AI 增强能力不再只以“零散工具函数”存在，而是统一收敛为 skill：

- `resources/skills/<skill-name>/SKILL.md` 保存 AI 可读的能力定义
- `core/skills/` 负责 skill 的运行时注册、发现与调用
- `core/skills/` 负责 skill 的运行时注册、发现与调用
- 业务模块优先通过 skill 入口使用能力，而不是直接拼装底层库调用

## 当前已拆分的 skill

- `document-to-image`
  - 职责：将 Word、PPT、PDF 统一转换为图片
  - 运行时入口：`core.skills.document_to_image_skill`
- `ocr`
  - 职责：识别验证码、截图或文档图片中的文本
  - 运行时入口：`core.skills.ocr_skill`
- `qr-code`
  - 职责：生成二维码、解析二维码
  - 运行时入口：`core.skills.qr_code_skill`
- `markdown-to-image`
  - 职责：将 Markdown 转换为 HTML 或图片
  - 运行时入口：`core.skills.markdown_to_image_skill`
- `image-generation`
  - 职责：处理文生图、图生图等图片生成请求
  - 运行时入口：`core.skills.image_generation_skill`

## 面向文件处理的 skill 划分建议

如果未来要做“上传文档后自动理解、抽取、重排、导出新文件”这类能力，建议继续按 skill 边界拆分，不要把所有逻辑都塞进一个文件工具类。

推荐拆分方式：

- `document-to-image`
  - 负责把 Word、PPT、PDF 标准化成图片
  - 适合文档预览、多模态理解、OCR 前处理
- `document-reader`
  - 负责读取文档结构化内容
  - 例如标题、段落、表格、图片、样式信息
- `document-formatter`
  - 负责修改文档样式并保存新文件
  - 例如论文格式、通知格式、作业模板格式

建议原则：

- “看懂文件” 与 “改写文件” 分开建 skill
- `FileAgent` 更适合调度读取类 skill，不适合直接承担所有排版细节
- 涉及真实文件写回、样式修改、导出新文档时，优先新增独立 formatter skill
- 如果只是为了让模型看懂文档内容，优先继续复用 `document-to-image`

## 面向多媒体生成的 skill 划分建议

如果未来要做海报生成、插画生成、封面图生成、图生图改写这类能力，建议把“提示词规划”和“底层生图接口”分开。

推荐拆分方式：

- `image-generation`
  - 负责真正调用底层绘图接口
  - 输入可以是文本、图片或图片加文本
  - 输出应是图片字节、图片链接或服务端响应片段
- `poster-designer` 或其他上层 Agent
  - 负责理解用户需求
  - 负责扩写 Prompt、选择风格、判断是否需要多轮生成
  - 负责决定是否把结果上传到 COS、OSS、CDN

建议原则：

- “生成图片” 适合作为 skill
- “理解需求并规划提示词” 更适合作为 Agent
- 图片上传、消息回发属于平台出口层，不建议塞进 skill
- 当前命令层可以继续复用 skill，但底层绘图能力应只有一个统一入口

## 目录约定

- `resources/skills/`
  - 存放符合 skill 规范的能力资源目录，每个 skill 至少包含一个 `SKILL.md`
- `core/skills/builtin/`
  - 存放 skill 的运行时代码目录，若希望被自动加载，目录下提供 `runtime.py`
- `core/skills/base.py`
  - 负责解析 `SKILL.md` frontmatter，并生成 manifest
- `core/skills/registry.py`
  - 负责 skill 的发现、注册与按名称获取
- `core/skills/runtime.py`
  - 负责把 skill 元数据绑定到项目内真正可执行的运行时实现

## 使用原则

- 新增通用 AI 能力时，先判断它是否应该成为独立 skill
- 如果能力具有清晰边界、可被多个插件复用、且适合被 agent 或多步流程调用，优先做成 skill
- 插件中的业务逻辑优先依赖 `core.skills` 暴露的运行时对象
- `utils/tools/` 保留为底层实现层，不再作为能力边界的唯一表达方式

## 加载方式

项目同时支持两种 skill 加载方式。

## 默认行为

- 导入 `core.skills` 时，会默认扫描 `resources/skills/`
- 注册表初始化位置在 `core/skills/registry.py`
- 默认扫描完成后，`skill_registry` 就可以直接按名称获取 skill
- 如果你新增了新的 skill 目录，通常不需要再手写注册代码，只要目录结构和 `runtime.py` 符合约定即可
- 如果你在测试或特殊场景下需要加载额外目录，可以显式调用 `load_skill(...)` 或 `load_skills(...)`

### 方式一：目录自动加载

适合默认能力目录，使用方式接近 NoneBot 的 `load_plugins(...)`：

```python
from core.skills import load_skills

load_skills("resources/skills")
```

自动加载规则：

- 扫描目录下的每个子目录
- 读取 `SKILL.md`
- 若存在 `runtime.py`，自动导入
- 优先读取 `__skills__`
- 其次读取 `__skill__`
- 如果都没有，则自动收集模块内定义的 `BaseProjectSkill` 子类

最小目录结构：

```text
resources/skills/
└── my-skill/
    └── SKILL.md
```

```text
core/skills/builtin/
└── my-skill/
    └── runtime.py
```

`SKILL.md` 最小示例：

```md
---
name: my-skill
description: Use this skill when ...
---

# My Skill

Write the developer/AI-facing instructions here.
```

`runtime.py` 最推荐的写法：

```python
from core.skills.base import BaseProjectSkill


class MySkill(BaseProjectSkill):
    skill_name = "my-skill"

    def do_something(self) -> str:
        return "ok"


__skill__ = MySkill
```

如果一个目录里要导出多个运行时类，可以写成：

```python
from .foo import FooSkill
from .bar import BarSkill

__skills__ = [FooSkill, BarSkill]
```

如果 `runtime.py` 里既没有 `__skill__`，也没有 `__skills__`，注册表会尝试自动收集模块里定义的 `BaseProjectSkill` 子类。

### 方式二：手动注册

适合测试、内置替身或非常规 skill：

```python
from core.skills import register_skill

register_skill(MySkill, skill_dir="resources/skills/my-skill")
```

手动注册仍然保留，目录自动加载只是默认方案，不会取代显式注册。

如果你已经自己解析好了 manifest，也可以直接传入：

```python
from core.skills import register_skill
from core.skills.base import parse_skill_manifest

manifest = parse_skill_manifest(Path("resources/skills/my-skill/SKILL.md"))
register_skill(MySkill, manifest=manifest)
```

## 开发者接入步骤

当你要新增一个项目内 skill，推荐按下面的顺序做：

1. 在 `resources/skills/<skill-name>/` 下创建 `SKILL.md`
2. 在 `core/skills/builtin/<skill-name>/` 下创建 `runtime.py`
3. 在 `runtime.py` 中暴露 `__skill__` 或 `__skills__`
4. 让运行时类继承 `BaseProjectSkill`
5. 保证类上的 `skill_name` 和 `SKILL.md` 的 `name` 一致
6. 在业务代码里通过 `core.skills` 获取 skill，而不是直接写死底层工具实现

推荐示例：

```python
from core.skills import get_skill

skill = get_skill("my-skill")
```

如果你需要类型更明确的入口，建议像当前内置 skill 一样，在 `core/skills/__init__.py` 中补一个 getter：

```python
def get_my_skill() -> MySkill:
    return skill_registry.get("my-skill", MySkill)
```

## 业务代码怎么使用

推荐优先使用下面几类入口：

- `get_skill("name")`
  - 适合按字符串动态获取
- `get_xxx_skill()`
  - 适合类型明确的静态调用
- `xxx_skill`
  - 适合业务代码直接复用懒加载代理

例如：

```python
from core.skills import qr_code_skill

image = qr_code_skill.encode("https://example.com")
```

## 注意事项

- `skill_name` 必须和 `SKILL.md` 的 `name` 一致，否则无法正确注册
- `register_skill(...)` 会覆盖同名 skill 的运行时类型，并清掉旧实例缓存
- `SKILL.md` 只有元数据和说明作用；真正给 Python 运行时用的是 `core/skills/builtin/<name>/runtime.py`
- 自动加载时尽量避免在 `runtime.py` 顶层做重初始化
  - 推荐把 OCR 模型、COS 客户端、浏览器渲染器之类的重依赖放到方法里按需导入
- 如果一个目录只有 `SKILL.md` 没有 `runtime.py`
  - 该 skill 的元数据仍然会被发现
  - 但不会自动注册可执行的运行时类
- 测试场景下如果不想影响全局注册表，建议单独创建 `SkillRegistry(...)` 实例

## 当前内置 skill 参考

可以直接参考这些目录：

- `resources/skills/document-to-image/`
- `resources/skills/image-generation/`
- `resources/skills/markdown-to-image/`
- `resources/skills/ocr/`
- `resources/skills/qr-code/`

对应运行时实现集中在：

- `core/skills/runtime.py`
- `core/skills/builtin/<skill-name>/runtime.py`

对应注册与发现逻辑在：

- `core/skills/registry.py`

## 导入约定

新代码统一从 `core.skills` 导入 skill 注册表和具体 skill 实例。不要新增其它 skill 门面目录。
