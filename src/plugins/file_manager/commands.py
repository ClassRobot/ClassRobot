from src.commands import CommandBinding, command_alconna
from utils.config import priority, comp_config
from utils.helper import HelperScope, UserRole
from src.commands.schema import CommandParam
from nonebot_plugin_alconna import Args, File, Field, Image, Other, Alconna, MultiVar

file_command_kwargs = {
    "priority": priority,
    "block": True,
    "skip_for_unmatch": False,
    "comp_config": comp_config,
}

pwd_cmd = command_alconna(
    Alconna("pwd"),
    aliases={"当前路径", "文件路径"},
    binding=CommandBinding(
        description="查看当前文件空间路径。",
        ai_description="查看当前用户或群组文件空间的工作目录，路径始终限制在 home 内。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage"},
        execution_mode="service",
    ),
    **file_command_kwargs,
)

ls_cmd = command_alconna(
    Alconna("ls", Args["path?", str | None, Field(default=None, completion="可选：要查看的路径")]),
    aliases={"查看文件", "文件列表"},
    binding=CommandBinding(
        description="列出当前目录或指定路径下的文件和目录。",
        ai_description="只能查看当前用户或群组自己的 home 空间，不能读取其他空间路径。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage"},
        execution_mode="service",
        param_labels={"path": "路径"},
    ),
    **file_command_kwargs,
)

cd_cmd = command_alconna(
    Alconna("cd", Args["path?", str | None, Field(default=None, completion="可选：目标目录")]),
    aliases={"进入目录", "切换目录"},
    binding=CommandBinding(
        description="切换当前文件空间目录；cd .. 在根目录会固定停留在 ~。",
        ai_description="切换工作目录时必须保持在当前用户或群组 home 内，越界路径会被钳制或拒绝。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage"},
        execution_mode="service",
        param_labels={"path": "路径"},
    ),
    **file_command_kwargs,
)

mkdir_cmd = command_alconna(
    Alconna("mkdir", Args["path", str, Field(completion="请输入要创建的目录路径")]),
    aliases={"创建目录"},
    binding=CommandBinding(
        description="在当前文件空间内创建目录。",
        ai_description="只能在当前用户或群组 home 内创建目录，不能使用越界路径。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage"},
        risk_level="medium",
        execution_mode="service",
        param_labels={"path": "路径"},
    ),
    **file_command_kwargs,
)

touch_cmd = command_alconna(
    Alconna("touch", Args["path", str, Field(completion="请输入要创建的空文件路径")]),
    aliases={"创建文件"},
    binding=CommandBinding(
        description="在当前文件空间内创建空文件；已存在文件不会被修改。",
        ai_description="只负责新增空文件，不会修改已有文件内容或更新时间。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage"},
        risk_level="medium",
        execution_mode="service",
        param_labels={"path": "路径"},
    ),
    **file_command_kwargs,
)

rm_cmd = command_alconna(
    Alconna("rm", Args["rm_args", MultiVar(str, "+"), Field(completion="例如：rm 文件名 或 rm -r 目录")]),
    aliases={"删除文件"},
    binding=CommandBinding(
        description="删除当前文件空间内的文件；删除目录需要使用 -r。",
        ai_description="高风险命令。必须确认路径属于当前用户或群组 home，不能删除默认根目录和默认分类目录。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage"},
        risk_level="high",
        execution_mode="service",
        params=[
            CommandParam(
                name="参数",
                description="删除参数，例如 文件名、-r 目录、-f 文件名。",
                multiple=True,
                source_name="rm_args",
            )
        ],
    ),
    **file_command_kwargs,
)

cat_cmd = command_alconna(
    Alconna("cat", Args["path", str, Field(completion="请输入要查看的文本文件路径")]),
    aliases={"查看文件内容"},
    binding=CommandBinding(
        description="查看当前文件空间内文本文件的内容，单次最多展示前 4096 字节。",
        ai_description="只能读取当前用户或群组 home 内的文本文件；二进制文件不要使用该命令。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage"},
        execution_mode="service",
        param_labels={"path": "路径"},
    ),
    **file_command_kwargs,
)

upload_file_cmd = command_alconna(
    Alconna(
        "上传文件",
        Args["upload_items", MultiVar(str | File | Image | Other, "+"), Field(completion="可选目标目录 + 文件")],
    ),
    aliases={"保存文件"},
    binding=CommandBinding(
        description="把消息中的附件保存到当前文件空间；可先写目标目录再附带文件。",
        ai_description="该命令依赖真实消息附件，Agent 不应直接调用。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage"},
        risk_level="medium",
        agent_callable=False,
        execution_mode="legacy_event",
        params=[
            CommandParam(
                name="文件参数",
                description="可选目标目录以及一个或多个消息附件。",
                multiple=True,
                source_name="upload_items",
            )
        ],
    ),
    **file_command_kwargs,
)

__helpers__ = [
    pwd_cmd.__helper__,
    ls_cmd.__helper__,
    cd_cmd.__helper__,
    mkdir_cmd.__helper__,
    touch_cmd.__helper__,
    rm_cmd.__helper__,
    cat_cmd.__helper__,
    upload_file_cmd.__helper__,
]

__all__ = [
    "pwd_cmd",
    "ls_cmd",
    "cd_cmd",
    "mkdir_cmd",
    "touch_cmd",
    "rm_cmd",
    "cat_cmd",
    "upload_file_cmd",
    "__helpers__",
]
