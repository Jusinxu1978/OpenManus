from typing import List  # 导入List类型用于类型注解

from pydantic import Field  # 导入Field用于定义Pydantic模型字段

from app.agent.toolcall import ToolCallAgent  # 导入ToolCallAgent作为基类
from app.prompt.swe import NEXT_STEP_TEMPLATE, SYSTEM_PROMPT  # 导入SWE相关的提示模板
from app.tool import Bash, StrReplaceEditor, Terminate, ToolCollection  # 导入各种工具类


class SWEAgent(ToolCallAgent):
    """一个实现SWEAgent范式的代理，用于执行代码和自然对话。"""

    name: str = "swe"  # 代理名称
    description: str = "一个直接与计算机交互以解决任务的自主AI程序员。"  # 代理描述

    system_prompt: str = SYSTEM_PROMPT  # 系统提示模板
    next_step_prompt: str = NEXT_STEP_TEMPLATE  # 下一步提示模板

    available_tools: ToolCollection = ToolCollection(
        Bash(), StrReplaceEditor(), Terminate()
    )  # 可用的工具集合
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])  # 特殊工具名称列表

    max_steps: int = 30  # 最大执行步骤数

    bash: Bash = Field(default_factory=Bash)  # Bash工具实例
    working_dir: str = "."  # 当前工作目录

    async def think(self) -> bool:
        """处理当前状态并决定下一步操作"""
        # 更新工作目录
        self.working_dir = await self.bash.execute("pwd")
        self.next_step_prompt = self.next_step_prompt.format(
            current_dir=self.working_dir
        )  # 格式化下一步提示模板

        return await super().think()  # 调用父类的think方法
