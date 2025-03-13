"""用于异步执行shell命令并处理超时的工具模块"""

import asyncio

TRUNCATED_MESSAGE: str = "<response clipped><NOTE>为节省上下文空间，仅显示部分内容。如需完整内容，请使用`grep -n`搜索文件后重新查询。</NOTE>"
MAX_RESPONSE_LEN: int = 16000  # 最大响应长度限制

def maybe_truncate(content: str, truncate_after: int | None = MAX_RESPONSE_LEN) -> str:
    """根据长度限制截断内容并在超出时添加提示信息"""
    if not truncate_after or len(content) <= truncate_after:
        return content
    else:
        return content[:truncate_after] + TRUNCATED_MESSAGE

async def run(
    cmd: str,  # 要执行的shell命令
    timeout: float | None = 120.0,  # 命令超时时间（秒），默认120秒
    truncate_after: int | None = MAX_RESPONSE_LEN  # 输出截断长度
):
    """异步执行shell命令并处理超时与输出截断"""
    process = await asyncio.create_subprocess_shell(
        cmd,  # 要执行的命令字符串
        stdout=asyncio.subprocess.PIPE,  # 捕获标准输出
        stderr=asyncio.subprocess.PIPE  # 捕获标准错误
    )
    
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),  # 等待命令执行完成
            timeout=timeout  # 应用超时限制
        )
        return (
            process.returncode or 0,  # 返回退出码（失败时默认0）
            maybe_truncate(stdout.decode(), truncate_after),  # 处理标准输出
            maybe_truncate(stderr.decode(), truncate_after)  # 处理标准错误
        )
    except asyncio.TimeoutError as exc:  # 超时处理
        try:
            process.kill()  # 终止进程
        except ProcessLookupError:  # 忽略进程不存在的异常
            pass
        raise TimeoutError(
            f"命令 '{cmd}' 在 {timeout} 秒后超时"
        ) from exc
