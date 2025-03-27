from strenum import StrEnum
from openai.types.chat.chat_completion import ChatCompletion as ChatCompletion  # noqa
from openai.types.chat.chat_completion_message import ChatCompletionMessage as ChatCompletionMessage  # noqa
from openai.types.chat.chat_completion_tool_param import ChatCompletionToolParam as ChatCompletionToolParam  # noqa
from openai.types.chat.chat_completion_message_param import (  # noqa
    ChatCompletionMessageParam as ChatCompletionMessageParam,
)
from openai.types.chat.chat_completion_message_tool_call import (  # noqa
    ChatCompletionMessageToolCall as ChatCompletionMessageToolCall,
)
from openai.types.chat.chat_completion_tool_choice_option_param import (  # noqa
    ChatCompletionToolChoiceOptionParam as ChatCompletionToolChoiceOptionParam,
)


class ContextType(StrEnum):
    agent = "agent"
    session = "session"


class AgentParamType(StrEnum):
    function = "function"
    messages = "messages"
