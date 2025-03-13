# 导入必要的模块
from abc import ABC, abstractmethod  # 抽象基类，用于定义抽象方法
from contextlib import asynccontextmanager  # 异步上下文管理器，用于管理异步资源
from typing import List, Optional  # 类型注解，用于类型提示和检查

from pydantic import BaseModel, Field, model_validator  # 数据验证和模型管理，用于定义数据模型和验证规则

# 导入自定义模块
from app.llm import LLM  # 语言模型，用于与大型语言模型交互
from app.logger import logger  # 日志记录器，用于记录系统运行日志
from app.schema import AgentState, Memory, Message, ROLE_TYPE  # 数据模型，定义代理的核心数据结构


class BaseAgent(BaseModel, ABC):
    """管理代理状态和执行流程的抽象基类。

    提供状态转换、内存管理和基于步骤的执行循环的基础功能。
    子类必须实现`step`方法。
    """
    # 继承自BaseModel和ABC，结合了数据模型和抽象基类的特性
    # BaseModel提供数据验证和序列化功能
    # ABC用于定义抽象方法，强制子类实现

    # 核心属性
    name: str = Field(..., description="代理的唯一名称")  # 代理的标识符，必须唯一
    description: Optional[str] = Field(None, description="代理的可选描述")  # 代理的功能描述，可选

    # 提示模板
    system_prompt: Optional[str] = Field(
        None, description="系统级别的指令提示"  # 用于初始化代理行为的系统级提示
    )
    next_step_prompt: Optional[str] = Field(
        None, description="用于确定下一步操作的提示"  # 用于指导代理决策过程的步骤提示
    )

    # 依赖项
    llm: LLM = Field(default_factory=LLM, description="语言模型实例")  # 用于与语言模型交互的核心组件
    memory: Memory = Field(default_factory=Memory, description="代理的内存存储")  # 存储代理的对话历史和执行状态
    state: AgentState = Field(
        default=AgentState.IDLE, description="当前代理状态"  # 表示代理的当前运行状态（空闲、运行中、完成等）
    )

    # 执行控制
    max_steps: int = Field(default=10, description="终止前的最大步骤数")  # 限制代理的最大执行步骤，防止无限循环
    current_step: int = Field(default=0, description="当前执行步骤")  # 跟踪当前执行步骤的计数器

    duplicate_threshold: int = 2  # 重复检测阈值，用于判断代理是否陷入重复状态

    class Config:
        arbitrary_types_allowed = True  # 允许任意类型，提高类的灵活性
        extra = "allow"  # 允许子类添加额外字段，支持扩展

    @model_validator(mode="after")
    def initialize_agent(self) -> "BaseAgent":
        """如果未提供，使用默认设置初始化代理。"""
        # 检查并初始化LLM实例
        if self.llm is None or not isinstance(self.llm, LLM):
            self.llm = LLM(config_name=self.name.lower())  # 使用代理名称作为配置名创建LLM实例
        # 检查并初始化Memory实例
        if not isinstance(self.memory, Memory):
            self.memory = Memory()  # 创建默认的内存存储实例
        return self  # 返回初始化后的代理实例

    @asynccontextmanager
    async def state_context(self, new_state: AgentState):
        """用于安全代理状态转换的上下文管理器。

        Args:
            new_state: 在上下文中要转换到的新状态。

        Yields:
            None: 允许在新状态下执行。

        Raises:
            ValueError: 如果new_state无效。
        """
        # 验证新状态是否有效
        if not isinstance(new_state, AgentState):
            raise ValueError(f"无效状态: {new_state}")

        # 保存当前状态以便恢复
        previous_state = self.state
        # 设置新状态
        self.state = new_state
        try:
            yield  # 执行上下文中的代码
        except Exception as e:
            self.state = AgentState.ERROR  # 发生异常时转换到ERROR状态
            raise e  # 重新抛出异常
        finally:
            self.state = previous_state  # 无论是否发生异常，都恢复到之前的状态

    def update_memory(
        self,
        role: ROLE_TYPE, # type: ignore
        content: str,
        **kwargs,
    ) -> None:
        """向代理的内存中添加消息。

        Args:
            role: 消息发送者的角色（用户、系统、助手、工具）。
            content: 消息内容。
            **kwargs: 附加参数（例如工具消息的tool_call_id）。

        Raises:
            ValueError: 如果角色不受支持。
        """
        # 定义角色到消息工厂函数的映射
        message_map = {
            "user": Message.user_message,  # 用户消息工厂
            "system": Message.system_message,  # 系统消息工厂
            "assistant": Message.assistant_message,  # 助手消息工厂
            "tool": lambda content, **kw: Message.tool_message(content, **kw),  # 工具消息工厂
        }

        # 检查角色是否受支持
        if role not in message_map:
            raise ValueError(f"不支持的消息角色: {role}")

        # 获取对应的消息工厂函数
        msg_factory = message_map[role]
        # 创建消息对象，处理工具消息的特殊情况
        msg = msg_factory(content, **kwargs) if role == "tool" else msg_factory(content)
        # 将消息添加到内存中
        self.memory.add_message(msg)

    async def run(self, request: Optional[str] = None) -> str:
        """异步执行代理的主循环。

        Args:
            request: 要处理的初始用户请求（可选）。

        Returns:
             执行结果的摘要字符串。

        Raises:
            RuntimeError: 如果代理启动时不在IDLE状态。
        """
        # 检查代理是否处于可运行状态
        if self.state != AgentState.IDLE:
            raise RuntimeError(f"无法从状态运行代理: {self.state}")

        # 如果有初始请求，将其添加到内存中
        if request:
            self.update_memory("user", request)

        # 存储执行结果
        results: List[str] = []
        # 在RUNNING状态下执行主循环
        async with self.state_context(AgentState.RUNNING):
            # 循环执行步骤，直到达到最大步骤数或完成状态
            while (
                self.current_step < self.max_steps and self.state != AgentState.FINISHED
            ):
                self.current_step += 1  # 递增步骤计数器
                logger.info(f"执行步骤 {self.current_step}/{self.max_steps}")
                # 执行单个步骤
                step_result = await self.step()

                # 检查是否卡住，如果是则处理卡住状态
                if self.is_stuck():
                    self.handle_stuck_state()

                # 记录步骤结果
                results.append(f"步骤 {self.current_step}: {step_result}")

            # 如果达到最大步骤数，重置状态
            if self.current_step >= self.max_steps:
                self.current_step = 0
                self.state = AgentState.IDLE
                results.append(f"终止: 达到最大步骤数 ({self.max_steps})")

        # 返回所有步骤结果的汇总
        return "\n".join(results) if results else "未执行任何步骤"

    @abstractmethod
    async def step(self) -> str:
        """执行代理工作流中的单个步骤。

        必须由子类实现以定义具体行为。
        """
        # 这是一个抽象方法，强制子类实现具体的步骤逻辑
        # 每个步骤应返回一个字符串，描述该步骤的执行结果

    def handle_stuck_state(self):
        """通过添加提示来改变策略，处理卡住状态"""
        # 定义卡住状态的提示信息
        stuck_prompt = "\
        观察到重复响应。考虑新的策略，避免重复已经尝试过的无效路径。"
        # 将提示信息添加到下一步提示中
        self.next_step_prompt = f"{stuck_prompt}\n{self.next_step_prompt}"
        # 记录警告日志
        logger.warning(f"代理检测到卡住状态。添加提示: {stuck_prompt}")

    def is_stuck(self) -> bool:
        """通过检测重复内容检查代理是否卡在循环中"""
        # 如果消息数量不足，直接返回未卡住
        if len(self.memory.messages) < 2:
            return False

        # 获取最后一条消息
        last_message = self.memory.messages[-1]
        # 如果最后一条消息没有内容，返回未卡住
        if not last_message.content:
            return False

        # 计算相同内容的出现次数
        duplicate_count = sum(
            1
            for msg in reversed(self.memory.messages[:-1])  # 遍历除最后一条外的所有消息
            if msg.role == "assistant" and msg.content == last_message.content  # 匹配助手角色和相同内容
        )

        # 判断重复次数是否达到阈值
        return duplicate_count >= self.duplicate_threshold

    @property
    def messages(self) -> List[Message]:
        """从代理的内存中检索消息列表。"""
        # 返回内存中存储的所有消息
        return self.memory.messages

    @messages.setter
    def messages(self, value: List[Message]):
        """设置代理内存中的消息列表。"""
        # 直接替换内存中的消息列表
        self.memory.messages = value
        try:
            yield  # 执行上下文中的代码
        except Exception as e:
            self.state = AgentState.ERROR  # 发生异常时转换到ERROR状态
            raise e  # 重新抛出异常
        finally:
            self.state = previous_state  # 无论是否发生异常，都恢复到之前的状态

    def update_memory(
        self,
        role: ROLE_TYPE, # type: ignore
        content: str,
        **kwargs,
    ) -> None:
        """向代理的内存中添加消息。

        Args:
            role: 消息发送者的角色（用户、系统、助手、工具）。
            content: 消息内容。
            **kwargs: 附加参数（例如工具消息的tool_call_id）。

        Raises:
            ValueError: 如果角色不受支持。
        """
        # 定义角色到消息工厂函数的映射
        message_map = {
            "user": Message.user_message,  # 用户消息工厂
            "system": Message.system_message,  # 系统消息工厂
            "assistant": Message.assistant_message,  # 助手消息工厂
            "tool": lambda content, **kw: Message.tool_message(content, **kw),  # 工具消息工厂
        }

        # 检查角色是否受支持
        if role not in message_map:
            raise ValueError(f"不支持的消息角色: {role}")

        # 获取对应的消息工厂函数
        msg_factory = message_map[role]
        # 创建消息对象，处理工具消息的特殊情况
        msg = msg_factory(content, **kwargs) if role == "tool" else msg_factory(content)
        # 将消息添加到内存中
        self.memory.add_message(msg)

    async def run(self, request: Optional[str] = None) -> str:
        """异步执行代理的主循环。

        Args:
            request: 要处理的初始用户请求（可选）。

        Returns:
             执行结果的摘要字符串。

        Raises:
            RuntimeError: 如果代理启动时不在IDLE状态。
        """
        # 检查代理是否处于可运行状态
        if self.state != AgentState.IDLE:
            raise RuntimeError(f"无法从状态运行代理: {self.state}")

        # 如果有初始请求，将其添加到内存中
        if request:
            self.update_memory("user", request)

        # 存储执行结果
        results: List[str] = []
        # 在RUNNING状态下执行主循环
        async with self.state_context(AgentState.RUNNING):
            # 循环执行步骤，直到达到最大步骤数或完成状态
            while (
                self.current_step < self.max_steps and self.state != AgentState.FINISHED
            ):
                self.current_step += 1  # 递增步骤计数器
                logger.info(f"执行步骤 {self.current_step}/{self.max_steps}")
                # 执行单个步骤
                step_result = await self.step()

                # 检查是否卡住，如果是则处理卡住状态
                if self.is_stuck():
                    self.handle_stuck_state()

                # 记录步骤结果
                results.append(f"步骤 {self.current_step}: {step_result}")

            # 如果达到最大步骤数，重置状态
            if self.current_step >= self.max_steps:
                self.current_step = 0
                self.state = AgentState.IDLE
                results.append(f"终止: 达到最大步骤数 ({self.max_steps})")

        # 返回所有步骤结果的汇总
        return "\n".join(results) if results else "未执行任何步骤"

    @abstractmethod
    async def step(self) -> str:
        """执行代理工作流中的单个步骤。

        必须由子类实现以定义具体行为。
        """
        # 这是一个抽象方法，强制子类实现具体的步骤逻辑
        # 每个步骤应返回一个字符串，描述该步骤的执行结果

    def handle_stuck_state(self):
        """通过添加提示来改变策略，处理卡住状态"""
        # 定义卡住状态的提示信息
        stuck_prompt = "\
        观察到重复响应。考虑新的策略，避免重复已经尝试过的无效路径。"
        # 将提示信息添加到下一步提示中
        self.next_step_prompt = f"{stuck_prompt}\n{self.next_step_prompt}"
        # 记录警告日志
        logger.warning(f"代理检测到卡住状态。添加提示: {stuck_prompt}")

    def is_stuck(self) -> bool:
        """通过检测重复内容检查代理是否卡在循环中"""
        # 如果消息数量不足，直接返回未卡住
        if len(self.memory.messages) < 2:
            return False

        # 获取最后一条消息
        last_message = self.memory.messages[-1]
        # 如果最后一条消息没有内容，返回未卡住
        if not last_message.content:
            return False

        # 计算相同内容的出现次数
        duplicate_count = sum(
            1
            for msg in reversed(self.memory.messages[:-1])  # 遍历除最后一条外的所有消息
            if msg.role == "assistant" and msg.content == last_message.content  # 匹配助手角色和相同内容
        )

        # 判断重复次数是否达到阈值
        return duplicate_count >= self.duplicate_threshold

    @property
    def messages(self) -> List[Message]:
        """从代理的内存中检索消息列表。"""
        # 返回内存中存储的所有消息
        return self.memory.messages

    @messages.setter
    def messages(self, value: List[Message]):
        """设置代理内存中的消息列表。"""
        # 直接替换内存中的消息列表
        self.memory.messages = value
