from .typings import ChatCompletionToolParam


class Functools:
    """封装函数工具调用时使用的上下文数据。"""

    def __init__(self):
        """初始化实例。"""
        self.functools: list[ChatCompletionToolParam] = []

    def add_function(self, name: str, description: str, parameters: dict):
        """添加function。

        参数:
            name (str): 名称。
            description (str): description。
            parameters (dict): parameters。
        """
        self.functools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            }
        )
