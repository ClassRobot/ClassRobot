# 配置说明

本文档用于统一说明项目中通过 `.env` 注入的配置项，包括：

- 应该在哪个文件里填写
- 每个变量的作用
- 哪些必须填，哪些可选
- JSON / 数组类变量应该怎么写
- 给开发环境和生产环境分别如何配置

## 配置分层约定

项目中的配置不要混着放，统一按下面三层处理：

1. 硬编码基础配置写在仓库根目录的 `.env` 体系中
- 例如 `.env`、`.env.dev`、`.env.prod`
- 这类配置用于项目启动时就要确定的基础参数，例如监听地址、数据库连接、平台接入、模型基线配置、各类密钥等
- 这部分本质上属于“启动配置”或“环境配置”，应优先通过环境变量加载

2. 运行过程中可热更新、可持久化的动态配置默认写到 `config` 目录
- 这类数据不应继续直接回写到源码目录中的业务文件
- 例如后台保存的运行时 JSON 配置、某些本地管理状态快照等
- `config` 目录的真实路径不要在业务代码里手写，统一从 `src.platform.config` 中提供的 `config_dir` 获取

3. Agent 工作流编排配置写到 `resources/agent`
- Agent Runtime 编排图属于项目工作流资源，需要随仓库结构和文档一起维护
- 热更新后的运行时图文件为 `resources/agent/agent_orchestration_runtime.json`
- 路径由 `src.platform.config.agent_resources_dir` 提供，不放入 NoneBot/localstore 的默认 `config` 目录

推荐理解方式：

- `.env` 负责“项目启动前就确定的配置基线”
- `config_dir` 负责“项目运行后可能被后台、Agent 或本地工具热更新的数据”
- `resources/agent` 负责“Agent 工作流编排这类需要项目化维护的资源配置”

这样做的目的有两个：

- 避免把运行期生成的数据散落到仓库各处，降低维护成本
- 避免把应当版本化管理的基础配置，和应当本地持久化的运行时状态混在一起

## 配置文件约定

当前仓库根目录下已经存在：

- `.env`
  - 默认本地开发配置
- `.env.dev`
  - 开发环境附加配置
- `.env.prod`
  - 生产环境附加配置

推荐使用方式：

1. 本地开发时，优先维护 `.env`
2. 团队协作时，可以保留 `.env.dev` 作为开发模板
3. 部署环境中，使用 `.env.prod` 或部署平台的环境变量注入

注意事项：

- 不要把真实密钥、Token、Secret 提交到公开仓库
- 文档中的示例值全部应该替换成你自己的真实配置
- 涉及 JSON、数组、列表的配置项，建议直接按 JSON 字符串填写
- 不要把普通热更新运行态数据直接写回文档、Prompt、源码目录或随意新建的 JSON 文件；这类数据统一写到 `src.platform.config.config_dir` 对应的本地配置目录
- Agent Runtime 工作流编排是例外，固定写入 `resources/agent/agent_orchestration_runtime.json`
- 当前仓库历史上同时存在大写和小写配置名写法
  - 例如 `.env` 中有 `CACHE_HOST`
  - `.env.dev` 中也有 `llm_configs`
  - 为了统一风格，本文档默认使用“推荐写法”展示
  - 新增配置建议优先使用大写环境变量名

## 配置分组概览

当前项目中的环境变量主要分为以下几类：

1. 基础运行配置
2. NoneBot 与插件基础配置
3. 数据库与缓存配置
4. LLM / Agent / RAG 配置
5. 文件、对象存储与工具配置
6. 平台接入配置
7. 业务补充配置

## 路径来源约定

项目内部和“本地持久化目录”相关的路径统一从 `src/platform/config.py` 提供，不建议在业务模块重复手写。

当前至少包括这些公共路径：

- `project_root`
  - 仓库根目录
- `data_dir`
  - NoneBot 本地数据目录
