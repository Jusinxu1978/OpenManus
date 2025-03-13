import os  # 导入操作系统接口模块，用于路径操作
import aiofiles  # 异步文件操作库，用于非阻塞文件写入

from app.tool.base import BaseTool  # 导入工具基类

class FileSaver(BaseTool):
    name: str = "file_saver"  # 工具名称标识符
    description: str = """Save content to a local file at a specified path.
Use this tool when you need to save text, code, or generated content to a file on the local filesystem.
The tool accepts content and a file path, and saves the content to that location.
"""  # 功能描述文本：说明工具用途和使用场景

    parameters: dict = {  # 参数定义
        "type": "object",
        "properties": {  # 参数属性集合
            "content": {  # 必要参数：文件内容
                "type": "string",
                "description": "(required) The content to save to the file.",
            },
            "file_path": {  # 必要参数：文件保存路径
                "type": "string",
                "description": "(required) The path where the file should be saved, including filename and extension.",
            },
            "mode": {  # 可选参数：文件操作模式
                "type": "string",
                "description": "(optional) The file opening mode. Default is 'w' for write. Use 'a' for append.",
                "enum": ["w", "a"],  # 允许的模式选项
                "default": "w",  # 默认写入模式
            },
        },
        "required": ["content", "file_path"],  # 必要参数列表
    }

    async def execute(
        self, content: str, file_path: str, mode: str = "w"
    ) -> str:
        """执行文件保存的核心方法"""
        try:
            # 确保目标目录存在（自动创建缺失目录）
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)  # 递归创建父目录

            # 异步写入文件内容
            async with aiofiles.open(file_path, mode, encoding="utf-8") as file:
                await file.write(content)  # 写入内容到文件

            return f"Content successfully saved to {file_path}"  # 成功提示
        except Exception as e:
            return f"Error saving file: {str(e)}"  # 异常信息返回
