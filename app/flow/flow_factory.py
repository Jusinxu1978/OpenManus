from typing import Dict, List, Union  # 类型注解支持

from app.agent.base import BaseAgent  # 导入agent基类
from app.flow.base import BaseFlow, FlowType  # 导入流程基类和流程类型枚举
from app.flow.planning import PlanningFlow  # 导入规划流程实现类


class FlowFactory:
    """Factory for creating different types of flows with support for multiple agents
    支持多agent的流程工厂类，用于创建不同类型的流程
    """

    @staticmethod
    def create_flow(
        flow_type: FlowType,
        agents: Union[BaseAgent, List[BaseAgent], Dict[str, BaseAgent]],
        **kwargs,
    ) -> BaseFlow:
        """创建指定类型的流程实例
        :param flow_type: 流程类型枚举值
        :param agents: 可以是一个BaseAgent实例、BaseAgent列表或包含agent的字典
        :param kwargs: 其他初始化参数
        :return: 创建的流程实例
        :raises ValueError: 如果传入未知的流程类型
        """
        flows = {
            FlowType.PLANNING: PlanningFlow,  # 规划流程映射
        }

        flow_class = flows.get(flow_type)  # 根据类型获取对应的流程类
        if not flow_class:
            raise ValueError(f"Unknown flow type: {flow_type}")  # 如果类型未知则抛出异常

        return flow_class(agents, **kwargs)  # 创建并返回流程实例
