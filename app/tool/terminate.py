from app.tool.base import BaseTool  # 导入基础工具类，所有工具需继承该基类

_TERMINATE_DESCRIPTION = """终止交互工具描述：
当任务完成或助手无法继续处理时调用此工具结束交互。
当所有任务完成后，调用该工具终止工作流程。"""

class Terminate(BaseTool):
    """终止交互工具类，用于结束当前工作流程"""
    name: str = "terminate"  # 工具名称标识符，用于外部调用时的唯一识别
    description: str = _TERMINATE_DESCRIPTION  # 工具功能描述，说明使用场景和规则
    parameters: dict = {  # 工具参数定义，遵循JSON Schema规范
        "type": "object",
        "properties": {
            "status": {  # 必要参数：任务完成状态
                "type": "string",
                "description": "交互完成状态标识，有效值为'success'或'failure'",
                "enum": ["success", "failure"],  # 限定允许的枚举值
            }
        },
        "required": ["status"],  # 指定必须提供的参数列表
    }

    async def execute(self, status: str) -> str:
        """执行终止操作，返回完成状态信息"""
        # 验证参数status的有效性由参数校验层处理，此处直接构造返回信息
        return f"交互已完成，状态：{status}"  # 返回标准化的终止信息字符串
