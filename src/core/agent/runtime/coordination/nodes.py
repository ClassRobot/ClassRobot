from __future__ import annotations

from typing import TYPE_CHECKING
from abc import ABC, abstractmethod

from nonebot import logger
from nonebot_plugin_alconna import UniMessage

from src.core.llm import LLMTaskType
from src.core.llm.util import json_loads
from src.core.agent.prompts import Prompt
from src.core.llm.message import LLMRole, Messages

from .state import PipelineState
from ..schema import AgentPlan, ChatMessage, IntentRoute, AutoTaskList

if TYPE_CHECKING:
    from ..pipeline import MessageProcessingPipeline


class WorkflowNode(ABC):
    """定义工作流节点的统一接口。"""

    @abstractmethod
    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        """执行当前节点逻辑。"""


class SummaryHistoryNode(WorkflowNode):
    """在会话过长时先压缩历史消息。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        pipeline.messages = await pipeline.summarize_history(pipeline.messages)


class NormalizeUserInputNode(WorkflowNode):
    """把平台原始消息转换为统一内容结构。"""

    def __init__(self, message: str | UniMessage | ChatMessage) -> None:
        self.message = message

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        state.user_content = pipeline.normalize_message(self.message)


class AppendUserMessageNode(WorkflowNode):
    """把当前用户消息写入会话。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        pipeline.messages.user_message(state.user_content)


class IntentRouteNode(WorkflowNode):
    """先判断消息类型，避免所有请求都进入重型规划链路。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None:
            return
        await pipeline.ensure_mcp_tools()
        route_tools = pipeline.select_route_command_tools(state.user_content)
        route_skills = pipeline.select_route_skill_summaries(state.user_content)
        route_prompt = await Prompt("intent_route").render(
            {
                "helpers": pipeline.helpers,
                "command_tools": pipeline.render_command_tools_prompt_from_tools(route_tools),
                "skill_catalog": pipeline.render_skill_catalog_prompt_from_summaries(route_skills),
                "mcp_tools": pipeline.render_mcp_tools_prompt(),
                "history": pipeline.serialize_recent_history(),
            }
        )
        route_messages = Messages()
        route_messages.extend(pipeline.messages.get(LLMRole.system))
        route_messages.system_message(route_prompt)
        # 图片消息要把原始多模态内容交给路由器，避免只看到 URL 文本。
        route_messages.user_message(state.user_content)
        multi_modal = pipeline.has_visual_input(state.user_content)
        response = await pipeline.create_llm_completion(
            route_messages,
            multi_modal=multi_modal,
            max_tokens=1024,
            task_type=LLMTaskType.vision if multi_modal else LLMTaskType.plan,
        )
        text = response.choices[0].message.content or "{}"
        try:
            state.intent_route = IntentRoute.parse_obj(json_loads(text))
        except Exception as error:
            preview = text.strip().replace("\n", "\\n")[:240]
            logger.warning(
                f'AutoGPT trace "{state.trace_id}" intent route parse failed: {error}; '
                f'fallback to complex_task; raw="{preview}"'
            )
            state.intent_route = IntentRoute(
                intent="complex_task",
                requires_command=True,
                reason="意图路由解析失败，降级到自动任务规划。",
            )
        logger.info(
            'AutoGPT trace "{}" routed intent="{}" requires_command={} requires_rag={}'.format(
                state.trace_id,
                state.intent_route.intent,
                state.intent_route.requires_command,
                state.intent_route.requires_rag,
            )
        )
        state.runtime_scene = pipeline.resolve_runtime_scene(state)
        pipeline.record_prompt_stage(
            "route",
            prompt_char_length=route_messages.char_length(),
            recalled_commands=[tool.command for tool in route_tools],
            recalled_skills=[item["name"] for item in route_skills],
        )
        progress_message = ""
        if not pipeline.should_direct_reply_from_vision(state.intent_route, state.user_content):
            progress_message = pipeline.build_user_progress_message(state.intent_route)
            if not progress_message and multi_modal:
                progress_message = "我先看一下图片或文件内容，请稍等~"
        await pipeline.report_progress(progress_message, stage="route")

        if state.intent_route.intent == "violation":
            state.runtime_scene = "violation"
            state.auto_tasks = AutoTaskList(
                reply=state.intent_route.reply or "用户发送的消息包含违规内容，已被屏蔽！",
                is_violation=True,
            )
        elif (
            not state.intent_route.requires_command
            and not pipeline.needs_external_knowledge(state.intent_route)
            and not pipeline.has_visual_input(state.user_content)
            and not pipeline.needs_local_knowledge(state.intent_route)
        ):
            state.auto_tasks = AutoTaskList(
                reply=state.intent_route.reply or "我在，有什么需要我帮你处理的吗？",
                need_confirm=state.intent_route.need_confirm,
            )


class DirectVisionReplyNode(WorkflowNode):
    """对无需命令和检索的简单图片问答直接给出最终回复。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None or state.intent_route is None:
            return
        if not pipeline.should_direct_reply_from_vision(state.intent_route, state.user_content):
            return

        reply_messages = Messages()
        reply_messages.extend(pipeline.messages.get(LLMRole.system))
        reply_messages.system_message(await Prompt("vision_reply").render())
        reply_messages.extend(pipeline.messages.get(LLMRole.user, LLMRole.assistant))

        response = await pipeline.create_llm_completion(
            reply_messages,
            multi_modal=True,
            max_tokens=2048,
            task_type=LLMTaskType.vision,
        )
        reply = (response.choices[0].message.content or "").strip()
        state.runtime_scene = "vision"
        state.auto_tasks = AutoTaskList(
            reply=reply
            or "我看到了这张图片，但还不能可靠判断具体内容，你可以发更清晰一点的图片或补一句你想让我看什么。",
            need_confirm=False,
        )


