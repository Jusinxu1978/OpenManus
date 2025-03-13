from abc import ABC, abstractmethod  # 导入抽象基类和抽象方法装饰器
from typing import Any, Dict, Optional  # 导入类型提示相关模块

from pydantic import BaseModel, Field  # 导入Pydantic数据模型基类和字段配置工具

# 工具基类，定义所有工具必须实现的接口和基础功能
class BaseTool(ABC, BaseModel):
    name: str  # 工具名称标识符
    description: str  # 工具功能描述文本
    parameters: Optional[dict] = None  # 工具参数定义（可选）

    class Config:  # Pydantic配置类
        arbitrary_types_allowed = True  # 允许使用任意类型（支持异步方法）

    async def __call__(self, **kwargs) -> Any:
        """工具调用入口，通过参数调用execute方法执行具体逻辑"""
        return await self.execute(**kwargs)  # 调用抽象方法执行核心功能

    @abstractmethod  # 强制子类必须实现该方法
    async def execute(self, **kwargs) -> Any:
        """抽象方法：定义工具的具体执行逻辑（由子类实现）"""

    def to_param(self) -> Dict:
        """将工具转换为API调用所需的函数格式参数"""
        return {
            "type": "function",  # 固定类型标识
            "function": {
                "name": self.name,  # 工具名称
                "description": self.description,  # 功能描述
                "parameters": self.parameters,  # 参数定义
            },
        }

# 工具执行结果基类，封装执行输出、错误和系统信息
class ToolResult(BaseModel):
    """表示工具执行结果的通用数据模型"""
    output: Any = Field(default=None)  # 工具执行输出内容
    error: Optional[str] = Field(default=None)  # 执行过程中产生的错误信息
    system: Optional[str] = Field(default=None)  # 系统级状态信息（如工具重启提示）

    class Config:
        arbitrary_types_allowed = True  # 允许任意类型数据

    def __bool__(self):
        """重载布尔判断：当output/error/system任一存在时返回True"""
        return any(getattr(self, field) for field in self.__fields__)

    def __add__(self, other: "ToolResult"):
        """合并两个ToolResult对象的方法"""
        def combine_fields(
            field: Optional[str], 
            other_field: Optional[str], 
            concatenate: bool = True
        ):
            """合并字段逻辑：优先保留非空值，可选拼接模式"""
            if field and other_field:
                if concatenate:
                    return field + other_field
                raise ValueError("Cannot combine tool results")
            return field or other_field

        return ToolResult(
            output=combine_fields(self.output, other.output),
            error=combine_fields(self.error, other.error),
            system=combine_fields(self.system, other.system),
        )

    def __str__(self):
        """字符串表示：优先显示错误信息，否则显示输出内容"""
        return f"Error: {self.error}" if self.error else self.output

    def replace(self, **kwargs):
        """创建新实例并替换指定字段值"""
        return type(self)(**{**self.dict(), **kwargs})

class CLIResult(ToolResult):
    """专门用于命令行工具执行结果的子类"""

class ToolFailure(ToolResult):
    """表示工具执行失败的专用结果类型"""

class AgentAwareTool:
    """代理感知工具基类，用于需要访问代理实例的工具"""
    agent: Optional = None  # 可选关联的代理实例
