"""工具集合类，用于管理多个工具实例及其执行流程"""
from typing import Any, Dict, List

from app.exceptions import ToolError
from app.tool.base import BaseTool, ToolFailure, ToolResult

class ToolCollection:
    """工具集合管理类，提供工具注册、执行及批量操作功能"""
    def __init__(self, *tools: BaseTool):
        """初始化工具集合
        Args:
            *tools: 需要注册的工具实例列表
        """
        self.tools = tools  # 存储所有工具实例的元组
        self.tool_map = {tool.name: tool for tool in tools}  # 工具名称到实例的快速查找字典

    def __iter__(self):
        """实现迭代协议，允许直接遍历工具集合"""
        return iter(self.tools)

    def to_params(self) -> List[Dict[str, Any]]:
        """将所有工具参数转换为标准化字典列表
        Returns:
            每个工具的参数描述字典组成的列表
        """
        return [tool.to_param() for tool in self.tools]

    async def execute(
        self, *, name: str, tool_input: Dict[str, Any] = None
    ) -> ToolResult:
        """执行指定名称的工具
        Args:
            name: 需要执行的工具名称
            tool_input: 工具执行参数字典（可选）
        Returns:
            工具执行结果对象（成功或失败状态）
        """
        tool = self.tool_map.get(name)
        if not tool:
            return ToolFailure(error=f"工具不存在：{name}")
        try:
            result = await tool(**(tool_input or {}))  # 使用默认空字典避免None错误
            return result
        except ToolError as e:
            return ToolFailure(error=str(e))

    async def execute_all(self) -> List[ToolResult]:
        """顺序执行所有工具并收集结果
        Returns:
            按执行顺序排列的工具结果列表
        """
        results = []
        for tool in self.tools:
            try:
                result = await tool()
                results.append(result)
            except ToolError as e:
                results.append(ToolFailure(error=str(e)))
        return results

    def get_tool(self, name: str) -> BaseTool:
        """通过名称获取工具实例"""
        return self.tool_map.get(name)

    def add_tool(self, tool: BaseTool):
        """添加单个工具到集合
        Args:
            tool: 需要注册的工具实例
        Returns:
            自身实例，支持链式调用
        """
        self.tools += (tool,)  # 元组追加需保持元组类型
        self.tool_map[tool.name] = tool
        return self

    def add_tools(self, *tools: BaseTool):
        """批量添加多个工具到集合
        Args:
            *tools: 需要注册的工具实例列表
        Returns:
            自身实例，支持链式调用
        """
        for tool in tools:
            self.add_tool(tool)
        return self
