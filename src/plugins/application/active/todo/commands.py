from __future__ import annotations

from src.platform.config import priority, comp_config
from src.platform.helper import UserRole, HelperScope
from nonebot_plugin_alconna import Args, Field, Alconna, MultiVar, CommandMeta, AlconnaMatcher
from src.platform.commands import (
    CommandParam,
    CommandBinding,
    CommandUserContextDepends,
    command_executor,
    on_agent_command,
    send_command_result,
)

# 待办命令域：个人私有待办的创建、查询、完成与删除。
# 统一以 CommandSpec 为事实来源，用户入口与 Agent 入口共享同一 service 执行路径。
# 带 due_at 的待办相当于“日程”，不带 due_at 的待办相当于“便签”，提醒能力后续扩展。

create_todo_cmd = on_agent_command(
    Alconna(
        "创建待办",
        Args["title?", str, Field(default="", completion=lambda: "请输入待办标题")],
        # 标题之后的内容按 token 收集，由 matcher 拆分出“截止时间 + 备注”，
        # 这样用户可以自然输入 `标题 2026-05-30 14:00 备注`（日期与时间含空格）。
        Args["rest?", MultiVar(str, flag="*")],
        meta=CommandMeta(description="创建一条个人待办；可选携带截止时间和备注。"),
    ),
    aliases={"添加待办", "记待办", "新建待办"},
    binding=CommandBinding(
        roles={UserRole.user},
        scopes={HelperScope.user},
        risk_level="medium",
        agent_callable=True,
        execution_mode="service",
        # Agent 工具按结构化字段理解参数，与 matcher 的 token 收集解耦。
        params=[
            CommandParam(name="标题", description="待办标题，不能为空。", value_type="string", required=True),
            CommandParam(
                name="截止时间",
                description="可选截止时间，支持 2026-05-30 或 2026-05-30 14:00。",
                value_type="string",
                required=False,
            ),
            CommandParam(name="备注", description="可选备注详情。", value_type="string", required=False),
        ],
        tags={"todo", "write"},
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

query_todo_cmd = on_agent_command(
    Alconna(
        "查询待办",
        Args["status?", str, Field(default="", completion=lambda: "可选：待办/已完成/已取消/全部")],
        meta=CommandMeta(description="查询自己的待办；默认只看待处理，可按状态过滤。"),
    ),
    aliases={"查看待办", "待办列表", "我的待办"},
    binding=CommandBinding(
        roles={UserRole.user},
        scopes={HelperScope.user},
        risk_level="low",
        agent_callable=True,
        execution_mode="service",
        param_labels={"status": "状态"},
        param_descriptions={"status": "可选状态过滤：待办、已完成、已取消或全部。"},
        tags={"todo", "query"},
    ),
    priority=priority,
    block=True,
    auto_user_handler=True,
)


@create_todo_cmd.handle()
async def handle_create_todo_user_command(
    matcher: AlconnaMatcher,
    context: CommandUserContextDepends,
    title: str,
    rest: tuple[str, ...] | list[str] = (),
) -> None:
    """保留 Alconna 必填参数补全，同时复用统一 service 执行链。"""

    if not title:
        await matcher.finish("请输入待办标题")
    result = await command_executor.execute("创建待办", {"title": title, "rest": rest}, context)
    await send_command_result(matcher, result)


complete_todo_cmd = on_agent_command(
    Alconna(
        "完成待办",
        Args["todo_id", int, Field(completion=lambda: "请输入待办ID")],
        meta=CommandMeta(description="把指定待办标记为已完成。"),
    ),
    aliases={"标记完成", "待办完成"},
    binding=CommandBinding(
        roles={UserRole.user},
        scopes={HelperScope.user},
        risk_level="medium",
        agent_callable=True,
        execution_mode="service",
        param_labels={"todo_id": "待办ID"},
        param_descriptions={"todo_id": "要标记完成的待办 ID。"},
        tags={"todo", "write"},
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
    auto_user_handler=True,
)

delete_todo_cmd = on_agent_command(
    Alconna(
        "删除待办",
        Args["todo_id", int, Field(completion=lambda: "请输入待办ID")],
        meta=CommandMeta(description="删除自己的指定待办，删除后不可恢复。"),
    ),
    aliases={"移除待办"},
    binding=CommandBinding(
        roles={UserRole.user},
        scopes={HelperScope.user},
        risk_level="high",
        # 删除为不可恢复写操作，默认不开放给 Agent 自动调用，仅用户显式触发。
        agent_callable=False,
        execution_mode="service",
        param_labels={"todo_id": "待办ID"},
        param_descriptions={"todo_id": "要删除的待办 ID。"},
        tags={"todo", "write"},
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
    auto_user_handler=True,
)

__all__ = [
    "create_todo_cmd",
    "query_todo_cmd",
    "complete_todo_cmd",
    "delete_todo_cmd",
]
