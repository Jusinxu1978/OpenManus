import threading  # 导入线程模块以实现线程同步[1,2,3](@ref)
import tomllib  # 导入tomllib模块用于读取TOML文件[6,7,8](@ref)
from pathlib import Path  # 导入Path类用于文件路径操作[9,10,11](@ref)
from typing import Dict, List, Optional  # 导入类型注解用于类型提示[12,13,14](@ref)

# 导入Pydantic的BaseModel和Field以实现数据验证和设置管理[16,17](@ref)
from pydantic import BaseModel, Field

# 获取项目根目录的函数
def get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).resolve().parent.parent

# 定义项目根目录
PROJECT_ROOT = get_project_root()
# 定义工作区根目录
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"

# 定义LLM配置类
class LLMSettings(BaseModel):
    model: str = Field(..., description="模型名称")  # 模型名称
    base_url: str = Field(..., description="API基础URL")  # API基础URL
    api_key: str = Field(..., description="API密钥")  # API密钥
    max_tokens: int = Field(4096, description="单次请求最大token数")  # 单次请求最大token数
    temperature: float = Field(1.0, description="采样温度")  # 采样温度
    api_type: str = Field(..., description="API类型（AzureOpenai或Openai）")  # API类型（AzureOpenai或Openai）
    api_version: str = Field(..., description="Azure Openai版本（若使用AzureOpenai）")  # Azure Openai版本（若使用AzureOpenai）

# 定义代理配置类
class ProxySettings(BaseModel):
    server: str = Field(None, description="代理服务器地址")  # 代理服务器地址
    username: Optional[str] = Field(None, description="代理用户名")  # 代理用户名
    password: Optional[str] = Field(None, description="代理密码")  # 代理密码

# 定义浏览器配置类
class BrowserSettings(BaseModel):
    headless: bool = Field(False, description="是否以无头模式运行浏览器")  # 是否以无头模式运行浏览器
    disable_security: bool = Field(
        True, description="禁用浏览器安全功能"
    )  # 禁用浏览器安全功能
    extra_chromium_args: List[str] = Field(
        default_factory=list, description="传递给浏览器的额外参数"
    )  # 传递给浏览器的额外参数
    chrome_instance_path: Optional[str] = Field(
        None, description="使用的Chrome实例路径"
    )  # 使用的Chrome实例路径
    wss_url: Optional[str] = Field(
        None, description="通过WebSocket连接到浏览器实例"
    )  # 通过WebSocket连接到浏览器实例
    cdp_url: Optional[str] = Field(
        None, description="通过CDP连接到浏览器实例"
    )  # 通过CDP连接到浏览器实例
    proxy: Optional[ProxySettings] = Field(
        None, description="浏览器代理配置"
    )  # 浏览器代理配置

# 定义应用配置类
class AppConfig(BaseModel):
    llm: Dict[str, LLMSettings]  # LLM配置
    browser_config: Optional[BrowserSettings] = Field(
        None, description="浏览器配置"
    )  # 浏览器配置

    class Config:
        arbitrary_types_allowed = True  # 允许任意类型[17](@ref)

# 定义配置单例类
class Config:
    _instance = None  # 单例实例
    _lock = threading.Lock()  # 线程安全锁[1,3](@ref)
    _initialized = False  # 初始化标志

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._config = None  # 配置字典
                    self._load_initial_config()  # 加载初始配置
                    self._initialized = True  # 设置初始化标志为True

    @staticmethod
    def _get_config_path() -> Path:
        root = PROJECT_ROOT  # 项目根目录
        config_path = root / "config" / "config.toml"  # 配置文件路径
        if config_path.exists():
            return config_path  # 返回存在的配置文件
        example_path = root / "config" / "config.example.toml"  # 示例配置文件路径
        if example_path.exists():
            return example_path  # 返回示例配置文件
        raise FileNotFoundError("配置目录中未找到配置文件")  # 无配置文件时抛出异常

    def _load_config(self) -> dict:
        config_path = self._get_config_path()  # 获取配置文件路径
        with config_path.open("rb") as f:
            return tomllib.load(f)  # 加载TOML配置文件[6,7](@ref)

    def _load_initial_config(self):
        raw_config = self._load_config()  # 加载原始配置
        base_llm = raw_config.get("llm", {})  # 获取基础LLM配置
        llm_overrides = {
            k: v for k, v in raw_config.get("llm", {}).items() if isinstance(v, dict)
        }  # 获取LLM覆盖配置

        default_settings = {
            "model": base_llm.get("model"),
            "base_url": base_llm.get("base_url"),
            "api_key": base_llm.get("api_key"),
            "max_tokens": base_llm.get("max_tokens", 4096),
            "temperature": base_llm.get("temperature", 1.0),
            "api_type": base_llm.get("api_type", ""),
            "api_version": base_llm.get("api_version", ""),
        }  # 定义默认设置

        # 处理浏览器配置
        browser_config = raw_config.get("browser", {})
        browser_settings = None

        if browser_config:
            # 处理代理配置
            proxy_config = browser_config.get("proxy", {})
            proxy_settings = None

            if proxy_config and proxy_config.get("server"):
                proxy_settings = ProxySettings(
                    **{
                        k: v
                        for k, v in proxy_config.items()
                        if k in ["server", "username", "password"] and v
                    }
                )

            # 过滤有效浏览器配置参数
            valid_browser_params = {
                k: v
                for k, v in browser_config.items()
                if k in BrowserSettings.__annotations__ and v is not None
            }

            # 若有代理配置则添加至参数
            if proxy_settings:
                valid_browser_params["proxy"] = proxy_settings

            # 仅当存在有效参数时创建BrowserSettings
            if valid_browser_params:
                browser_settings = BrowserSettings(**valid_browser_params)

        # 创建配置字典
        config_dict = {
            "llm": {
                "default": default_settings,
                **{
                    name: {**default_settings, **override_config}
                    for name, override_config in llm_overrides.items()
                },
            },
            "browser_config": browser_settings,
        }

        self._config = AppConfig(**config_dict)  # 设置配置

    @property
    def llm(self) -> Dict[str, LLMSettings]:
        return self._config.llm  # 返回LLM配置

    @property
    def browser_config(self) -> Optional[BrowserSettings]:
        return self._config.browser_config  # 返回浏览器配置

# 创建配置实例
config = Config()
