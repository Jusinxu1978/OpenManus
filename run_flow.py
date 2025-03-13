# 导入异步编程所需的Python标准库
import asyncio  # 提供异步IO和事件循环功能
import time     # 用于时间测量和延迟控制

# 导入自定义模块
from app.agent.manus import Manus  # 负责处理用户请求的主代理类
from app.flow.base import FlowType  # 定义流程类型的枚举类
from app.flow.flow_factory import FlowFactory  # 根据类型创建流程实例的工厂类
from app.logger import logger  # 自定义日志记录器，用于输出运行状态信息

# 主异步函数，负责协调流程执行
async def run_flow():
    """协调代理与流程的执行，处理用户输入并监控执行过程"""
    # 初始化代理集合字典，键为代理名称，值为代理实例
    agents = {
        "manus": Manus(),  # 存储主代理实例供流程调用
    }

    try:
        # 从命令行获取用户输入的提示内容
        prompt = input("Enter your prompt: ")  # 阻塞式等待用户输入

        # 验证输入有效性：检查是否为空或仅包含空白字符
        if prompt.strip() == "" or prompt.isspace():
            logger.warning("Empty prompt provided.")
            return  # 输入无效时直接退出函数

        # 通过工厂模式创建指定类型的流程实例
        flow = FlowFactory.create_flow(
            flow_type=FlowType.PLANNING,  # 选择规划类型流程
            agents=agents,                # 传入代理集合供流程调用
        )
        logger.warning("Processing your request...")  # 输出处理开始提示

        try:
            # 记录流程开始时间
            start_time = time.time()  # 获取当前时间戳

            # 执行流程并设置超时监控（1小时）
            result = await asyncio.wait_for(
                flow.execute(prompt),  # 执行流程的主逻辑，传入用户输入
                timeout=3600,          # 超时阈值设为3600秒（60分钟）
            )
            # 计算并记录执行耗时
            elapsed_time = time.time() - start_time
            logger.info(f"Request processed in {elapsed_time:.2f} seconds")
            logger.info(result)  # 输出流程最终结果

        except asyncio.TimeoutError:  # 捕获超时异常
            logger.error("Request processing timed out after 1 hour")
            logger.info(
                "Operation terminated due to timeout. "  # 超时提示信息
                "Please try a simpler request."
            )

    except KeyboardInterrupt:  # 捕获用户手动中断（Ctrl+C）
        logger.info("Operation cancelled by user.")
    except Exception as e:  # 捕获其他未知异常
        logger.error(f"Error: {str(e)}")  # 记录异常信息

# 程序入口判断
if __name__ == "__main__":  # 确保仅在直接运行此文件时执行
    asyncio.run(run_flow())  # 启动异步主函数的执行流程
