import threading
from typing import Dict

from app.tool.base import BaseTool

class PythonExecute(BaseTool):
    """用于执行Python代码的工具类，支持超时控制和安全限制"""
    
    name: str = "python_execute"  # 工具名称标识符
    description: str = "执行Python代码字符串。注意：仅能查看print输出，函数返回值不会被捕获，请使用print语句查看结果"  # 工具功能描述
    parameters: dict = {  # 参数定义结构
        "type": "object",
        "properties": {  # 参数属性集合
            "code": {  # 必要参数：要执行的代码字符串
                "type": "string",
                "description": "要执行的Python代码内容",
            },
        },
        "required": ["code"],  # 必填参数列表
    }

    async def execute(  # 工具执行方法
        self,
        code: str,  # 要执行的Python代码
        timeout: int = 5,  # 执行超时时间（秒）
    ) -> Dict:  # 返回执行结果字典
        """执行Python代码并处理超时与异常"""
        result = {"observation": ""}  # 初始化结果字典

        def run_code():  # 子线程执行函数
            try:
                safe_globals = {"__builtins__": dict(__builtins__)}  # 创建安全的全局变量环境
                
                import sys
                from io import StringIO
                
                output_buffer = StringIO()  # 捕获输出的缓冲区
                sys.stdout = output_buffer  # 重定向标准输出
                
                exec(code, safe_globals, {})  # 执行用户提供的代码
                
                sys.stdout = sys.__stdout__  # 恢复标准输出
                
                result["observation"] = output_buffer.getvalue()  # 保存执行输出
                
            except Exception as e:  # 捕获异常
                result["observation"] = str(e)  # 记录错误信息
                result["success"] = False  # 标记执行失败

        thread = threading.Thread(target=run_code)  # 创建执行线程
        thread.start()  # 启动线程
        thread.join(timeout)  # 等待线程完成或超时
        
        if thread.is_alive():  # 检查是否超时
            return {  # 返回超时信息
                "observation": f"执行超时（超过{timeout}秒）",
                "success": False,
            }
        
        return result  # 返回执行结果
