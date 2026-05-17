# Agent 运行资源

`resources/agent/` 用来存放 Agent Runtime 需要随项目一起维护的资源化配置。这里保存的是“项目级工作流资源”，不是普通用户数据，也不是临时运行缓存。

## 约定文件

- `agent_orchestration_runtime.json`
  - 管理端“保存并热更新”后的 Agent 运行时编排图。
  - 文件不存在时，运行时会使用代码中的安全默认图。
  - 该文件属于项目资源，不放入 NoneBot/localstore 的默认 `config` 目录。

## 维护约定

- 这里放的是 Agent 工作流和编排资源，不放模型密钥、API 地址、token 等环境配置。
- 模型凭据和静态地址仍放 `.env`；普通运行态数据和用户数据仍走项目各自的存储目录。
- 手动修改 JSON 后建议运行 `tests/autogpt/test_orchestration_config.py` 验证图结构。
- 如果配置已经涉及“当前环境才有的瞬时状态”，应优先落到 `config_dir` 或持久化层，而不是写回这里。
