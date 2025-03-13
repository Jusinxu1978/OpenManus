# 导入必要的模块
import asyncio  # 用于异步编程的Python库

# 导入自定义模块
from app.agent.manus import Manus  # 主代理类，负责处理用户请求
from app.logger import logger  # 自定义日志记录器，用于输出运行状态信息

# 主异步函数定义
async def main():
    """程序核心入口，负责初始化代理并处理用户输入"""
    # 初始化Manus代理实例
    agent = Manus()  # 创建代理对象以处理用户请求

    try:
        # 获取用户输入的提示信息
        prompt = input("Enter your prompt: ")  # 通过命令行读取用户输入的提示内容

        # 检查输入内容是否为空
        if not prompt.strip():  # 去除首尾空白后判断是否为空字符串
            logger.warning("Empty prompt provided.")  # 记录警告信息
            return  # 退出当前函数执行

        # 开始处理用户请求
        logger.warning("Processing your request...")  # 输出处理开始的提示信息
        await agent.run(prompt)  # 异步执行代理的处理流程（解析、规划、执行等步骤）
        logger.info("Request processing completed.")  # 记录处理完成状态

    except KeyboardInterrupt:  # 捕获用户手动中断（Ctrl+C）
        logger.warning("Operation interrupted.")  # 记录中断操作日志

# 程序入口判断
if __name__ == "__main__":  # 确保仅在直接运行此文件时执行以下代码
    asyncio.run(main())  # 启动异步主函数的执行流程
