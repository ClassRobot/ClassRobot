from utils.llm.functools import Functools

functools = Functools()
functools.add_function(
    "get_command_help",
    "需要调用`命令列表`中存在的命令时候使用这个函数来获取命令的详细使用说明.",
    {"commands": "一个或多个需要查询的命令,多个命令使用逗号分隔,例如: 命令1,命令2."},
)
functools.add_function(
    "vision_model",
    "机器人视觉模型,分析上下文中，用户想要理解的哪些图片内容",
    {"urls": '格式如下: ["url1", "url2"]', "desc": "详细说明想从图片中识别的内容"},
)
functools.add_function(
    "file_model",
    "机器人文件模型,分析上下文中，用户想要理解的哪些文件内容",
    {"urls": '格式如下: ["url1", "url2"]', "desc": "详细说明想从文件中识别的内容"},
)