- `cache_dir`
  - NoneBot 本地缓存目录
- `config_dir`
  - NoneBot 本地配置目录
- `resources_dir`
  - 项目内置资源目录
- `agent_resources_dir`
  - Agent Runtime 工作流编排资源目录，对应 `resources/agent`

后续如果某个功能需要“可热更新且不适合写回 `.env`”的本地配置文件，应优先落到 `config_dir` 下，并在附近文档或 README 中明确说明文件名和用途。Agent 工作流编排这种需要随项目工程资产维护的资源化配置，应放到 `agent_resources_dir`。

---

## 1. 基础运行配置

这部分用于控制当前应用以什么驱动启动、监听哪个地址与端口。

| 变量名 | 是否必填 | 示例值 | 作用 |
| --- | --- | --- | --- |
| `ENVIRONMENT` | 建议填写 | `dev` | 当前环境标识，常见值为 `dev`、`test`、`prod`。主要用于区分开发、测试、生产环境。 |
| `DRIVER` | 必填 | `~fastapi+~httpx+~websockets+~aiohttp` | NoneBot 驱动组合，决定应用启用哪些协议与运行方式。当前项目开发环境建议保持现有组合。 |
| `HOST` | 必填 | `127.0.0.1` | 当前服务监听地址。本地开发可用 `127.0.0.1`，局域网调试或容器部署可根据实际情况修改。 |
| `PORT` | 必填 | `8080` | 当前服务监听端口。 |
| `LOG_LEVEL` | 可选 | `INFO` | 日志级别。调试时可临时改为 `DEBUG` 或 `TRACE`。 |

建议：

- 本地开发常用 `HOST=127.0.0.1`
- 如果要让局域网其他设备访问，可以改为 `0.0.0.0`

---

## 2. NoneBot 与插件基础配置

这部分主要来自 NoneBot 本身以及已安装插件的配置项。

### 2.1 命令与会话相关

| 变量名 | 是否必填 | 示例值 | 作用 |
| --- | --- | --- | --- |
| `SUPERUSERS` | 建议填写 | `[]` | 超级用户列表。可用于控制部分高权限命令。通常写成 JSON 数组。 |
| `COMMAND_START` | 建议填写 | `["/", ""]` | 命令前缀列表。`""` 表示允许无前缀命令。 |
| `COMMAND_SEP` | 建议填写 | `[".", " "]` | 命令分隔符列表。 |
| `SESSION_EXPIRE_TIMEOUT` | 建议填写 | `90` | 会话过期时间，单位通常为秒，用于控制等待类交互会话。 |
| `API_TIMEOUT` | 建议填写 | `300` | API 调用超时时间，通常用于 Bot API 或平台 API 调用。 |

说明：

- `SUPERUSERS`、`COMMAND_START`、`COMMAND_SEP` 建议写成标准 JSON 字符串
- 如果你不希望机器人支持无前缀命令，可以把 `COMMAND_START` 改成如 `["/"]`

### 2.2 插件行为相关

| 变量名 | 是否必填 | 示例值 | 作用 |
| --- | --- | --- | --- |
| `server_status_only_superusers` | 可选 | `false` | 是否仅允许超级用户查看运行状态。来自状态插件。 |
| `HTMLRENDER_BROWSER` | 建议填写 | `firefox` | HTML 渲染插件使用的浏览器类型，常见为 `firefox` 或 `chromium`。 |
| `ANIMERES_FORWARD` | 可选 | `false` | 动漫资源插件相关转发配置。当前项目通常保持默认即可。 |
| `alconna_use_param` | 建议填写 | `true` | 是否启用 Alconna 参数系统。 |
| `alconna_use_command_start` | 建议填写 | `true` | 是否让 Alconna 使用命令前缀配置。 |
| `alconna_use_command_sep` | 建议填写 | `true` | 是否让 Alconna 使用命令分隔符配置。 |
| `alconna_auto_completion` | 建议填写 | `true` | 是否启用命令自动补全。 |
| `alconna_global_extensions` | 可选 | `[]` | Alconna 全局扩展列表，通常写成 JSON 数组。 |

