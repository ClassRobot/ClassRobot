from .typings import ChatCompletionToolParam


class Functools:
    def __init__(self):
        self.functools: list[ChatCompletionToolParam] = []

    def add_function(self, name: str, description: str, parameters: dict):
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