class RetrieveLocalKnowledgeNode(WorkflowNode):
    """按需检索聊天记录、文件空间和其他本地上下文。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None:
            return
        requests = pipeline.local_knowledge_source_requests(state.intent_route)
        if not requests:
            return
        await pipeline.report_progress("我正在按当前问题选择可用的历史记录和文件上下文。", stage="memory")
        state.local_knowledge = await pipeline.local_knowledge_retriever.retrieve_sources(
            requests,
            pipeline.runtime_context,
        )
        if state.local_knowledge:
            logger.info(f'AutoGPT trace "{state.trace_id}" loaded local knowledge context')


class ExtractContextNode(WorkflowNode):
    """从当前会话中抽取结构化上下文。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None:
            return
        await pipeline.report_progress("我正在提取这轮对话里的目标、约束和关键信息。", stage="extract")
        extract_agent = pipeline.create_extract_agent()
        extract_prompt = await Prompt("extract").render({"history": extract_agent.message_to_string(pipeline.messages)})
        extract_messages = Messages()
        extract_messages.system_message(extract_prompt)
        latest_user_context = extract_agent.latest_user_context(pipeline.messages)
        if latest_user_context is not None:
            extract_messages.user_message(latest_user_context.content)
        pipeline.record_prompt_stage("extract", prompt_char_length=extract_messages.char_length())
        state.extracted_context = await extract_agent.execute(pipeline.messages)


