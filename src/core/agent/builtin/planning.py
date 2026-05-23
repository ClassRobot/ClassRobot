from nonebot import logger

from pydantic import Field

from src.platform.helper.schema import Helpers
from src.core.agent.prompts import Prompt
from src.core.llm import LLMTaskType, client_create
from src.core.agent.runtime.auto_task import AutoTaskList
from src.core.llm.message import Context, LLMRole, Messages

from ..base import BaseAgent, BaseAgentConfig


class AutoTaskAgentConfig(BaseAgentConfig):
    """自动任务规划 Agent 的运行配置。"""

    command_tools_prompt: str = ""
    skill_catalog_prompt: str = ""
    llm_name: str | None = None


class AutoTaskAgent(BaseAgent):
    """负责结合帮助信息和聊天上下文生成自动任务建议。"""

    agent_name = "auto_task_agent"
    display_name = "自动任务规划智能体"
    capabilities = ("task_planning", "command_selection", "skill_selection")
    config: AutoTaskAgentConfig = Field(default_factory=AutoTaskAgentConfig)
    helpers: Helpers = Field(default_factory=Helpers)

    @property
    def command_tools_prompt(self) -> str:
        """返回命令工具目录摘要。"""

        return self.config.command_tools_prompt

    @property
    def skill_catalog_prompt(self) -> str:
        """返回 Skill 摘要目录。"""

        return self.config.skill_catalog_prompt

    async def execute(
        self,
        context: Context,
        knowledge: str | None = None,
        plan: str | None = None,
    ) -> AutoTaskList:
        """根据抽取上下文与补充知识生成最终任务规划结果。

        Args:
            context: 由抽取智能体生成的结构化上下文。
            knowledge: 检索补充知识。
            plan: 显式 Planner 生成的结构化计划。

        Returns:
            AutoTaskList: 模型生成并解析后的任务规划结果。
        """
        planning_messages = Messages()
        planning_messages.extend(self.messages.get(LLMRole.system))
        planning_messages.system_message(
            await Prompt("auto_task").render(
                {
                    "helpers": self.helpers,
                    "context": context.single_modal(),
                    "knowledge": knowledge,
                    "plan": plan,
                    "command_tools": self.command_tools_prompt,
                    "skill_catalog": self.skill_catalog_prompt,
                }
            )
        )
        planning_messages.user_message(context.content)
        logger.debug(planning_messages)
        response = await client_create(
            planning_messages,
            multi_modal=not context.text_only(),
            task_type=LLMTaskType.vision if not context.text_only() else LLMTaskType.plan,
            llm_name=self.config.llm_name,
        )
        return AutoTaskList.parse_str(response.choices[0].message.content or "")
