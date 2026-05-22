from src.platform.commands import CommandBinding, on_agent_command
from src.platform.config import priority, comp_config
from src.platform.helper import HelperScope, UserRole
from src.platform.commands.schema import CommandParam
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
        description="查看当前文件空间路径。",
        ai_description="查看当前用户文件管理工作目录；外部群组、班级、学院、学校空间会以虚拟挂载目录展示。",
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
        description="列出当前目录或指定路径下的文件和目录。",
        ai_description="列出个人空间或已授权挂载空间。挂载空间以 群组/班级/学院/学校 分类展示，默认外部空间只读。",
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
        description="切换当前文件空间目录；cd .. 在根目录会固定停留在 ~。",
        ai_description="切换个人空间或挂载空间目录；路径必须保持在虚拟 ~ 内，不能越权进入其他用户或组织空间。",
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
        description="在当前可写文件空间内创建目录。",
        ai_description="只能在个人空间或当前用户具备管理权限的挂载空间中创建目录，普通外部挂载空间只读。",
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
        description="在当前可写文件空间内创建空文件；已存在文件不会被修改。",
        ai_description="只负责新增空文件，不会修改已有文件内容或更新时间；外部挂载空间需要管理权限才能写入。",
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
        description="删除当前文件空间内的文件；删除目录需要使用 -r。",
        ai_description="高风险命令。只能删除个人空间或有管理权限挂载空间中的文件，不能删除虚拟挂载分类或越权路径。",
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
        description="查看个人空间或授权挂载空间内文本文件的内容，单次最多展示前 4096 字节。",
        ai_description="可以读取个人空间和授权挂载空间内的文本文件；二进制文件不要使用该命令。",
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
        description="按名称或路径查找个人空间与授权挂载空间内的文件和目录。",
        ai_description="默认在当前虚拟路径覆盖范围内查找；在 ~ 下会覆盖个人空间与可访问的群组、班级、学院、学校挂载。",
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
        description="在个人空间与授权挂载空间内搜索文本文件内容。",
        ai_description="默认在当前虚拟路径覆盖范围内搜索小型文本文件内容，返回命中文件路径和行号。",
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
        description="查看个人空间与授权挂载空间组成的文件树。",
        ai_description="展示当前虚拟文件管理范围内的文件树，默认限制深度和条目数量以避免过大输出。",
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
        description="把消息中的附件保存到当前可写文件空间；可先写目标目录再附带文件。",
        ai_description="该命令依赖真实消息附件，Agent 不应直接调用；外部挂载目录需要管理权限才能保存。",
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

__helpers__ = [
    pwd_cmd.__helper__,
    ls_cmd.__helper__,
    cd_cmd.__helper__,
    mkdir_cmd.__helper__,
    touch_cmd.__helper__,
    rm_cmd.__helper__,
    cat_cmd.__helper__,
    find_cmd.__helper__,
    grep_cmd.__helper__,
    tree_cmd.__helper__,
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
    "find_cmd",
    "grep_cmd",
    "tree_cmd",
    "upload_file_cmd",
    "__helpers__",
]
