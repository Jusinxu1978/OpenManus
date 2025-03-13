# 导入必要的模块
import time  # 时间处理
from typing import Dict, List, Optional  # 类型注解

from pydantic import Field, model_validator  # 数据验证和设置管理

# 导入自定义模块
from app.agent.toolcall import ToolCallAgent  # 工具调用代理基类
from app.logger import logger  # 日志记录器
from app.prompt.planning import NEXT_STEP_PROMPT, PLANNING_SYSTEM_PROMPT  # 提示模板
from app.schema import Message, TOOL_CHOICE_TYPE, ToolCall, ToolChoice  # 数据模型
from app.tool import PlanningTool, Terminate, ToolCollection  # 工具集合


class PlanningAgent(ToolCallAgent):
    """
    一个创建和管理计划以解决任务的代理。

    该代理使用计划工具来创建和管理结构化计划，
    并通过各个步骤跟踪进度，直到任务完成。
    """

    name: str = "planning"  # 代理名称
    description: str = "An agent that creates and manages plans to solve tasks"  # 代理描述

    system_prompt: str = PLANNING_SYSTEM_PROMPT  # 系统提示模板
    next_step_prompt: str = NEXT_STEP_PROMPT  # 下一步提示模板

    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(PlanningTool(), Terminate())  # 可用工具集合
    )
    tool_choices: TOOL_CHOICE_TYPE = ToolChoice.AUTO # type: ignore  # 工具选择模式
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])  # 特殊工具名称列表

    tool_calls: List[ToolCall] = Field(default_factory=list)  # 工具调用记录
    active_plan_id: Optional[str] = Field(default=None)  # 当前活动计划ID

    # 用于跟踪每个工具调用的步骤状态
    step_execution_tracker: Dict[str, Dict] = Field(default_factory=dict)  # 步骤执行跟踪器
    current_step_index: Optional[int] = None  # 当前步骤索引

    max_steps: int = 20  # 最大步骤数

    @model_validator(mode="after")
    def initialize_plan_and_verify_tools(self) -> "PlanningAgent":
        """
        初始化代理并验证所需工具。

        该方法会：
        1. 生成默认的计划ID
        2. 验证planning工具是否存在，如果不存在则添加
        3. 返回初始化后的代理实例
        """
        self.active_plan_id = f"plan_{int(time.time())}"  # 使用时间戳生成唯一计划ID

        if "planning" not in self.available_tools.tool_map:  # 检查planning工具是否存在
            self.available_tools.add_tool(PlanningTool())  # 如果不存在则添加

        return self  # 返回初始化后的实例

    async def think(self) -> bool:
        """
        根据当前计划状态决定下一步行动。

        该方法会：
        1. 根据当前计划状态生成提示信息
        2. 获取当前步骤索引
        3. 调用父类think方法进行决策
        4. 如果决定执行工具，则记录工具调用与当前步骤的关联

        返回:
            bool: 是否成功做出决策
        """
        prompt = (
            f"CURRENT PLAN STATUS:\n{await self.get_plan()}\n\n{self.next_step_prompt}"
            if self.active_plan_id  # 如果有活动计划，添加当前计划状态
            else self.next_step_prompt  # 否则只使用下一步提示
        )
        self.messages.append(Message.user_message(prompt))  # 将提示信息添加到消息列表

        # 在思考前获取当前步骤索引
        self.current_step_index = await self._get_current_step_index()

        result = await super().think()  # 调用父类think方法进行决策

        # 如果决定执行工具且不是planning工具或特殊工具，将其与当前步骤关联
        if result and self.tool_calls:
            latest_tool_call = self.tool_calls[0]  # 获取最新的工具调用
            if (
                latest_tool_call.function.name != "planning"
                and latest_tool_call.function.name not in self.special_tool_names
                and self.current_step_index is not None
            ):
                self.step_execution_tracker[latest_tool_call.id] = {
                    "step_index": self.current_step_index,  # 记录步骤索引
                    "tool_name": latest_tool_call.function.name,  # 记录工具名称
                    "status": "pending",  # 初始状态为pending
                }

        return result  # 返回决策结果

    async def act(self) -> str:
        """
        执行一个步骤并跟踪其完成状态。

        该方法会：
        1. 调用父类act方法执行工具
        2. 如果工具调用存在，更新执行状态为"completed"
        3. 如果工具不是planning或特殊工具，更新计划状态

        返回:
            str: 工具执行结果
        """
        result = await super().act()  # 调用父类act方法执行工具

        # 执行工具后更新计划状态
        if self.tool_calls:
            latest_tool_call = self.tool_calls[0]

            # 如果工具调用在跟踪器中，更新状态为completed
            if latest_tool_call.id in self.step_execution_tracker:
                self.step_execution_tracker[latest_tool_call.id]["status"] = "completed"
                self.step_execution_tracker[latest_tool_call.id]["result"] = result

                # 如果工具不是planning或特殊工具，更新计划状态
                if (
                    latest_tool_call.function.name != "planning"
                    and latest_tool_call.function.name not in self.special_tool_names
                ):
                    await self.update_plan_status(latest_tool_call.id)

        return result  # 返回执行结果

    async def get_plan(self) -> str:
        """
        获取当前计划状态。

        该方法会：
        1. 检查是否存在活动计划
        2. 如果存在活动计划，则通过planning工具获取计划内容
        3. 返回计划内容或提示信息

        返回:
            str: 当前计划状态或提示信息
        """
        if not self.active_plan_id:  # 检查是否有活动计划
            return "No active plan. Please create a plan first."  # 如果没有活动计划返回提示

        result = await self.available_tools.execute(  # 通过planning工具获取计划内容
            name="planning",
            tool_input={"command": "get", "plan_id": self.active_plan_id},
        )
        return result.output if hasattr(result, "output") else str(result)  # 返回计划内容

    async def run(self, request: Optional[str] = None) -> str:
        """
        运行代理，可选择提供初始请求。

        该方法会：
        1. 如果提供了初始请求，则创建初始计划
        2. 调用父类run方法执行代理
        3. 返回执行结果

        参数:
            request (Optional[str]): 可选的初始请求内容

        返回:
            str: 代理执行结果
        """
        if request:  # 如果有初始请求
            await self.create_initial_plan(request)  # 创建初始计划
        return await super().run()  # 调用父类run方法执行代理

    async def update_plan_status(self, tool_call_id: str) -> None:
        """
        根据完成的工具执行更新当前计划进度。

        该方法会：
        1. 检查是否存在活动计划
        2. 验证工具调用是否在跟踪器中
        3. 确认工具是否成功完成
        4. 如果以上条件都满足，则通过planning工具标记步骤为完成

        参数:
            tool_call_id (str): 要更新的工具调用ID
        """
        if not self.active_plan_id:  # 检查是否有活动计划
            return

        if tool_call_id not in self.step_execution_tracker:  # 检查工具调用是否在跟踪器中
            logger.warning(f"No step tracking found for tool call {tool_call_id}")
            return

        tracker = self.step_execution_tracker[tool_call_id]  # 获取跟踪器记录
        if tracker["status"] != "completed":  # 检查工具是否成功完成
            logger.warning(f"Tool call {tool_call_id} has not completed successfully")
            return

        step_index = tracker["step_index"]  # 获取步骤索引

        try:
            # 通过planning工具标记步骤为完成
            await self.available_tools.execute(
                name="planning",
                tool_input={
                    "command": "mark_step",
                    "plan_id": self.active_plan_id,
                    "step_index": step_index,
                    "step_status": "completed",
                },
            )
            logger.info(
                f"Marked step {step_index} as completed in plan {self.active_plan_id}"
            )
        except Exception as e:
            logger.warning(f"Failed to update plan status: {e}")

    async def _get_current_step_index(self) -> Optional[int]:
        """
        解析当前计划以识别第一个未完成步骤的索引。

        该方法会：
        1. 检查是否存在活动计划
        2. 解析计划内容，找到"Steps:"行
        3. 查找第一个标记为未完成（[ ]）或进行中（[→]）的步骤
        4. 将找到的步骤标记为进行中
        5. 返回步骤索引，如果未找到则返回None

        返回:
            Optional[int]: 当前步骤的索引，如果未找到则返回None
        """
        if not self.active_plan_id:  # 检查是否有活动计划
            return None

        plan = await self.get_plan()  # 获取当前计划内容

        try:
            plan_lines = plan.splitlines()  # 将计划内容按行分割
            steps_index = -1

            # 查找"Steps:"行的索引
            for i, line in enumerate(plan_lines):
                if line.strip() == "Steps:":
                    steps_index = i
                    break

            if steps_index == -1:  # 如果没有找到Steps行
                return None

            # 查找第一个未完成或进行中的步骤
            for i, line in enumerate(plan_lines[steps_index + 1 :], start=0):
                if "[ ]" in line or "[→]" in line:  # 未开始或进行中
                    # 将当前步骤标记为进行中
                    await self.available_tools.execute(
                        name="planning",
                        tool_input={
                            "command": "mark_step",
                            "plan_id": self.active_plan_id,
                            "step_index": i,
                            "step_status": "in_progress",
                        },
                    )
                    return i  # 返回步骤索引

            return None  # 没有找到活动步骤
        except Exception as e:
            logger.warning(f"Error finding current step index: {e}")
            return None

    async def create_initial_plan(self, request: str) -> None:
        """
        根据请求创建初始计划。

        该方法会：
        1. 记录创建初始计划的日志
        2. 将请求信息添加到内存中
        3. 调用LLM生成计划
        4. 如果成功创建计划，记录执行结果
        5. 如果创建失败，记录错误信息

        参数:
            request (str): 用于创建计划的请求内容
        """
        logger.info(f"Creating initial plan with ID: {self.active_plan_id}")  # 记录日志

        messages = [
            Message.user_message(
                f"Analyze the request and create a plan with ID {self.active_plan_id}: {request}"
            )
        ]
        self.memory.add_messages(messages)  # 将消息添加到内存

        response = await self.llm.ask_tool(  # 调用LLM生成计划
            messages=messages,
            system_msgs=[Message.system_message(self.system_prompt)],
            tools=self.available_tools.to_params(),
            tool_choice=ToolChoice.REQUIRED,
        )
        assistant_msg = Message.from_tool_calls(  # 将LLM响应转换为消息
            content=response.content, tool_calls=response.tool_calls
        )

        self.memory.add_message(assistant_msg)  # 将消息添加到内存

        plan_created = False
        for tool_call in response.tool_calls:  # 处理工具调用
            if tool_call.function.name == "planning":
                result = await self.execute_tool(tool_call)  # 执行planning工具
                logger.info(
                    f"Executed tool {tool_call.function.name} with result: {result}"
                )

                # 将工具响应添加到内存
                tool_msg = Message.tool_message(
                    content=result,
                    tool_call_id=tool_call.id,
                    name=tool_call.function.name,
                )
                self.memory.add_message(tool_msg)
                plan_created = True
                break

        if not plan_created:  # 如果未创建计划
            logger.warning("No plan created from initial request")
            tool_msg = Message.assistant_message(
                "Error: Parameter `plan_id` is required for command: create"
            )
            self.memory.add_message(tool_msg)


async def main():
    # 配置并运行代理
    agent = PlanningAgent(available_tools=ToolCollection(PlanningTool(), Terminate()))
    result = await agent.run("Help me plan a trip to the moon")
    print(result)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