class PlannerNode(WorkflowNode):
    """把上下文转换成显式计划，再交给后续节点执行。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None or state.extracted_context is None:
            return
        await pipeline.report_progress("我正在把目标拆成可执行步骤，并确认需要哪些命令或技能。", stage="plan")
        await pipeline.ensure_mcp_tools()
        plan_tools = pipeline.select_plan_command_tools(state.extracted_context)
        plan_skills = pipeline.select_plan_skill_summaries(state.extracted_context)
        plan_prompt = await Prompt("agent_plan").render(
            {
                "helpers": pipeline.helpers,
                "command_tools": pipeline.render_command_tools_prompt_from_tools(plan_tools),
                "skill_catalog": pipeline.render_skill_catalog_prompt_from_summaries(plan_skills),
                "mcp_tools": pipeline.render_mcp_tools_prompt(),
                "route": state.intent_route.json(ensure_ascii=False) if state.intent_route else "{}",
                "context": state.extracted_context.single_modal(),
                "local_knowledge": state.local_knowledge,
                "history": pipeline.serialize_recent_history(),
            }
        )

        plan_messages = Messages()
        plan_messages.extend(pipeline.messages.get(LLMRole.system))
        plan_messages.system_message(plan_prompt)
        plan_input = (
            state.extracted_context.single_modal().strip()
            or pipeline.text_query_from_contents(state.user_content)
            or "请基于当前上下文生成结构化计划。"
        )
        plan_messages.user_message(plan_input)
        response = await pipeline.create_llm_completion(
            plan_messages,
            multi_modal=False,
            max_tokens=2048,
            task_type=LLMTaskType.plan,
        )
        text = response.choices[0].message.content or "{}"
        try:
            state.agent_plan = AgentPlan.parse_obj(json_loads(text))
        except Exception as error:
            logger.exception(f'AutoGPT trace "{state.trace_id}" planner parse failed: {error}')
            state.agent_plan = AgentPlan(
                goal=state.extracted_context.single_modal(),
                requires_command=bool(state.intent_route and state.intent_route.requires_command),
                requires_rag=bool(state.intent_route and state.intent_route.requires_rag),
                reason="计划解析失败，使用上下文和入口路由降级。",
            )
        logger.info(
            'AutoGPT trace "{}" planned requires_command={} should_execute={} risk_level="{}" candidates={}'.format(
                state.trace_id,
                state.agent_plan.requires_command,
                state.agent_plan.should_execute,
                state.agent_plan.risk_level,
                state.agent_plan.candidate_commands,
            )
        )
        pipeline.record_prompt_stage(
            "plan",
            prompt_char_length=plan_messages.char_length(),
            recalled_commands=[tool.command for tool in plan_tools],
            recalled_skills=[item["name"] for item in plan_skills],
            selected_commands=state.agent_plan.candidate_commands,
        )
        pipeline.record_planner_candidate_commands(state.agent_plan.candidate_commands)

        if state.agent_plan.confirmation_question or state.agent_plan.missing_info:
            state.auto_tasks = AutoTaskList(
                reply=state.agent_plan.confirmation_question
                or "还需要补充一些信息后才能继续：" + "、".join(state.agent_plan.missing_info),
                need_confirm=True,
            )


class ExecutionPolicyNode(WorkflowNode):
    """使用代码规则校验 Planner 输出，避免模型直接越权执行。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None or state.agent_plan is None:
            return

        plan = state.agent_plan
        if plan.risk_level == "high" and plan.requires_command:
            state.auto_tasks = AutoTaskList(
                reply=plan.confirmation_question or "这个操作风险较高，请确认是否继续执行。",
                need_confirm=True,
            )
            return

        if plan.requires_command and not plan.should_execute:
            state.auto_tasks = AutoTaskList(
                reply=plan.confirmation_question
                or "我还需要你确认执行条件后才能调用系统命令。"
                + (f" 缺少信息：{'、'.join(plan.missing_info)}" if plan.missing_info else ""),
                need_confirm=True,
            )
            return

        if plan.requires_command and not pipeline.resolve_candidate_commands(plan):
            state.auto_tasks = AutoTaskList(
                reply="我还不能确定要调用哪个项目命令，请再说明一下要执行的具体功能。",
                need_confirm=True,
            )
            return

        if plan.candidate_mcp_tools and not pipeline.resolve_candidate_mcp_tools(plan):
            state.auto_tasks = AutoTaskList(
                reply="我还不能确定要调用哪个 MCP 工具，请再说明一下要使用的外部能力。",
                need_confirm=True,
            )


