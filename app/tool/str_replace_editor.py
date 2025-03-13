"""字符串替换编辑工具模块，支持文件查看、创建、替换、插入和撤销操作"""

from collections import defaultdict
from pathlib import Path
from typing import Literal, get_args

from app.exceptions import ToolError
from app.tool import BaseTool
from app.tool.base import CLIResult, ToolResult
from app.tool.run import run

Command = Literal["view", "create", "str_replace", "insert", "undo_edit"]
SNIPPET_LINES: int = 4  # 编辑时显示的上下文行数
MAX_RESPONSE_LEN: int = 16000  # 最大响应长度限制
TRUNCATED_MESSAGE: str = "<response clipped><NOTE>为节省上下文空间，仅显示部分内容。如需完整内容，请使用`grep -n`搜索文件后重新查询。</NOTE>"

_STR_REPLACE_EDITOR_DESCRIPTION = """自定义文件编辑工具
* 状态在命令调用和用户交互间保持持久
* `view`命令：文件显示带行号的`cat`输出，目录显示2层深度的非隐藏文件列表
* `create`命令：若路径已存在则禁止创建
* 长输出会截断并标记`<response clipped>`
* `undo_edit`可撤销最后一次对文件的编辑
`str_replace`注意事项：
* `old_str`需精确匹配文件中连续的1+行（注意空格）
* 非唯一匹配时拒绝替换，需增加上下文确保唯一性
* `new_str`替换`old_str`的内容
"""

def maybe_truncate(content: str, truncate_after: int | None = MAX_RESPONSE_LEN) -> str:
    """根据长度限制截断内容并在超出时添加提示信息"""
    if not truncate_after or len(content) <= truncate_after:
        return content
    return content[:truncate_after] + TRUNCATED_MESSAGE