建议：

- 如果没有特殊需求，以上插件参数基本可以保持默认示例

---

## 3. 数据库与缓存配置

### 3.1 ORM 数据库配置

| 变量名 | 是否必填 | 示例值 | 作用 |
| --- | --- | --- | --- |
| `SQLALCHEMY_DATABASE_URL` | 必填 | `sqlite+aiosqlite:///db.sqlite3` | 主业务数据库连接串，供 `nonebot-plugin-orm` 使用。 |

常见写法：

```env
# SQLite
SQLALCHEMY_DATABASE_URL=sqlite+aiosqlite:///db.sqlite3

# PostgreSQL
SQLALCHEMY_DATABASE_URL=postgresql+asyncpg://user:password@127.0.0.1:5432/classbot
```

说明：

- 本地开发可以先用 SQLite
- 生产环境更推荐 PostgreSQL

### 3.2 Redis / 缓存配置

这部分来自 `src/core/cache/config.py`。

| 变量名 | 是否必填 | 默认值 | 示例值 | 作用 |
| --- | --- | --- | --- | --- |
| `CACHE_HOST` | 可选 | `localhost` | `127.0.0.1` | Redis 主机地址。 |
| `CACHE_PORT` | 可选 | `6379` | `6379` | Redis 端口。 |

说明：

- 当前项目已经有缓存接入层，但并不是所有记忆都已经持久化到 Redis
- 后续如果引入持久化记忆层，这两个参数会更重要

---

## 4. LLM / Agent / RAG 配置

这部分是当前最核心、也最容易写错的一组配置。

### 4.1 通用全局 AI 配置

这部分来自 `src/platform/config.py`。

| 变量名 | 是否必填 | 示例值 | 作用 |
| --- | --- | --- | --- |
| `GLOBAL_PROXY` | 可选 | `http://127.0.0.1:7890` | 全局代理地址。用于需要代理访问外部模型或服务时。 |
| `GOOGLEAPIS_KEY` | 按需填写 | `your_google_api_key` | Google / Gemini 相关接口 Key。当前图片生成能力会用到。 |
| `RAGFLOW_KEY` | 按需填写 | `your_ragflow_api_key` | RagFlow API Key。开启知识检索链路时必填。 |
| `RAGFLOW_URL` | 按需填写 | `http://127.0.0.1:9380` | RagFlow 服务地址。开启知识检索链路时必填。 |
| `WSL_SHARE_DIR` | 可选 | `\\\\wsl$\\Ubuntu\\home\\user\\share` | Windows 与 WSL 共享目录，用于某些文件处理或任务导出场景。 |
| `TEACHER_MAX_CLASSES` | 可选 | `6` | 单个教师允许绑定或管理的最大班级数量。 |

说明：

- 如果你暂时不用 RAG，可以先不填 `RAGFLOW_KEY` 和 `RAGFLOW_URL`
- 如果你暂时不用生图，可以先不填 `GOOGLEAPIS_KEY`
- 这类全局配置仍属于启动前确定的基础配置，应写在 `.env` 体系中，而不是运行后再写入 `config_dir`

### 4.2 LLM 模型路由配置

这部分来自 `src/core/llm/config.py`。

| 变量名 | 是否必填 | 示例值 | 作用 |
| --- | --- | --- | --- |
| `llm_configs` | 建议填写 | 见下方示例 | 模型配置列表。支持配置多个模型，供系统按能力路由。 |
| `llm_timeout` | 建议填写 | `60` | LLM 请求超时时间，单位秒。 |

`llm_configs` 的单个配置项字段说明：

