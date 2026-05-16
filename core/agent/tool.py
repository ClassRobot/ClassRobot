import json
import inspect
from enum import Enum
from types import UnionType
from collections.abc import Awaitable
from typing import Any, Union, Literal, Callable, TypeAlias, get_args, get_origin

from pydantic import BaseModel

from core.llm.typings import ChatCompletionToolParam
from core.llm.util import json_loads

JsonSchema: TypeAlias = dict[str, Any]
ToolValue: TypeAlias = str | int | float | bool | dict[str, Any] | list[Any] | BaseModel | None
ToolHandler: TypeAlias = Callable[..., ToolValue | Awaitable[ToolValue]]


class ToolExecutionError(Exception):
    """工具执行失败。"""


class AgentTool:
    """将 Python 函数包装为 OpenAI function calling 工具。

    `parameters` 是给模型看的 JSON Schema；`handler` 是真正执行的
    Python 函数。模型只负责产出工具名和 JSON 参数，实际副作用仍由
    本地函数控制。
    """

    def __init__(
        self,
        name: str,
        description: str,
        parameters: JsonSchema,
        handler: ToolHandler,
        model_param: str | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler
        self.model_param = model_param

    @classmethod
    def from_function(
        cls,
        func: ToolHandler,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> "AgentTool":
        """从函数签名和 docstring 自动生成工具定义。"""

        tool_name = name or func.__name__
        tool_description = description or inspect.getdoc(func) or tool_name
        parameters, model_param = build_tool_parameters(func)
        return cls(
            name=tool_name,
            description=tool_description,
            parameters=parameters,
            handler=func,
            model_param=model_param,
        )

    def as_openai_tool(self) -> ChatCompletionToolParam:
        """转换为 OpenAI 兼容的 tool 描述。"""

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def run(self, arguments: str | dict[str, Any]) -> str:
        """执行工具，并把返回值统一转换成字符串写回模型上下文。"""

        try:
            kwargs = json_loads(arguments) if isinstance(arguments, str) else arguments
            if not isinstance(kwargs, dict):
                raise ToolExecutionError("tool arguments must be a JSON object")
            if self.model_param:
                # 函数只有一个 Pydantic 入参时，让 Pydantic 负责校验和类型转换。
                annotation = inspect.signature(self.handler).parameters[self.model_param].annotation
                result = self.handler(annotation.parse_obj(kwargs))
            else:
                result = self.handler(**kwargs)
            if inspect.isawaitable(result):
                result = await result
            return stringify_tool_result(result)
        except Exception as error:
            raise ToolExecutionError(str(error)) from error


def tool(
    func: ToolHandler | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> AgentTool | Callable[[ToolHandler], AgentTool]:
    """把函数声明为智能体工具。"""

    def decorator(inner: ToolHandler) -> AgentTool:
        return AgentTool.from_function(inner, name=name, description=description)

    if func is None:
        return decorator
    return decorator(func)


def build_tool_parameters(func: ToolHandler) -> tuple[JsonSchema, str | None]:
    """根据函数签名生成 function calling 使用的 JSON Schema。

    返回值里的第二项用于记录“单个 Pydantic 参数”模式；这种模式下
    执行时需要先把模型给出的 JSON 对象解析成对应的 BaseModel。
    """

    signature = inspect.signature(func)
    params = [
        param
        for param in signature.parameters.values()
        if param.kind in {param.POSITIONAL_OR_KEYWORD, param.KEYWORD_ONLY}
    ]
    if len(params) == 1 and is_pydantic_model_annotation(params[0].annotation):
        # 复杂业务参数建议走 Pydantic，这样字段说明、必填项和校验都集中在模型里。
        return params[0].annotation.schema(), params[0].name

    properties: dict[str, JsonSchema] = {}
    required: list[str] = []
    for param in params:
        if param.default is inspect.Parameter.empty:
            required.append(param.name)
        schema = annotation_to_json_schema(param.annotation)
        if param.default is not inspect.Parameter.empty:
            schema["default"] = param.default
        properties[param.name] = schema
    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }, None


def is_pydantic_model_annotation(annotation: Any) -> bool:
    """判断类型标注是否是 Pydantic 模型类。"""

    return inspect.isclass(annotation) and issubclass(annotation, BaseModel)


def annotation_to_json_schema(annotation: Any) -> JsonSchema:
    """把常见 Python 类型标注转换成足够模型使用的 JSON Schema。"""

    if annotation is inspect.Parameter.empty or annotation is Any:
        return {"type": "string"}
    if is_pydantic_model_annotation(annotation):
        return annotation.schema()

    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in {Union, UnionType}:
        # 支持 `str | None`、`Union[int, str]` 等常见写法。
        nullable = type(None) in args
        schemas = [annotation_to_json_schema(arg) for arg in args if arg is not type(None)]
        union_schema: JsonSchema = schemas[0] if len(schemas) == 1 else {"anyOf": schemas}
        if nullable:
            union_schema["nullable"] = True
        return union_schema
    if origin is Literal:
        # Literal 会转成 enum，能明显减少模型乱填参数的概率。
        values = list(args)
        literal_schema: JsonSchema = annotation_to_json_schema(type(values[0])) if values else {"type": "string"}
        literal_schema["enum"] = values
        return literal_schema
    if origin in {list, tuple, set}:
        item_schema: JsonSchema = annotation_to_json_schema(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": item_schema}
    if origin is dict:
        return {"type": "object"}
    if inspect.isclass(annotation) and issubclass(annotation, Enum):
        values = [item.value for item in annotation]
        enum_schema: JsonSchema = annotation_to_json_schema(type(values[0])) if values else {"type": "string"}
        enum_schema["enum"] = values
        return enum_schema

    mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        dict: "object",
        list: "array",
    }
    return {"type": mapping.get(annotation, "string")}


def stringify_tool_result(result: Any) -> str:
    """把工具返回值转成适合放入 tool 消息的文本。"""

    if isinstance(result, str):
        return result
    if isinstance(result, BaseModel):
        return result.json(ensure_ascii=False)
    return json.dumps(result, ensure_ascii=False, default=str)
