# tool/planning.py
from typing import Dict, List, Literal, Optional

from app.exceptions import ToolError
from app.tool.base import BaseTool, ToolResult

_PLANNING_TOOL_DESCRIPTION = """
A planning tool that allows the agent to create and manage plans for solving complex tasks.
The tool provides functionality for creating plans, updating plan steps, and tracking progress.
"""

class PlanningTool(BaseTool):
    """
    实现计划管理功能的工具类，允许代理创建、更新和跟踪复杂任务的计划
    """
    name: str = "planning"  # 工具名称标识符
    description: str = _PLANNING_TOOL_DESCRIPTION  # 工具功能描述
    parameters: dict = {  # 工具参数定义
        "type": "object",
        "properties": {  # 参数属性集合
            "command": {  # 必要参数：操作指令类型
                "description": "要执行的命令类型，支持创建/更新/列出等操作",
                "enum": [  # 允许的命令枚举值
                    "create", "update", "list", "get", "set_active", "mark_step", "delete"
                ],
                "type": "string"
            },
            "plan_id": {  # 计划唯一标识参数
                "description": "计划ID，创建/更新等操作时必填",
                "type": "string"
            },
            "title": {  # 计划标题参数
                "description": "计划标题，创建时必填，更新时可选",
                "type": "string"
            },
            "steps": {  # 计划步骤参数
                "description": "步骤列表，创建时必填，更新时可选",
                "type": "array",
                "items": {"type": "string"}
            },
            "step_index": {  # 步骤索引参数
                "description": "步骤索引位置（0开始），标记步骤时必填",
                "type": "integer"
            },
            "step_status": {  # 步骤状态参数
                "description": "步骤状态值，可选值：not_started/in_progress/completed/blocked",
                "enum": ["not_started", "in_progress", "completed", "blocked"],
                "type": "string"
            },
            "step_notes": {  # 步骤备注参数
                "description": "步骤备注信息，标记步骤时可选",
                "type": "string"
            }
        },
        "required": ["command"],  # 必填参数列表
        "additionalProperties": False  # 禁用额外属性
    }

    plans: dict = {}  # 存储所有计划的字典
    _current_plan_id: Optional[str] = None  # 当前激活的计划ID

    async def execute(  # 工具执行入口方法
        self,
        *,
        command: Literal[  # 操作指令类型
            "create", "update", "list", "get", "set_active", "mark_step", "delete"
        ],
        plan_id: Optional[str] = None,
        title: Optional[str] = None,
        steps: Optional[List[str]] = None,
        step_index: Optional[int] = None,
        step_status: Optional[Literal["not_started", "in_progress", "completed", "blocked"]] = None,
        step_notes: Optional[str] = None,
        **kwargs,
    ):
        """执行具体操作的分发方法"""
        if command == "create":  # 创建新计划
            return self._create_plan(plan_id, title, steps)
        elif command == "update":  # 更新现有计划
            return self._update_plan(plan_id, title, steps)
        elif command == "list":  # 列出所有计划
            return self._list_plans()
        elif command == "get":  # 获取指定计划详情
            return self._get_plan(plan_id)
        elif command == "set_active":  # 设置当前激活计划
            return self._set_active_plan(plan_id)
        elif command == "mark_step":  # 标记步骤状态
            return self._mark_step(plan_id, step_index, step_status, step_notes)
        elif command == "delete":  # 删除计划
            return self._delete_plan(plan_id)
        else:  # 无效指令处理
            raise ToolError(f"不支持的指令：{command}")

    def _create_plan(  # 创建新计划的私有方法
        self, plan_id: Optional[str], title: Optional[str], steps: Optional[List[str]]
    ) -> ToolResult:
        """创建新计划的核心实现"""
        if not plan_id:  # 检查必要参数
            raise ToolError("创建计划时必须指定plan_id")
        if plan_id in self.plans:  # 检查ID是否重复
            raise ToolError(f"ID为{plan_id}的计划已存在")
        if not title:  # 标题参数校验
            raise ToolError("必须提供计划标题")
        if not steps or not isinstance(steps, list) or not all(isinstance(s, str) for s in steps):
            raise ToolError("步骤必须为非空字符串列表")
        # 初始化步骤状态和备注
        plan = {
            "plan_id": plan_id,
            "title": title,
            "steps": steps,
            "step_statuses": ["not_started"] * len(steps),
            "step_notes": [""] * len(steps),
        }
        self.plans[plan_id] = plan  # 存储新计划
        self._current_plan_id = plan_id  # 设置为当前激活计划
        return ToolResult(output=f"计划创建成功：{plan_id}\n\n{self._format_plan(plan)}")

    def _update_plan(  # 更新计划的私有方法
        self, plan_id: Optional[str], title: Optional[str], steps: Optional[List[str]]
    ) -> ToolResult:
        """更新现有计划的核心实现"""
        if not plan_id:  # 参数校验
            raise ToolError("更新计划时必须指定plan_id")
        if plan_id not in self.plans:  # 检查是否存在
            raise ToolError(f"未找到ID为{plan_id}的计划")
        plan = self.plans[plan_id]
        if title:  # 更新标题
            plan["title"] = title
        if steps:  # 更新步骤时保留原有状态
            if not isinstance(steps, list) or not all(isinstance(s, str) for s in steps):
                raise ToolError("步骤必须为字符串列表")
            old_steps = plan["steps"]
            old_statuses = plan["step_statuses"]
            old_notes = plan["step_notes"]
            new_statuses = []
            new_notes = []
            for i, step in enumerate(steps):
                if i < len(old_steps) and step == old_steps[i]:
                    new_statuses.append(old_statuses[i])
                    new_notes.append(old_notes[i])
                else:
                    new_statuses.append("not_started")
                    new_notes.append("")
            plan["steps"] = steps
            plan["step_statuses"] = new_statuses
            plan["step_notes"] = new_notes
        return ToolResult(output=f"计划更新成功：{plan_id}\n\n{self._format_plan(plan)}")

    def _list_plans(self) -> ToolResult:  # 列出所有计划
        """获取所有计划的概要信息"""
        if not self.plans:  # 空处理
            return ToolResult(output="暂无任何计划，请使用create指令创建")
        output = "可用计划列表：\n"
        for pid, p in self.plans.items():
            current = " (当前)" if pid == self._current_plan_id else ""
            completed = sum(1 for s in p["step_statuses"] if s == "completed")
            output += f"• {pid}{current}: {p['title']} - {completed}/{len(p['steps'])}步骤完成\n"
        return ToolResult(output=output)

    def _get_plan(self, plan_id: Optional[str]) -> ToolResult:  # 获取计划详情
        """获取指定计划的详细信息"""
        if not plan_id and not self._current_plan_id:  # 参数处理
            raise ToolError("未指定计划ID且没有当前激活计划")
        plan_id = plan_id or self._current_plan_id
        if plan_id not in self.plans:
            raise ToolError(f"未找到ID为{plan_id}的计划")
        return ToolResult(output=self._format_plan(self.plans[plan_id]))

    def _set_active_plan(self, plan_id: Optional[str]) -> ToolResult:  # 设置当前计划
        """设置当前激活的计划"""
        if not plan_id:
            raise ToolError("必须指定要激活的plan_id")
        if plan_id not in self.plans:
            raise ToolError(f"未找到ID为{plan_id}的计划")
        self._current_plan_id = plan_id
        return ToolResult(output=f"已激活计划：{plan_id}\n\n{self._format_plan(self.plans[plan_id])}")

    def _mark_step(  # 标记步骤状态
        self,
        plan_id: Optional[str],
        step_index: Optional[int],
        step_status: Optional[str],
        step_notes: Optional[str],
    ) -> ToolResult:
        """标记指定步骤的状态和备注"""
        plan_id = plan_id or self._current_plan_id  # 使用当前计划
        if not plan_id:
            raise ToolError("未指定计划ID且没有当前激活计划")
        if plan_id not in self.plans:
            raise ToolError(f"未找到ID为{plan_id}的计划")
        if step_index is None:
            raise ToolError("必须指定步骤索引")
        plan = self.plans[plan_id]
        if step_index < 0 or step_index >= len(plan["steps"]):
            raise ToolError(f"步骤索引{step_index}超出范围")
        if step_status and step_status not in ["not_started", "in_progress", "completed", "blocked"]:
            raise ToolError("无效的状态值")
        if step_status:
            plan["step_statuses"][step_index] = step_status
        if step_notes:
            plan["step_notes"][step_index] = step_notes
        return ToolResult(output=f"步骤{step_index}已更新\n\n{self._format_plan(plan)}")

    def _delete_plan(self, plan_id: Optional[str]) -> ToolResult:  # 删除计划
        """删除指定计划"""
        if not plan_id:
            raise ToolError("必须指定要删除的plan_id")
        if plan_id not in self.plans:
            raise ToolError(f"未找到ID为{plan_id}的计划")
        del self.plans[plan_id]
        if self._current_plan_id == plan_id:
            self._current_plan_id = None
        return ToolResult(output=f"已删除计划：{plan_id}")

    def _format_plan(self, plan: Dict) -> str:  # 格式化输出计划信息
        """将计划数据格式化为可读字符串"""
        output = f"计划：{plan['title']} (ID：{plan['plan_id']})\n"
        output += "=" * len(output) + "\n\n"
        total = len(plan["steps"])
        completed = sum(s == "completed" for s in plan["step_statuses"])
        output += f"进度：{completed}/{total} ({(completed/total*100):.1f}%)\n"
        output += f"状态：完成{completed}个，进行中{plan['step_statuses'].count('in_progress')}个，阻塞{plan['step_statuses'].count('blocked')}个，未开始{plan['step_statuses'].count('not_started')}个\n\n"
        output += "步骤详情：\n"
        for i, (step, status, note) in enumerate(zip(plan["steps"], plan["step_statuses"], plan["step_notes"])):
            status_sym = {
                "not_started": "□",
                "in_progress": "▶",
                "completed": "✓",
                "blocked": "‼"
            }.get(status, "□")
            output += f"{i}. {status_sym} {step}\n"
            if note:
                output += f"   备注：{note}\n"
        return output
