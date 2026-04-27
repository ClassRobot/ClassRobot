from strenum import StrEnum
from openai.types.chat.chat_completion import ChatCompletion as ChatCompletion  # noqa
from openai.types.chat.chat_completion_message import ChatCompletionMessage as ChatCompletionMessage  # noqa
from openai.types.chat.chat_completion_tool_param import ChatCompletionToolParam as ChatCompletionToolParam  # noqa
from openai.types.chat.chat_completion_message_param import (
    ChatCompletionMessageParam as ChatCompletionMessageParam,
)  # noqa
from openai.types.chat.chat_completion_message_tool_call import (  # noqa
    ChatCompletionMessageToolCall as ChatCompletionMessageToolCall,
)
from openai.types.chat.chat_completion_tool_choice_option_param import (  # noqa
    ChatCompletionToolChoiceOptionParam as ChatCompletionToolChoiceOptionParam,
)


class ContextType(StrEnum):
    """定义对话上下文片段的类型枚举值。"""

    agent = "agent"
    session = "session"


class AgentParamType(StrEnum):
    """定义智能体参数支持的类型枚举值。"""

    function = "function"
    messages = "messages"
