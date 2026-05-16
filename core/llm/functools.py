from .typings import ChatCompletionToolParam


class Functools:
    """封装函数工具调用时使用的上下文数据。"""

    def __init__(self) -> None:
        self.functools: list[ChatCompletionToolParam] = []

    def add_function(self, name: str, description: str, parameters: dict) -> None:
        """添加 function calling 工具定义。"""

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
