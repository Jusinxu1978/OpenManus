# 导入必要的模块
from abc import ABC, abstractmethod  # 提供抽象基类功能，用于定义接口规范
from typing import Optional  # 用于类型注解，表示可选参数

from pydantic import Field  # 用于数据模型字段的定义和验证

# 导入自定义模块
from app.agent.base import BaseAgent  # 所有代理类的基类，提供通用功能
from app.llm import LLM  # 语言模型类，用于处理自然语言任务
from app.schema import AgentState, Memory  # 定义代理状态和内存存储的数据结构


class ReActAgent(BaseAgent, ABC):
    """ReAct（思考-执行）代理的抽象基类"""

    name: str  # 代理的唯一标识名称
    description: Optional[str] = None  # 代理的功能描述，可为空

    system_prompt: Optional[str] = None  # 系统级别的提示信息，用于初始化代理
    next_step_prompt: Optional[str] = None  # 用于指导代理下一步操作的提示模板

    llm: Optional[LLM] = Field(default_factory=LLM)  # 语言模型实例，默认使用LLM类创建
    memory: Memory = Field(default_factory=Memory)  # 内存存储实例，用于保存代理运行时的数据
    state: AgentState = AgentState.IDLE  # 代理的当前状态，初始化为空闲状态

    max_steps: int = 10  # 代理执行的最大步骤数，防止无限循环
    current_step: int = 0  # 当前执行的步骤计数

    @abstractmethod
    async def think(self) -> bool:
        """处理当前状态并决定下一步操作
        返回布尔值表示是否需要执行操作"""

    @abstractmethod
    async def act(self) -> str:
        """执行决定的操作
        返回字符串表示操作结果"""

    async def step(self) -> str:
        """执行单个步骤：思考并执行。
        返回字符串表示步骤执行结果"""
        should_act = await self.think()  # 调用think方法决定是否需要执行操作
        if not should_act:  # 如果不需要执行操作
            return "思考完成 - 无需操作"  # 返回提示信息
        return await self.act()  # 否则执行操作并返回结果
