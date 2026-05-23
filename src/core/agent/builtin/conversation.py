import json

from nonebot import logger

from src.core.llm.util import json_loads
from src.core.agent.prompts import Prompt
from src.core.llm import LLMTaskType, client_create
from src.core.llm.message import Context, LLMRole, Messages

from pydantic import Field

from ..base import BaseAgent, BaseAgentConfig


class LLMAgentConfig(BaseAgentConfig):
    """基础对话 Agent 的运行配置。"""

    llm_name: str | None = None


class SummaryAgentConfig(BaseAgentConfig):
    """会话历史压缩 Agent 的运行配置。"""

    max_chars: int = 20480
    llm_name: str | None = None


class ExtractAgentConfig(BaseAgentConfig):
    """上下文抽取 Agent 的运行配置。"""

    llm_name: str | None = None


class ExecutionReplyAgentConfig(BaseAgentConfig):
    """命令观察结果最终回复 Agent 的运行配置。"""

    llm_name: str | None = None
    max_raw_output_chars: int = 1200


class LLMAgent(BaseAgent):
    """负责协调大模型对话与工具调用流程的智能体。"""

    agent_name = "llm_agent"
    display_name = "基础对话智能体"
    capabilities = ("chat", "tool_handoff")
    config: LLMAgentConfig = Field(default_factory=LLMAgentConfig)

    async def execute(self, messages: Messages) -> Messages:
        """执行当前逻辑。

        Args:
            messages: 消息列表。

        Returns:
            Messages: 返回处理结果。
        """
        if messages[-1].role == LLMRole.assistant:
            return messages
        response = await client_create(
            messages,
            self.functions(),
            multi_modal=False,
            task_type=LLMTaskType.tool,
            llm_name=self.config.llm_name,
        )
        if response.choices[0].message.tool_calls:
            messages.add_tool(response.choices[0].message)
        else:
            messages.assistant_message(response.choices[0].message.content or "")
        return messages


class SummaryAgent(BaseAgent):
    """负责在会话过长时压缩历史对话，控制上下文长度。"""

    agent_name = "summary_agent"
    display_name = "会话压缩智能体"
    capabilities = ("history_summary", "context_compaction")
    config: SummaryAgentConfig = Field(default_factory=SummaryAgentConfig)

    @property
    def max_chars(self) -> int:
        """返回触发历史压缩的字符阈值。"""

        return self.config.max_chars

    async def execute(self, messages: Messages) -> Messages:
        """在消息过长时生成历史摘要并替换旧对话。

        Args:
            messages: 当前会话的消息集合。

        Returns:
            Messages: 可能已被摘要压缩过的消息集合。
        """
        message_chars = messages.char_length()
        logger.debug(f"{self.name()} message_chars={message_chars}")
        if message_chars > self.max_chars:
            system_message = messages.get(LLMRole.system)
            summary_message = messages.get(LLMRole.user, LLMRole.assistant)
            summary_message.user_message("针对之前的聊天内容进行总结,总结长度不超过<4000字.")
            response = await client_create(
                summary_message,
                multi_modal=True,
                max_tokens=4096,
                task_type=LLMTaskType.summary,
                llm_name=self.config.llm_name,
            )
            summary_text = response.choices[0].message.content or ""
            # 保留系统提示，同时把长历史压缩成一条摘要，避免会话上下文无限增长。
            messages.clear()
            messages.extend(system_message)
            messages.assistant_message("# 历史聊天内容总结\n" + summary_text)
        return messages


class ExtractAgent(BaseAgent):
    """负责从聊天历史中提取结构化上下文，供检索与任务规划使用。"""

    agent_name = "extract_agent"
    display_name = "上下文抽取智能体"
    capabilities = ("context_extraction", "multimodal_extract")
    config: ExtractAgentConfig = Field(default_factory=ExtractAgentConfig)

    async def execute(self, messages: Messages):
        """将历史消息压缩为结构化上下文对象。

        Args:
            messages: 当前会话的消息集合。

        Returns:
            Context: 从历史消息中抽取出的结构化上下文。
        """
        logger.debug(self.name())
        extract = Prompt("extract")
        extract_messages = Messages()
        extract_messages.system_message(await extract.render({"history": self.message_to_string(messages)}))
        latest_user_context = self.latest_user_context(messages)
        multi_modal = latest_user_context is not None and not latest_user_context.text_only()
        if latest_user_context is not None:
            # 保留最后一条用户视觉消息作为原始输入，确保抽取阶段能直接看图。
            extract_messages.user_message(latest_user_context.content)
        response = await client_create(
            extract_messages,
            multi_modal=multi_modal,
            max_tokens=4096,
            task_type=LLMTaskType.vision if multi_modal else LLMTaskType.extract,
            llm_name=self.config.llm_name,
        )
        text = response.choices[0].message.content or ""
        logger.debug(text)
        return Context.parse_obj(json_loads(text))

    def message_to_string(self, messages: Messages) -> str:
        """将系统、用户和助手消息序列化为字符串。

        Args:
            messages: 当前会话的消息集合。

        Returns:
            str: 适合放入提示词中的 JSON 字符串。
        """
        message = messages.get(LLMRole.system, LLMRole.user, LLMRole.assistant)
        return message.json(ensure_ascii=False)

    @staticmethod
    def latest_user_context(messages: Messages) -> Context | None:
        """返回最近一条用户消息，供抽取阶段按需保留原始多模态输入。"""

        for message in reversed(messages.messages):
            if isinstance(message, Context) and message.role == LLMRole.user:
                return message
        return None


class ExecutionReplyAgent(BaseAgent):
    """把任务流观察结果整理成面向用户的最终自然语言回复。"""

    agent_name = "execution_reply_agent"
    display_name = "执行结果回复智能体"
    capabilities = ("observation_synthesis", "final_reply")
    config: ExecutionReplyAgentConfig = Field(default_factory=ExecutionReplyAgentConfig)

    async def execute(
        self,
        messages: Messages,
        *,
        workflow,
        observations: list,
        raw_outputs: list[str] | None = None,
    ) -> str:
        """基于任务流执行观察生成最终回复。"""

        prompt = await Prompt("execution_reply").render(
            {
                "workflow": json.dumps(workflow.dict(), ensure_ascii=False, default=str),
                "observations": json.dumps(
                    [observation.dict() for observation in observations],
                    ensure_ascii=False,
                    default=str,
                ),
                "raw_outputs": self.render_raw_outputs(raw_outputs or []),
            }
        )
        reply_messages = Messages()
        reply_messages.extend(messages.get(LLMRole.system))
        reply_messages.system_message(prompt)
        reply_messages.extend(messages.get(LLMRole.user, LLMRole.assistant))
        response = await client_create(
            reply_messages,
            multi_modal=False,
            max_tokens=2048,
            task_type=LLMTaskType.reply,
            llm_name=self.config.llm_name,
        )
        return (response.choices[0].message.content or "").strip()

    def render_raw_outputs(self, outputs: list[str]) -> str:
        """压缩原始输出，避免最终回复 Prompt 被大段命令文本淹没。"""

        text = "\n\n".join(output.strip() for output in outputs if output.strip())
        if len(text) <= self.config.max_raw_output_chars:
            return text
        return text[: self.config.max_raw_output_chars] + "\n...（原始输出已截断）"