| 字段名 | 是否必填 | 示例值 | 作用 |
| --- | --- | --- | --- |
| `name` | 必填 | `volcengine_ark` | 模型配置名称，用于内部识别和路由。 |
| `key` | 必填 | `<your_volcengine_ark_key>` | 模型服务 API Key。 |
| `url` | 必填 | `https://ark.cn-beijing.volces.com/api/v3` | 模型服务 Base URL。 |
| `model` | 必填 | `ep-20250702155751-ztq4h` | 实际调用的模型名称。 |
| `proxy` | 可选 | `http://127.0.0.1:7890` | 当前模型独立代理地址。留空或省略时不为该模型启用代理。 |
| `priority` | 可选 | `100` | 路由优先级，值越大越优先。 |
| `tasks` | 可选 | `["chat", "summary", "extract", "plan", "reply"]` | 偏好的任务类型标签。用于模型路由。 |
| `multi_modal` | 可选 | `false` | 是否支持多模态。 |
| `supports_functools` | 可选 | `false` | 是否支持工具调用 / 函数调用。 |

如果你当前使用的是火山引擎方舟兼容接口，可以直接按下面结构填写：

```env
llm_configs='
[
    {
        "name":"volcengine_ark",
        "key":"<your_volcengine_ark_key>",
        "url":"https://ark.cn-beijing.volces.com/api/v3",
        "model":"ep-20250702155751-ztq4h",
        "proxy":"http://127.0.0.1:7890",
        "priority":100,
        "tasks":["chat","summary","extract","plan","reply"],
        "multi_modal":false,
        "supports_functools":false
    }
]'
llm_timeout=60
```

建议：

- 至少配置一个主模型
- 如果后续要把摘要、抽取、规划、生图理解拆开，可以配置多个模型
- 如果只有个别模型需要代理，优先为对应模型单独填写 `proxy`，不要默认影响所有模型
- 对于 `llm_configs` 这类复杂 JSON 配置，建议像上面这样用单引号包住多行内容，避免 `.env` 解析时出现转义或引号问题
- `llm_configs` 属于模型基线配置，原则上仍应维护在 `.env` 中；如果后续某些运行态策略需要热更新，应拆成独立运行时配置文件写入 `config_dir`

### 4.3 RAG 配置

虽然 `RAGFLOW_KEY` 和 `RAGFLOW_URL` 已经在通用 AI 配置里列出，但这里单独强调一次：

| 变量名 | 是否必填 | 示例值 | 作用 |
| --- | --- | --- | --- |
| `RAGFLOW_URL` | 使用 RAG 时必填 | `http://127.0.0.1:9380` | RagFlow 服务地址。 |
| `RAGFLOW_KEY` | 使用 RAG 时必填 | `your_ragflow_api_key` | RagFlow 服务认证 Key。 |

如果不配置：

- RAG 检索链路无法正常工作
- 文档知识问答能力无法接通

---

## 5. 文件、对象存储与工具配置

### 5.1 COS 对象存储配置

这部分来自 `src/core/storage/object_store.py`。

| 变量名 | 是否必填 | 示例值 | 作用 |
| --- | --- | --- | --- |
| `COS_SECRET_ID` | 按需填写 | `your_cos_secret_id` | 腾讯云 COS SecretId。 |
| `COS_SECRET_KEY` | 按需填写 | `your_cos_secret_key` | 腾讯云 COS SecretKey。 |
| `REGION` | 按需填写 | `ap-guangzhou` | COS 所在地域。 |
| `BUCKET` | 按需填写 | `classbot-1300000000` | COS 存储桶名称。 |
| `SCHEME` | 可选 | `https` | COS 访问协议，默认 `https`。 |

说明：

- 如果你要使用图片上传、文件上传、RAG 引用图片回传、生图结果持久化，这组配置基本都需要
- 如果不配置 COS，部分“图片/文件换公网链接”的能力会受限

### 5.2 加密盐配置

这部分来自 `src/core/auth/crypto.py`。

