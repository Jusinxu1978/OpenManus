from typing import Any, List, Optional, Type, Union, get_args, get_origin  # 导入类型提示相关模块
from pydantic import BaseModel, Field  # 导入Pydantic数据模型基类和字段配置工具
from app.tool import BaseTool  # 导入工具基类

class CreateChatCompletion(BaseTool):
    name: str = "create_chat_completion"  # 工具名称标识符
    description: str = "Creates a structured completion with specified output formatting."  # 功能描述文本

    type_mapping: dict = {  # 基础类型到JSON schema类型的映射
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        dict: "object",
        list: "array",
    }
    response_type: Optional[Type] = None  # 响应类型定义（可选）
    required: List[str] = Field(default_factory=lambda: ["response"])  # 必要字段列表

    def __init__(self, response_type: Optional[Type] = str):
        """初始化方法：设置响应类型并构建参数schema"""
        super().__init__()
        self.response_type = response_type
        self.parameters = self._build_parameters()  # 根据响应类型构建参数结构

    def _build_parameters(self) -> dict:
        """根据响应类型构建JSON schema参数定义"""
        if self.response_type == str:
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "string",
                        "description": "The response text that should be delivered to the user.",
                    },
                },
                "required": self.required,
            }

        if isinstance(self.response_type, type) and issubclass(self.response_type, BaseModel):
            schema = self.response_type.model_json_schema()
            return {
                "type": "object",
                "properties": schema["properties"],
                "required": schema.get("required", self.required),
            }

        return self._create_type_schema(self.response_type)  # 处理复杂类型

    def _create_type_schema(self, type_hint: Type) -> dict:
        """为给定类型生成JSON schema"""
        origin = get_origin(type_hint)
        args = get_args(type_hint)

        if origin is None:  # 基础类型处理
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": self.type_mapping.get(type_hint, "string"),
                        "description": f"Response of type {type_hint.__name__}",
                    }
                },
                "required": self.required,
            }

        if origin is list:  # 列表类型处理
            item_type = args[0] if args else Any
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "array",
                        "items": self._get_type_info(item_type),
                    }
                },
                "required": self.required,
            }

        if origin is dict:  # 字典类型处理
            value_type = args[1] if len(args) > 1 else Any
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "object",
                        "additionalProperties": self._get_type_info(value_type),
                    }
                },
                "required": self.required,
            }

        if origin is Union:  # 联合类型处理
            return self._create_union_schema(args)

        return self._build_parameters()

    def _get_type_info(self, type_hint: Type) -> dict:
        """获取单个类型的schema信息"""
        if isinstance(type_hint, type) and issubclass(type_hint, BaseModel):
            return type_hint.model_json_schema()

        return {
            "type": self.type_mapping.get(type_hint, "string"),
            "description": f"Value of type {getattr(type_hint, '__name__', 'any')}",
        }

    def _create_union_schema(self, types: tuple) -> dict:
        """为联合类型生成schema"""
        return {
            "type": "object",
            "properties": {
                "response": {"anyOf": [self._get_type_info(t) for t in types]}
            },
            "required": self.required,
        }

    async def execute(self, required: list | None = None, **kwargs) -> Any:
        """执行类型转换的核心方法"""
        required = required or self.required

        if isinstance(required, list) and len(required) > 0:
            if len(required) == 1:
                required_field = required[0]
                result = kwargs.get(required_field, "")
            else:
                return {field: kwargs.get(field, "") for field in required}
        else:
            required_field = "response"
            result = kwargs.get(required_field, "")

        if self.response_type == str:
            return result

        if isinstance(self.response_type, type) and issubclass(self.response_type, BaseModel):
            return self.response_type(**kwargs)

        if get_origin(self.response_type) in (list, dict):
            return result

        try:
            return self.response_type(result)
        except (ValueError, TypeError):
            return result
