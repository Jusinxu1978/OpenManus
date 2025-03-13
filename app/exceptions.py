class ToolError(Exception):  # 定义一个用于工具错误的自定义异常类
    """Raised when a tool encounters an error."""  # 当工具遇到错误时抛出此异常

    def __init__(self, message):  # 初始化方法，接收错误信息参数
        self.message = message    # 将传入的错误信息赋值给实例变量