| 变量名 | 是否必填 | 示例值 | 作用 |
| --- | --- | --- | --- |
| `ENCRYPT_SALT` | 建议填写 | `a1b2c3...` | 密码或敏感数据哈希使用的盐值。 |

说明：

- 如果不填写，系统会自动生成并写入本地配置目录
- 但为了环境可迁移、部署后稳定一致，建议明确写到 `.env` 中

---

## 6. 平台接入配置

### 6.1 QQ 官方适配器配置

这部分来自 NoneBot QQ 适配器。

| 变量名 | 是否必填 | 示例值 | 作用 |
| --- | --- | --- | --- |
| `QQ_IS_SANDBOX` | 按需填写 | `true` | 是否使用 QQ 沙箱环境。开发联调时通常为 `true`。 |
| `QQ_BOTS` | 接入 QQ 时必填 | 见下方示例 | QQ Bot 列表配置。通常写成 JSON 字符串。 |

推荐写法：

```env
QQ_IS_SANDBOX=true
QQ_BOTS='[
  {
    "id": "your_bot_app_id",
    "token": "your_bot_token",
    "secret": "your_bot_secret",
    "intent": {
      "c2c_group_at_messages": true
    }
  }
]'
```

说明：

- 如果你接多个 QQ Bot，可以在数组里写多个对象
- 建议保持 JSON 结构合法，避免多余逗号和引号错误

### 6.2 未来飞书接入配置

当前仓库还没有完整落地飞书 Webhook 接入，但后续大概率会新增类似下面的配置：

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_VERIFICATION_TOKEN`
- `FEISHU_ENCRYPT_KEY`

当前这些变量还没有在代码中完全落地，所以本节先作为预留说明，不建议提前乱加到生产配置里。

---

## 7. 业务补充配置

### 7.1 教师班级数量限制

| 变量名 | 是否必填 | 默认值 | 示例值 | 作用 |
| --- | --- | --- | --- | --- |
| `TEACHER_MAX_CLASSES` | 可选 | `6` | `8` | 教师允许管理的最大班级数量。 |

### 7.2 WSL 共享目录

| 变量名 | 是否必填 | 示例值 | 作用 |
| --- | --- | --- | --- |
| `WSL_SHARE_DIR` | 可选 | `\\\\wsl$\\Ubuntu\\home\\user\\share` | 在 Windows + WSL 混合环境下处理文件时使用的共享目录。 |

---

## 最小可运行配置

如果你只想先把项目跑起来，最小建议配置如下：

```env
ENVIRONMENT=dev
DRIVER=~fastapi+~httpx+~websockets+~aiohttp
HOST=127.0.0.1
PORT=8080

SUPERUSERS=[]
COMMAND_START=["/", ""]
COMMAND_SEP=[".", " "]
SESSION_EXPIRE_TIMEOUT=90
API_TIMEOUT=300

SQLALCHEMY_DATABASE_URL=sqlite+aiosqlite:///db.sqlite3

CACHE_HOST=localhost
CACHE_PORT=6379

TEACHER_MAX_CLASSES=6
HTMLRENDER_BROWSER=firefox
alconna_use_param=true
alconna_use_command_start=true
alconna_use_command_sep=true
alconna_auto_completion=true
alconna_global_extensions=[]

llm_configs=[]
llm_timeout=60
```

说明：

- 这份配置足够本地启动，但不代表所有 AI 能力都能正常使用
- 如果 `llm_configs=[]`，很多 AI 功能不会生效

## 推荐开发环境配置模板

如果你要在本地完整调试主要能力，可以参考下面模板：

```env
ENVIRONMENT=dev
DRIVER=~fastapi+~httpx+~websockets+~aiohttp
HOST=127.0.0.1
PORT=8080
LOG_LEVEL=INFO

SUPERUSERS=[]
COMMAND_START=["/", ""]
COMMAND_SEP=[".", " "]
SESSION_EXPIRE_TIMEOUT=90
API_TIMEOUT=300

