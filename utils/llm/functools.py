from .typings import ChatCompletionToolParam


class Functools:
    def __init__(self):
        self.functools: list[ChatCompletionToolParam] = []

    def add_function(self, name: str, description: str, parameters: dict[str, str]):
        self.functools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {param: {"type": "string", "description": parameters[param]} for param in parameters},
                },
            }
        )
