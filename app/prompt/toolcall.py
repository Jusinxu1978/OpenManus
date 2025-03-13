# 定义系统提示（SYSTEM_PROMPT）：
# 指定代理的核心能力为执行工具调用
SYSTEM_PROMPT = "You are an agent that can execute tool calls"

# 下一步提示（NEXT_STEP_PROMPT）：
# 当需要终止交互时，使用`terminate`工具/函数调用
NEXT_STEP_PROMPT = (
    "If you want to stop interaction, use `terminate` tool/function call."
)