SQLALCHEMY_DATABASE_URL=sqlite+aiosqlite:///db.sqlite3

CACHE_HOST=localhost
CACHE_PORT=6379

TEACHER_MAX_CLASSES=6
WSL_SHARE_DIR=
GLOBAL_PROXY=

HTMLRENDER_BROWSER=firefox
server_status_only_superusers=false
ANIMERES_FORWARD=false
alconna_use_param=true
alconna_use_command_start=true
alconna_use_command_sep=true
alconna_auto_completion=true
alconna_global_extensions=[]

llm_configs='
[
  {
    "name":"volcengine_ark",
    "key":"<your_volcengine_ark_key>",
    "url":"https://ark.cn-beijing.volces.com/api/v3",
    "model":"ep-20250702155751-ztq4h",
    "proxy":"",
    "priority":100,
    "tasks":["chat","summary","extract","plan","reply"],
    "multi_modal":false,
    "supports_functools":false
  }
]'
llm_timeout=60

GOOGLEAPIS_KEY=
RAGFLOW_URL=
RAGFLOW_KEY=

COS_SECRET_ID=
COS_SECRET_KEY=
REGION=
BUCKET=
SCHEME=https

ENCRYPT_SALT=

QQ_IS_SANDBOX=true
QQ_BOTS=[]
```

## 按能力启用时需要补哪些配置

### 1. 只跑基础机器人能力

至少需要：

- 基础运行配置
- 数据库配置
- 命令与插件基础配置

### 2. 启用 AI 对话能力

额外需要：

- `llm_configs`
- `llm_timeout`

### 3. 启用 RAG 知识问答

额外需要：

- `RAGFLOW_URL`
- `RAGFLOW_KEY`
- 通常还建议配好 COS，用于引用图片回传

### 4. 启用图片生成

额外需要：

- `GOOGLEAPIS_KEY`
- 通常还建议配置 COS，用于回传图片链接

### 5. 启用文件上传/图片上传/导出文件

额外需要：

- `COS_SECRET_ID`
- `COS_SECRET_KEY`
- `REGION`
- `BUCKET`

### 6. 启用 QQ 官方机器人

额外需要：

- `QQ_IS_SANDBOX`
- `QQ_BOTS`

## 常见问题

### 1. 为什么有些变量在代码里是小写，但 `.env` 里我看到是大写？

因为当前项目历史上同时存在两种写法：

- 一部分变量沿用传统环境变量风格，使用大写
- 一部分变量直接沿用 Pydantic 字段名，使用小写，例如 `llm_configs`

对于当前项目，建议优先以“代码实际使用方式”和“现有 `.env` 示例”保持一致，不要强行混改。

### 2. `llm_configs` 为什么这么复杂？

因为系统支持多个模型配置，并且后续会按任务类型、优先级、是否多模态、是否支持工具调用来做路由，所以必须用结构化 JSON 描述。

### 3. `QQ_BOTS` 为什么建议写成 JSON？

因为它本质上是一个 Bot 列表对象，不是单个字符串。写成 JSON 更适合扩展多个 Bot。

### 4. `ENCRYPT_SALT` 不填会怎样？

系统会自动生成并保存到本地配置目录，但这会导致不同环境间不容易保持一致，所以仍然建议显式填写。

### 5. 我暂时不用 RAG / 生图 / COS，是不是可以不填？

可以。只要对应能力没有启用，就可以先不填这些变量。

## 配合阅读

- [项目结构说明](./project-structure.md)
  - 查看代码和资源目录如何组织
- [项目能力总览](../reference/capability-overview.md)
  - 查看当前已经有哪些能力
- [消息处理流程](../guides/message-processing-flow.md)
  - 查看消息、RAG、文件、生图链路如何流转
- [当前系统架构设计](../architecture/current-system-architecture-design.md)
  - 查看当前系统总体架构设计
