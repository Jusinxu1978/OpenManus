import asyncio  # 导入异步IO库，用于异步执行Bash命令
import os  # 导入操作系统接口模块，用于访问操作系统功能
from typing import Optional  # 导入可选类型提示

from app.exceptions import ToolError  # 从异常模块导入自定义工具错误类
from app.tool.base import BaseTool, CLIResult, ToolResult  # 从基础工具模块导入基类和结果类

# 执行Bash命令的工具描述文本，包含长命令处理、交互式命令和超时处理说明
_BASH_DESCRIPTION = """Execute a bash command in the terminal.
* Long running commands: For commands that may run indefinitely, it should be run in the background and the output should be redirected to a file, e.g. command = `python3 app.py > server.log 2>&1 &`.
* Interactive: If a bash command returns exit code `-1`, this means the process is not yet finished. The assistant must then send a second call to terminal with an empty `command` (which will retrieve any additional logs), or it can send additional text (set `command` to the text) to STDIN of the running process, or it can send command=`ctrl+c` to interrupt the process.
* Timeout: If a command execution result says "Command timed out. Sending SIGINT to the process", the assistant should retry running the command in the background.
"""

# Bash会话类，管理Bash进程的生命周期和命令执行
class _BashSession:
    """A session of a bash shell."""

    _started: bool  # 标记会话是否已启动
    _process: asyncio.subprocess.Process  # 存储异步子进程对象

    command: str = "/bin/bash"  # 默认Bash命令路径
    _output_delay: float = 0.2  # 输出读取间隔时间（秒）
    _timeout: float = 120.0  # 命令执行超时时间（秒）
    _sentinel: str = "<<exit>>"  # 命令结束标识符

    def __init__(self):
        self._started = False  # 初始化会话未启动状态
        self._timed_out = False  # 标记是否因超时终止

    async def start(self):
        """启动Bash会话进程"""
        if self._started:
            return  # 已启动则直接返回
        self._process = await asyncio.create_subprocess_shell(
            self.command,  # 执行Bash命令
            preexec_fn=os.setsid,  # 创建新会话组以便后续终止进程组
            shell=True,  # 启用shell解释器
            bufsize=0,  # 禁用缓冲以实时读取输出
            stdin=asyncio.subprocess.PIPE,  # 配置标准输入管道
            stdout=asyncio.subprocess.PIPE,  # 配置标准输出管道
            stderr=asyncio.subprocess.PIPE  # 配置标准错误管道
        )
        self._started = True  # 标记为已启动

    def stop(self):
        """终止Bash会话进程"""
        if not self._started:
            raise ToolError("Session has not started.")  # 未启动时抛出错误
        if self._process.returncode is not None:
            return  # 进程已自然终止则直接返回
        self._process.terminate()  # 终止进程

    async def run(self, command: str):
        """在Bash会话中执行具体命令"""
        if not self._started:
            raise ToolError("Session has not started.")  # 未启动时抛出错误
        if self._process.returncode is not None:
            return ToolResult(  # 进程已终止时返回错误信息
                system="tool must be restarted",
                error=f"bash has exited with returncode {self._process.returncode}"
            )
        if self._timed_out:
            raise ToolError(  # 超时后抛出错误
                f"timed out: bash has not returned in {self._timeout} seconds and must be restarted"
            )

        assert self._process.stdin  # 确保输入管道存在
        assert self._process.stdout  # 确保输出管道存在
        assert self._process.stderr  # 确保错误管道存在

        # 向进程发送命令并添加结束标识符
        self._process.stdin.write(
            command.encode() + f"; echo '{self._sentinel}'\n".encode()
        )
        await self._process.stdin.drain()  # 确保数据完全写入

        # 循环读取输出直到遇到标识符或超时
        try:
            async with asyncio.timeout(self._timeout):
                while True:
                    await asyncio.sleep(self._output_delay)  # 等待输出产生
                    output = self._process.stdout._buffer.decode()  # 读取原始输出缓冲区
                    if self._sentinel in output:
                        output = output[: output.index(self._sentinel)]  # 截取标识符前内容
                        break
        except asyncio.TimeoutError:
            self._timed_out = True
            raise ToolError(  # 超时处理
                f"timed out: bash has not returned in {self._timeout} seconds and must be restarted"
            ) from None

        # 处理输出格式
        if output.endswith("\n"):
            output = output[:-1]
        error = self._process.stderr._buffer.decode()  # 读取错误输出
        if error.endswith("\n"):
            error = error[:-1]

        # 清空缓冲区准备下次读取
        self._process.stdout._buffer.clear()
        self._process.stderr._buffer.clear()

        return CLIResult(output=output, error=error)  # 返回命令执行结果

# 具体Bash工具类，继承自基础工具类
class Bash(BaseTool):
    """A tool for executing bash commands"""
    name: str = "bash"  # 工具名称
    description: str = _BASH_DESCRIPTION  # 工具描述文本
    parameters: dict = {  # 参数定义
        "type": "object",
        "properties": {
            "command": {  # 必要参数定义
                "type": "string",
                "description": "The bash command to execute. Can be empty to view additional logs when previous exit code is `-1`. Can be `ctrl+c` to interrupt the currently running process.",
            },
        },
        "required": ["command"],  # 必要参数列表
    }

    _session: Optional[_BashSession] = None  # 会话实例

    async def execute(
        self, command: str | None = None, restart: bool = False, **kwargs
    ) -> CLIResult:
        """执行Bash命令的核心方法"""
        if restart:
            if self._session:
                self._session.stop()  # 停止现有会话
            self._session = _BashSession()
            await self._session.start()  # 启动新会话
            return ToolResult(system="tool has been restarted.")  # 返回重启结果

        if self._session is None:
            self._session = _BashSession()
            await self._session.start()  # 首次启动会话

        if command is not None:
            return await self._session.run(command)  # 执行具体命令

        raise ToolError("no command provided.")  # 参数缺失时抛出错误

if __name__ == "__main__":
    bash = Bash()  # 创建Bash工具实例
    rst = asyncio.run(bash.execute("ls -l"))  # 执行示例命令
    print(rst)  # 输出执行结果
