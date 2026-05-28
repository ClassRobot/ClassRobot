from src.platform.commands.schema import CommandParam
from src.platform.config import priority, comp_config
from src.platform.helper import UserRole, HelperScope
from src.platform.commands import CommandBinding, on_agent_command
from nonebot_plugin_alconna import Args, File, Field, Image, Other, Alconna, MultiVar

file_command_kwargs = {
    "priority": priority,
    "block": True,
    "skip_for_unmatch": False,
    "comp_config": comp_config,
}

pwd_cmd = on_agent_command(
    Alconna("pwd"),
    aliases={"当前路径", "文件路径"},
    binding=CommandBinding(
        description="查看当前文件空间路径，会显示个人空间和可访问挂载位置。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage"},
        execution_mode="service",
    ),
    **file_command_kwargs,
)

ls_cmd = on_agent_command(
    Alconna("ls", Args["path?", str | None, Field(default=None, completion="可选：要查看的路径")]),
    aliases={"查看文件", "文件列表"},
    binding=CommandBinding(
        description="列出当前目录或指定路径；可查看个人空间和授权挂载空间。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage"},
        execution_mode="service",
        param_labels={"path": "路径"},
    ),
    **file_command_kwargs,
)

cd_cmd = on_agent_command(
    Alconna("cd", Args["path?", str | None, Field(default=None, completion="可选：目标目录")]),
    aliases={"进入目录", "切换目录"},
    binding=CommandBinding(
        description="切换文件目录，路径始终限制在当前可访问空间内。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage"},
        execution_mode="service",
        param_labels={"path": "路径"},
    ),
    **file_command_kwargs,
)

mkdir_cmd = on_agent_command(
    Alconna("mkdir", Args["path", str, Field(completion="请输入要创建的目录路径")]),
    aliases={"创建目录"},
    binding=CommandBinding(
        description="在个人空间或有管理权限的挂载空间中创建目录。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage"},
        risk_level="medium",
        execution_mode="service",
        param_labels={"path": "路径"},
    ),
    **file_command_kwargs,
)

touch_cmd = on_agent_command(
    Alconna("touch", Args["path", str, Field(completion="请输入要创建的空文件路径")]),
    aliases={"创建文件"},
    binding=CommandBinding(
        description="在可写空间中创建空文件；不会修改已有文件内容。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage"},
        risk_level="medium",
        execution_mode="service",
        param_labels={"path": "路径"},
    ),
    **file_command_kwargs,
)

rm_cmd = on_agent_command(
    Alconna("rm", Args["rm_args", MultiVar(str, "+"), Field(completion="例如：rm 文件名 或 rm -r 目录")]),
    aliases={"删除文件"},
    binding=CommandBinding(
        description="删除可写空间内的文件；删除目录需要使用 -r。",
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

cat_cmd = on_agent_command(
    Alconna("cat", Args["path", str, Field(completion="请输入要查看的文本文件路径")]),
    aliases={"查看文件内容"},
    binding=CommandBinding(
        description="查看可访问文本文件内容，单次最多展示前 4096 字节。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage"},
        execution_mode="service",
        param_labels={"path": "路径"},
    ),
    **file_command_kwargs,
)

find_cmd = on_agent_command(
    Alconna(
        "find",
        Args[
            "pattern",
            str,
            Field(completion="请输入要查找的文件名关键词"),
        ]["path?", str | None, Field(default=None, completion="可选：从哪个目录开始查找")],
    ),
    aliases={"查找文件", "搜索文件名"},
    binding=CommandBinding(
        description="按文件名或路径关键词查找个人空间和授权挂载空间。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage", "search"},
        execution_mode="service",
        param_labels={"pattern": "关键词", "path": "路径"},
        param_descriptions={
            "pattern": "文件名或路径关键词。",
            "path": "可选搜索起点，默认当前目录。",
        },
    ),
    **file_command_kwargs,
)

grep_cmd = on_agent_command(
    Alconna(
        "grep",
        Args[
            "keyword",
            str,
            Field(completion="请输入要搜索的文本关键词"),
        ]["path?", str | None, Field(default=None, completion="可选：文件或目录路径")],
    ),
    aliases={"搜索内容", "全文搜索"},
    binding=CommandBinding(
        description="在可访问的小型文本文件中搜索关键词并返回命中位置。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage", "search"},
        execution_mode="service",
        param_labels={"keyword": "关键词", "path": "路径"},
        param_descriptions={
            "keyword": "需要搜索的文本关键词。",
            "path": "可选搜索起点，可以是文件或目录，默认当前目录。",
        },
    ),
    **file_command_kwargs,
)

tree_cmd = on_agent_command(
    Alconna(
        "tree",
        Args[
            "path?",
            str | None,
            Field(default=None, completion="可选：要展示的目录路径"),
        ]["max_depth?", int | None, Field(default=None, completion="可选：展示深度，默认 3")],
    ),
    aliases={"文件树"},
    binding=CommandBinding(
        description="查看个人空间和授权挂载空间的文件树，默认限制深度。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage", "search"},
        execution_mode="service",
        param_labels={"path": "路径", "max_depth": "深度"},
        param_descriptions={
            "path": "可选目录路径，默认当前目录。",
            "max_depth": "可选展示深度，默认 3，最大 8。",
        },
    ),
    **file_command_kwargs,
)

upload_file_cmd = on_agent_command(
    Alconna(
        "上传文件",
        Args["upload_items", MultiVar(str | File | Image | Other, "+"), Field(completion="可选目标目录 + 文件")],
    ),
    aliases={"保存文件"},
    binding=CommandBinding(
        description="把消息附件保存到当前可写空间；可先写目标目录再附带文件。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        tags={"file", "storage"},
        risk_level="medium",
        agent_callable=False,
        execution_mode="matcher",
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

__all__ = [
    "pwd_cmd",
    "ls_cmd",
    "cd_cmd",
    "mkdir_cmd",
    "touch_cmd",
    "rm_cmd",
    "cat_cmd",
    "find_cmd",
    "grep_cmd",
    "tree_cmd",
    "upload_file_cmd",
]
