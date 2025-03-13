from abc import ABC, abstractmethod  # 抽象基类相关功能
from enum import Enum  # 枚举类型支持
from typing import Dict, List, Optional, Union  # 类型注解支持

from pydantic import BaseModel  # 数据模型基类

from app.agent.base import BaseAgent  # 导入agent基类


class FlowType(str, Enum):
    """流程类型枚举类，定义不同的流程类型"""
    PLANNING = "planning"  # 规划类型流程


class BaseFlow(BaseModel, ABC):
    """Base class for execution flows supporting multiple agents
    支持多agent的执行流程基类
    """

    agents: Dict[str, BaseAgent]  # 存储所有agent的字典，key为agent标识符
    tools: Optional[List] = None  # 可选工具列表
    primary_agent_key: Optional[str] = None  # 主agent的标识符

    class Config:
        """Pydantic模型配置类"""
        arbitrary_types_allowed = True  # 允许任意类型作为字段值

    def __init__(
        self, agents: Union[BaseAgent, List[BaseAgent], Dict[str, BaseAgent]], **data
    ):
        """初始化BaseFlow实例
        :param agents: 可以是一个BaseAgent实例、BaseAgent列表或包含agent的字典
        :param data: 其他初始化数据
        """
        # 处理不同类型的agents参数
        if isinstance(agents, BaseAgent):
            agents_dict = {"default": agents}  # 单个agent转换为字典
        elif isinstance(agents, list):
            agents_dict = {f"agent_{i}": agent for i, agent in enumerate(agents)}  # 列表转换为字典
        else:
            agents_dict = agents  # 已经是字典则直接使用

        # 如果未指定主agent，则使用第一个agent
        primary_key = data.get("primary_agent_key")
        if not primary_key and agents_dict:
            primary_key = next(iter(agents_dict))  # 获取第一个agent的key
            data["primary_agent_key"] = primary_key  # 设置主agent key

        # 设置agents字典
        data["agents"] = agents_dict

        # 调用BaseModel的初始化方法
        super().__init__(**data)

    @property
    def primary_agent(self) -> Optional[BaseAgent]:
        """Get the primary agent for the flow
        获取流程的主agent
        :return: 主agent实例，如果未设置则返回None
        """
        return self.agents.get(self.primary_agent_key)  # 通过primary_agent_key获取主agent

    def get_agent(self, key: str) -> Optional[BaseAgent]:
        """Get a specific agent by key
        根据key获取指定的agent
        :param key: agent的唯一标识符
        :return: 对应的agent实例，如果不存在则返回None
        """
        return self.agents.get(key)  # 从agents字典中获取指定key的agent

    def add_agent(self, key: str, agent: BaseAgent) -> None:
        """Add a new agent to the flow
        向流程中添加一个新的agent
        :param key: agent的唯一标识符
        :param agent: 要添加的agent实例
        """
        self.agents[key] = agent  # 将新agent添加到agents字典中

    @abstractmethod
    async def execute(self, input_text: str) -> str:
        """Execute the flow with given input
        使用给定的输入执行流程
        :param input_text: 输入文本
        :return: 执行结果字符串
        """
        # 抽象方法，需要子类实现具体执行逻辑


class PlanStepStatus(str, Enum):
    """Enum class defining possible statuses of a plan step
    定义计划步骤可能状态的枚举类
    """

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"

    @classmethod
    def get_all_statuses(cls) -> list[str]:
        """Return a list of all possible step status values
        获取所有可能的步骤状态值列表
        :return: 包含所有状态值的字符串列表
        """
        return [status.value for status in cls]  # 遍历枚举类获取所有状态值

    @classmethod
    def get_active_statuses(cls) -> list[str]:
        """Return a list of values representing active statuses (not started or in progress)
        获取表示活动状态（未开始或进行中）的值列表
        :return: 包含活动状态值的字符串列表
        """
        return [cls.NOT_STARTED.value, cls.IN_PROGRESS.value]  # 返回未开始和进行中状态

    @classmethod
    def get_status_marks(cls) -> Dict[str, str]:
        """Return a mapping of statuses to their marker symbols
        获取状态到标记符号的映射
        :return: 包含状态和对应标记符号的字典
        """
        return {
            cls.COMPLETED.value: "[✓]",  # 完成状态标记
            cls.IN_PROGRESS.value: "[→]",  # 进行中状态标记
            cls.BLOCKED.value: "[!]",  # 阻塞状态标记
            cls.NOT_STARTED.value: "[ ]",  # 未开始状态标记
        }
