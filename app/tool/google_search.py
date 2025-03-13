import asyncio  # 导入异步IO库，用于异步执行搜索操作
from typing import List  # 导入类型提示中的列表类型

from googlesearch import search  # 导入Google搜索API的搜索函数
from app.tool.base import BaseTool  # 导入工具基类

class GoogleSearch(BaseTool):
    name: str = "google_search"  # 工具名称标识符
    description: str = """Perform a Google search and return a list of relevant links.
Use this tool when you need to find information on the web, get up-to-date data, or research specific topics.
The tool returns a list of URLs that match the search query.
"""  # 功能描述文本：说明工具用途和使用场景

    parameters: dict = {  # 参数定义字典
        "type": "object",
        "properties": {  # 参数属性集合
            "query": {  # 必要参数：搜索查询内容
                "type": "string",
                "description": "(required) The search query to submit to Google.",
            },
            "num_results": {  # 可选参数：返回结果数量
                "type": "integer",
                "description": "(optional) The number of search results to return. Default is 10.",
                "default": 10,
            },
        },
        "required": ["query"],  # 必要参数列表
    }

    async def execute(
        self, query: str, num_results: int = 10
    ) -> List[str]:
        """执行搜索的核心异步方法"""
        # 在线程池中运行以避免阻塞事件循环
        loop = asyncio.get_event_loop()  # 获取当前事件循环
        links = await loop.run_in_executor(  # 异步执行搜索操作
            None,
            lambda: list(search(query, num_results=num_results)),  # 调用search函数并转换为列表
        )
        return links  # 返回搜索结果链接列表
