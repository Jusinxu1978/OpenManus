import asyncio
import os
import shlex
from typing import Optional

from app.tool.base import BaseTool, CLIResult

class Terminal(BaseTool):
    """终端执行工具类，支持异步执行CLI命令并保持上下文环境"""
    name: str = "execute_command"  # 工具名称标识符，用于外部调用时的唯一标识
    description: str = """执行系统CLI命令的工具
    * 适用于需要执行系统操作或特定命令完成任务的场景
    * 需根据用户系统环境调整命令格式并说明其作用
    * 优先执行复杂CLI命令而非脚本以保持灵活性
    * 命令默认在当前工作目录执行
    * 注意：若命令执行时间少于50ms，请在末尾添加`sleep 0.05`以避免终端工具返回空结果的已知问题
    """
    parameters: dict = {  # 工具参数定义结构，遵循JSON Schema规范
        "type": "object",
        "properties": {
            "command": {  # 必要参数：要执行的命令字符串
                "type": "string",
                "description": "必须提供，且需符合当前操作系统语法的CLI命令",
            }
        },
        "required": ["command"],  # 必填参数列表
    }
    process: Optional[asyncio.subprocess.Process] = None  # 当前正在执行的进程对象
    current_path: str = os.getcwd()  # 当前工作目录路径，初始化为脚本执行目录
    lock: asyncio.Lock = asyncio.Lock()  # 异步锁对象，防止并发执行导致的上下文混乱

    async def execute(self, command: str) -> CLIResult:
        """执行终端命令并返回结果，支持多命令链式执行"""
        commands = [cmd.strip() for cmd in command.split('&') if cmd.strip()]  # 按&符号分割多命令，过滤空命令
        final_output = CLIResult(output="", error="")  # 初始化最终输出容器
        
        for cmd in commands:
            sanitized_cmd = self._sanitize_command(cmd)  # 执行命令安全检查
            
            if sanitized_cmd.lstrip().startswith("cd "):  # 特殊处理cd命令
                result = await self._handle_cd_command(sanitized_cmd)
            else:
                async with self.lock:  # 获取锁确保单线程执行
                    try:
                        self.process = await asyncio.create_subprocess_shell(
                            sanitized_cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                            cwd=self.current_path,  # 使用当前工作目录执行命令
                        )
                        stdout, stderr = await self.process.communicate()  # 等待命令执行完成
                        result = CLIResult(
                            output=stdout.decode().strip(),
                            error=stderr.decode().strip()
                        )
                    except Exception as e:
                        result = CLIResult(output="", error=str(e))
                    finally:
                        self.process = None  # 清理进程对象防止资源泄漏
                    
            # 合并多命令输出结果
            if result.output:
                final_output.output += f"{result.output}\n" if final_output.output else result.output
            if result.error:
                final_output.error += f"{result.error}\n" if final_output.error else result.error
        
        # 清理末尾多余换行符
        final_output.output = final_output.output.rstrip()
        final_output.error = final_output.error.rstrip()
        return final_output

    async def execute_in_env(self, env_name: str, command: str) -> CLIResult:
        """在指定Conda环境中执行命令"""
        sanitized_cmd = self._sanitize_command(command)
        conda_cmd = f"conda run -n {shlex.quote(env_name)} {sanitized_cmd}"
        return await self.execute(conda_cmd)

    async def _handle_cd_command(self, command: str) -> CLIResult:
        """处理目录切换命令，更新current_path属性"""
        try:
            parts = shlex.split(command)
            if len(parts) < 2:  # 无参数时切换到用户主目录
                new_path = os.path.expanduser("~")
            else:
                new_path = os.path.expanduser(parts[1])
            
            if not os.path.isabs(new_path):  # 相对路径转换为绝对路径
                new_path = os.path.join(self.current_path, new_path)
            new_path = os.path.abspath(new_path)  # 获取规范绝对路径
            
            if os.path.isdir(new_path):  # 验证目录是否存在
                self.current_path = new_path
                return CLIResult(output=f"切换到目录：{self.current_path}", error="")
            else:
                return CLIResult(output="", error=f"目录不存在：{new_path}")
        except Exception as e:
            return CLIResult(output="", error=str(e))

    @staticmethod
    def _sanitize_command(command: str) -> str:
        """命令安全检查，禁止危险操作"""
        dangerous_commands = ["rm", "sudo", "shutdown", "reboot"]
        try:
            parts = shlex.split(command)
            if any(cmd in dangerous_commands for cmd in parts):
                raise ValueError("禁止使用危险命令")
        except:
            if any(cmd in command for cmd in dangerous_commands):
                raise ValueError("禁止使用危险命令")
        return command

    async def close(self):
        """关闭持久化进程，确保资源释放"""
        async with self.lock:
            if self.process:
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    self.process.kill()
                    await self.process.wait()
                finally:
                    self.process = None

    async def __aenter__(self):
        """异步上下文管理器进入，支持with语句使用"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出时关闭进程，确保资源释放"""
        await self.close()