class StrReplaceEditor(BaseTool):
    """文件编辑工具类，支持查看、创建、替换、插入和撤销操作"""
    
    name: str = "str_replace_editor"  # 工具名称标识符
    description: str = _STR_REPLACE_EDITOR_DESCRIPTION  # 功能描述
    parameters: dict = {  # 参数定义结构
        "type": "object",
        "properties": {  # 参数属性集合
            "command": {  # 必要参数：操作指令类型
                "description": "支持的操作指令：`view`查看、`create`创建、`str_replace`替换、`insert`插入、`undo_edit`撤销",
                "enum": ["view", "create", "str_replace", "insert", "undo_edit"],
                "type": "string"
            },
            "path": {  # 必要参数：文件路径
                "description": "绝对路径的文件或目录",
                "type": "string"
            },
            "file_text": {  # `create`命令必填参数
                "description": "创建文件时的内容",
                "type": "string"
            },
            "old_str": {  # `str_replace`命令必填参数
                "description": "要替换的原始字符串内容",
                "type": "string"
            },
            "new_str": {  # `str_replace`和`insert`命令参数
                "description": "替换后的新内容（`str_replace`可选，`insert`必填）",
                "type": "string"
            },
            "insert_line": {  # `insert`命令必填参数
                "description": "插入位置的行号（在该行后插入）",
                "type": "integer"
            },
            "view_range": {  # `view`命令可选参数
                "description": "文件查看的行号范围，如[11,12]显示指定行，[start,-1]显示从start到末尾",
                "items": {"type": "integer"},
                "type": "array"
            },
        },
        "required": ["command", "path"],  # 必填参数列表
    }

    _file_history: dict = defaultdict(list)  # 文件编辑历史记录

    async def execute(  # 工具执行入口方法
        self,
        *,
        command: Command,  # 操作指令类型
        path: str,  # 操作路径
        file_text: str | None = None,  # `create`命令内容
        view_range: list[int] | None = None,  # `view`命令范围参数
        old_str: str | None = None,  # `str_replace`旧内容
        new_str: str | None = None,  # 替换后的新内容
        insert_line: int | None = None,  # `insert`插入行号
        **kwargs,
    ) -> CLIResult:
        """根据指令执行对应操作并返回结果"""
        _path = Path(path)
        self.validate_path(command, _path)  # 验证路径有效性
        
        if command == "view":  # 查看文件/目录
            return await self.view(_path, view_range)
        elif command == "create":  # 创建新文件
            if file_text is None:
                raise ToolError("创建文件时必须指定`file_text`参数")
            self.write_file(_path, file_text)
            self._file_history[_path].append(file_text)
            return CLIResult(output=f"文件创建成功：{_path}")
        elif command == "str_replace":  # 字符串替换
            if old_str is None:
                raise ToolError("替换操作必须指定`old_str`参数")
            return self.str_replace(_path, old_str, new_str)
        elif command == "insert":  # 插入内容
            if insert_line is None or new_str is None:
                raise ToolError("插入操作必须指定`insert_line`和`new_str`参数")
            return self.insert(_path, insert_line, new_str)
        elif command == "undo_edit":  # 撤销上次编辑
            return self.undo_edit(_path)
        else:  # 无效指令处理
            raise ToolError(f"不支持的指令：{command}")

    def validate_path(self, command: str, path: Path):
        """验证路径与指令的兼容性"""
        if not path.is_absolute():  # 绝对路径检查
            suggested_path = Path("") / path
            raise ToolError(f"路径应为绝对路径，是否指：{suggested_path}?")
        if not path.exists() and command != "create":  # 文件存在性检查
            raise ToolError(f"路径不存在：{path}")
        if path.exists() and command == "create":  # 创建冲突检查
            raise ToolError(f"文件已存在：{path}")
        if path.is_dir() and command != "view":  # 目录操作限制
            raise ToolError(f"目录仅支持`view`指令：{path}")

    async def view(self, path: Path, view_range: list[int] | None = None) -> CLIResult:
        """实现文件/目录查看功能"""
        if path.is_dir():  # 目录查看
            if view_range:
                raise ToolError("目录查看不支持`view_range`参数")
            _, stdout, stderr = await run(f"find {path} -maxdepth 2 -not -path '*/\.*'")
            return CLIResult(output=stdout, error=stderr)
        else:  # 文件查看
            content = self.read_file(path)
            if view_range:  # 处理行号范围参数
                if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
                    raise ToolError("`view_range`应为两个整数的列表")
                lines = content.split("\n")
                start, end = view_range
                if start < 1 or start > len(lines):
                    raise ToolError(f"起始行号{start}超出范围[1-{len(lines)}]")
                if end != -1 and (end < start or end > len(lines)):
                    raise ToolError(f"结束行号{end}超出范围[start-{len(lines)}]")
                content = "\n".join(lines[start-1:end] if end != -1 else lines[start-1:])
            return CLIResult(output=self._make_output(content, str(path), start_line=view_range[0] if view_range else 1))

    def str_replace(self, path: Path, old_str: str, new_str: str | None) -> CLIResult:
        """实现字符串精确替换功能"""
        current_content = self.read_file(path).expandtabs()
        old_str_expanded = old_str.expandtabs()
        new_str_expanded = new_str.expandtabs() if new_str else ""
        
        # 确保旧字符串唯一匹配
        occurrences = current_content.count(old_str_expanded)
        if occurrences == 0:
            raise ToolError(f"未找到匹配内容：{old_str}")
        if occurrences > 1:
            lines = [i+1 for i, line in enumerate(current_content.split("\n")) if old_str in line]
            raise ToolError(f"匹配不唯一，出现在行：{lines}")
        
        # 执行替换并记录历史
        new_content = current_content.replace(old_str_expanded, new_str_expanded)
        self.write_file(path, new_content)
        self._file_history[path].append(current_content)
        
        # 生成编辑片段预览
        replace_line = current_content.split(old_str_expanded)[0].count("\n")
        start = max(0, replace_line - SNIPPET_LINES)
        end = replace_line + SNIPPET_LINES + new_str.count("\n") if new_str else 0
        snippet = "\n".join(new_content.split("\n")[start:end+1])
        
        return CLIResult(output=self._make_output(snippet, f"文件{path}的编辑片段", start+1) + "请确认修改是否符合预期，必要时可再次编辑")

    def insert(self, path: Path, insert_line: int, new_str: str) -> CLIResult:
        """实现指定行后插入内容功能"""
        content = self.read_file(path).expandtabs()
        lines = content.split("\n")
        if insert_line < 0 or insert_line > len(lines):
            raise ToolError(f"无效行号：{insert_line}，有效范围[0-{len(lines)}]")
        
        # 插入新内容并记录历史
        new_lines = lines[:insert_line] + new_str.expandtabs().split("\n") + lines[insert_line:]
        self.write_file(path, "\n".join(new_lines))
        self._file_history[path].append(content)
        
        # 生成插入位置片段预览
        start_line = max(0, insert_line - SNIPPET_LINES)
        snippet_lines = (
            lines[start_line:insert_line] +
            new_str.split("\n") +
            lines[insert_line:insert_line+SNIPPET_LINES]
        )
        snippet = "\n".join(snippet_lines)
        
        return CLIResult(output=self._make_output(snippet, f"文件{path}的插入位置", start_line+1) + "请确认缩进和内容是否正确，必要时可再次编辑")

    def undo_edit(self, path: Path) -> CLIResult:
        """实现撤销最后一次编辑功能"""
        if not self._file_history.get(path):
            raise ToolError(f"文件{path}无编辑历史")
        previous_content = self._file_history[path].pop()
        self.write_file(path, previous_content)
        return CLIResult(output=f"已撤销{path}的最后一次编辑")

    def read_file(self, path: Path) -> str:
        """安全读取文件内容，捕获异常"""
        try:
            return path.read_text()
        except Exception as e:
            raise ToolError(f"读取文件失败：{path}，错误：{str(e)}")

    def write_file(self, path: Path, content: str):
        """安全写入文件内容，捕获异常"""
        try:
            path.write_text(content)
        except Exception as e:
            raise ToolError(f"写入文件失败：{path}，错误：{str(e)}")

    def _make_output(
        self,
        content: str,
        file_descriptor: str,
        init_line: int = 1,
        expand_tabs: bool = True
    ) -> str:
        """生成带行号的文件内容展示"""
        truncated = maybe_truncate(content)
        if expand_tabs:
            truncated = truncated.expandtabs()
        numbered = "\n".join(f"{i+init_line:6}\t{line}" for i, line in enumerate(truncated.split("\n")))
        return f"文件{file_descriptor}的`cat -n`输出：\n{numbered}\n"
