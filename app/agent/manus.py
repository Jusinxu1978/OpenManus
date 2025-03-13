# 导入必要的模块
from typing import Any  # 类型注解，用于定义函数参数和返回值的类型

from pydantic import Field  # 数据验证和设置管理，用于定义数据模型字段

# 导入自定义模块
from app.agent.toolcall import ToolCallAgent  # 工具调用基类，提供工具调用的基础功能
from app.prompt.manus import NEXT_STEP_PROMPT, SYSTEM_PROMPT  # 提示模板，用于生成系统提示和下一步提示
from app.tool import Terminate, ToolCollection  # 工具集合和终止工具，用于管理可用工具
from app.tool.browser_use_tool import BrowserUseTool  # 浏览器工具，用于网页浏览操作
from app.tool.file_saver import FileSaver  # 文件保存工具，用于文件保存操作
from app.tool.google_search import GoogleSearch  # 谷歌搜索工具，用于信息检索
from app.tool.python_execute import PythonExecute  # Python执行工具，用于执行Python代码


class Manus(ToolCallAgent):
    """
    一个通用的多功能代理，使用规划来解决各种任务。

    该代理扩展了PlanningAgent，具有全面的工具和能力，
    包括Python执行、网页浏览、文件操作和信息检索，
    可以处理各种用户请求。
    """

    # 代理名称，用于标识代理类型
    name: str = "Manus"
    # 代理描述，简要说明代理的功能和用途
    description: str = (
        "一个可以使用多种工具解决各种任务的多功能代理"
    )

    # 系统提示模板，用于初始化代理时的系统提示
    system_prompt: str = SYSTEM_PROMPT
    # 下一步提示模板，用于生成下一步操作的提示
    next_step_prompt: str = NEXT_STEP_PROMPT

    # 最大观察长度，限制代理观察结果的最大长度
    max_observe: int = 2000
    # 最大步骤数，限制代理执行任务的最大步骤数
    max_steps: int = 20

    # 添加通用工具到工具集合，初始化代理时可用的工具
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            PythonExecute(),  # Python执行工具，用于执行Python代码
            GoogleSearch(),  # 谷歌搜索工具，用于信息检索
            BrowserUseTool(),  # 浏览器工具，用于网页浏览操作
            FileSaver(),  # 文件保存工具，用于文件保存操作
            Terminate()  # 终止工具，用于结束任务
        )
    )

    # 处理特殊工具的方法，用于在工具调用后执行特定操作
    async def _handle_special_tool(self, name: str, result: Any, **kwargs):
        # 清理浏览器工具，确保浏览器资源被正确释放
        await self.available_tools.get_tool(BrowserUseTool().name).cleanup()
        # 调用父类方法处理特殊工具，执行父类的特殊工具处理逻辑
        await super()._handle_special_tool(name, result, **kwargs)