class RetrieveKnowledgeNode(WorkflowNode):
    """根据抽取上下文获取补充知识。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None or not pipeline.should_retrieve(state.intent_route, state.agent_plan):
            return
        if state.extracted_context is None:
            return
        await pipeline.report_progress("我正在补充相关知识和上下文，用来支撑后续处理。", stage="rag")
        rag_context = await pipeline.create_rag_agent().execute(state.extracted_context)
        state.retrieved_knowledge = pipeline.format_external_knowledge_observation(
            rag_context,
            route=state.intent_route,
            fallback_query=state.extracted_context.single_modal(),
        )


class PlanTasksNode(WorkflowNode):
    """结合上下文、补充知识和命令清单生成最终规划。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is not None:
            return
        if state.extracted_context is None:
            return
        combined_knowledge = pipeline.combine_knowledge(state.local_knowledge, state.retrieved_knowledge)
        await pipeline.ensure_mcp_tools()
        task_tools = pipeline.select_task_command_tools(state.extracted_context, plan=state.agent_plan)
        task_skills = pipeline.select_task_skill_summaries(state.extracted_context, plan=state.agent_plan)
        task_prompt = await Prompt("auto_task").render(
            {
                "helpers": pipeline.helpers,
                "context": state.extracted_context.single_modal(),
                "knowledge": combined_knowledge,
                "plan": state.agent_plan.json(ensure_ascii=False) if state.agent_plan else None,
                "command_tools": pipeline.render_command_tools_prompt_from_tools(task_tools),
                "skill_catalog": pipeline.render_skill_catalog_prompt_from_summaries(task_skills),
                "mcp_tools": pipeline.render_mcp_tools_prompt(
                    tool_names=state.agent_plan.candidate_mcp_tools if state.agent_plan else None
                ),
            }
        )
        task_messages = Messages()
        task_messages.extend(pipeline.messages.get(LLMRole.system))
        task_messages.system_message(task_prompt)
        task_messages.user_message(state.extracted_context.content)
        state.auto_tasks = await pipeline.create_auto_task_agent(
            helpers=pipeline.helpers,
            messages=pipeline.messages,
            command_tools_prompt=pipeline.render_command_tools_prompt_from_tools(task_tools),
            skill_catalog_prompt=pipeline.render_skill_catalog_prompt_from_summaries(task_skills),
            mcp_tools_prompt=pipeline.render_mcp_tools_prompt(
                tool_names=state.agent_plan.candidate_mcp_tools if state.agent_plan else None
            ),
        ).execute(
            state.extracted_context,
            combined_knowledge,
            plan=state.agent_plan.json(ensure_ascii=False) if state.agent_plan else None,
        )
        pipeline.record_prompt_stage(
            "task",
            prompt_char_length=task_messages.char_length(),
            recalled_commands=[tool.command for tool in task_tools],
            recalled_skills=[item["name"] for item in task_skills],
            selected_commands=[task.command for task in state.auto_tasks.tasks],
        )


class ValidateAutoTasksNode(WorkflowNode):
    """校验 AutoTask 输出，确保任务仍在 Planner 和 Helper 允许范围内。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is None or not state.auto_tasks.tasks:
            return

        allowed_commands = pipeline.resolve_candidate_commands(state.agent_plan)
        allowed_mcp_tools = pipeline.resolve_candidate_mcp_tools(state.agent_plan)
        valid_tasks = []
        invalid_commands = []
        for task in state.auto_tasks.tasks:
            if task.task_type == "mcp_tool":
                if pipeline.mcp_tools.get(task.command) is None:
                    invalid_commands.append(task.command)
                    continue
                if allowed_mcp_tools and task.command not in allowed_mcp_tools:
                    invalid_commands.append(task.command)
                    continue
                valid_tasks.append(task)
                continue
            helper = pipeline.helpers.get_helper(task.command)
            if helper is None:
                invalid_commands.append(task.command)
                continue
            if allowed_commands and helper.command not in allowed_commands:
                invalid_commands.append(task.command)
                continue
            valid_tasks.append(task)

        state.auto_tasks.tasks = valid_tasks
        if invalid_commands and not valid_tasks:
            state.auto_tasks.reply = "计划中的命令不在当前可用能力范围内，请换一种说法或补充更明确的信息。"
            state.auto_tasks.need_confirm = True
        elif invalid_commands:
            state.auto_tasks.reply = (state.auto_tasks.reply or "") + "\n部分命令因不在当前计划或权限范围内，已跳过。"

        pipeline.record_final_hit_commands([task.command for task in valid_tasks])
        state.auto_tasks.reply = pipeline.normalize_auto_task_reply(
            state.intent_route,
            state.agent_plan,
            state.auto_tasks,
        )


class PersistAssistantReplyNode(WorkflowNode):
    """将结构化规划回写到会话历史，便于后续轮次继续引用。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is None:
            return
        pipeline.messages.assistant_message(pipeline.serialize_auto_task_result(state.auto_tasks))


RUNTIME_NODE_CLASS_REGISTRY: dict[str, type[WorkflowNode]] = {
    "summary_history": SummaryHistoryNode,
    "append_user_message": AppendUserMessageNode,
    "route": IntentRouteNode,
    "local_rag": RetrieveLocalKnowledgeNode,
    "direct_vision_reply": DirectVisionReplyNode,
    "extract": ExtractContextNode,
    "plan": PlannerNode,
    "execution_policy": ExecutionPolicyNode,
    "external_rag": RetrieveKnowledgeNode,
    "plan_tasks": PlanTasksNode,
    "validate_tasks": ValidateAutoTasksNode,
    "persist": PersistAssistantReplyNode,
}
