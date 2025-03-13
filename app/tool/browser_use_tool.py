import asyncio  # 导入异步IO库，用于浏览器操作的异步执行
import json  # JSON数据处理模块
from typing import Optional  # 导入可选类型提示

from browser_use import Browser as BrowserUseBrowser  # 浏览器控制核心类
from browser_use import BrowserConfig  # 浏览器配置类
from browser_use.browser.context import BrowserContext, BrowserContextConfig  # 浏览器上下文管理类
from browser_use.dom.service import DomService  # DOM操作服务类
from pydantic import Field, field_validator  # Pydantic字段验证工具
from pydantic_core.core_schema import ValidationInfo  # 验证信息类

from app.config import config  # 应用配置模块
from app.tool.base import BaseTool, ToolResult  # 工具基类和结果类

MAX_LENGTH = 2000  # HTML内容截断最大长度

_BROWSER_DESCRIPTION = """  # 浏览器工具功能描述文本
Interact with a web browser to perform various actions such as navigation, element interaction,
content extraction, and tab management. Supported actions include:
- 'navigate': Go to a specific URL
- 'click': Click an element by index
- 'input_text': Input text into an element
- 'screenshot': Capture a screenshot
- 'get_html': Get page HTML content
- 'get_text': Get text content of the page
- 'read_links': Get all links on the page
- 'execute_js': Execute JavaScript code
- 'scroll': Scroll the page
- 'switch_tab': Switch to a specific tab
- 'new_tab': Open a new tab
- 'close_tab': Close the current tab
- 'refresh': Refresh the current page
"""

class BrowserUseTool(BaseTool):
    name: str = "browser_use"  # 工具名称标识符
    description: str = _BROWSER_DESCRIPTION  # 功能描述文本
    parameters: dict = {  # 参数定义
        "type": "object",
        "properties": {  # 参数属性集合
            "action": {  # 必要参数：操作类型
                "type": "string",
                "enum": [  # 支持的操作列表
                    "navigate", "click", "input_text", "screenshot",
                    "get_html", "get_text", "execute_js", "scroll",
                    "switch_tab", "new_tab", "close_tab", "refresh"
                ],
                "description": "The browser action to perform"
            },
            "url": {  # URL参数（部分操作需要）
                "type": "string",
                "description": "URL for 'navigate' or 'new_tab' actions"
            },
            "index": {  # 元素索引（用于点击/输入操作）
                "type": "integer",
                "description": "Element index for 'click' or 'input_text' actions"
            },
            "text": {  # 输入文本内容
                "type": "string",
                "description": "Text for 'input_text' action"
            },
            "script": {  # JavaScript脚本内容
                "type": "string",
                "description": "JavaScript code for 'execute_js' action"
            },
            "scroll_amount": {  # 滚动像素数
                "type": "integer",
                "description": "Pixels to scroll (positive for down, negative for up)"
            },
            "tab_id": {  # 标签页ID（用于切换操作）
                "type": "integer",
                "description": "Tab ID for 'switch_tab' action"
            },
        },
        "required": ["action"],  # 必要参数列表
        "dependencies": {  # 参数依赖关系
            "navigate": ["url"],
            "click": ["index"],
            "input_text": ["index", "text"],
            "execute_js": ["script"],
            "switch_tab": ["tab_id"],
            "new_tab": ["url"],
            "scroll": ["scroll_amount"],
        },
    }

    lock: asyncio.Lock = Field(default_factory=asyncio.Lock)  # 异步锁确保线程安全
    browser: Optional[BrowserUseBrowser] = Field(default=None, exclude=True)  # 浏览器实例
    context: Optional[BrowserContext] = Field(default=None, exclude=True)  # 浏览器上下文
    dom_service: Optional[DomService] = Field(default=None, exclude=True)  # DOM操作服务

    @field_validator("parameters", mode="before")  # 参数验证装饰器
    def validate_parameters(cls, v: dict, info: ValidationInfo) -> dict:
        """参数验证方法：确保参数不为空"""
        if not v:
            raise ValueError("Parameters cannot be empty")
        return v

    async def _ensure_browser_initialized(self) -> BrowserContext:
        """确保浏览器和上下文已初始化"""
        if self.browser is None:  # 初始化浏览器配置
            browser_config_kwargs = {"headless": False}
            if config.browser_config:
                from browser_use.browser.browser import ProxySettings
                if config.browser_config.proxy and config.browser_config.proxy.server:
                    browser_config_kwargs["proxy"] = ProxySettings(
                        server=config.browser_config.proxy.server,
                        username=config.browser_config.proxy.username,
                        password=config.browser_config.proxy.password,
                    )
                browser_attrs = [
                    "headless", "disable_security", "extra_chromium_args",
                    "chrome_instance_path", "wss_url", "cdp_url"
                ]
                for attr in browser_attrs:
                    value = getattr(config.browser_config, attr, None)
                    if value is not None and (not isinstance(value, list) or value):
                        browser_config_kwargs[attr] = value
            self.browser = BrowserUseBrowser(BrowserConfig(**browser_config_kwargs))
        if self.context is None:  # 初始化浏览器上下文
            context_config = BrowserContextConfig()
            if config.browser_config and config.browser_config.new_context_config:
                context_config = config.browser_config.new_context_config
            self.context = await self.browser.new_context(context_config)
            self.dom_service = DomService(await self.context.get_current_page())
        return self.context

    async def execute(
        self,
        action: str,
        url: Optional[str] = None,
        index: Optional[int] = None,
        text: Optional[str] = None,
        script: Optional[str] = None,
        scroll_amount: Optional[int] = None,
        tab_id: Optional[int] = None,
        **kwargs,
    ) -> ToolResult:
        """执行浏览器操作的核心方法"""
        async with self.lock:  # 线程安全锁
            try:
                context = await self._ensure_browser_initialized()  # 确保环境已初始化
                if action == "navigate":  # 导航操作
                    if not url:
                        return ToolResult(error="URL is required for 'navigate' action")
                    await context.navigate_to(url)
                    return ToolResult(output=f"Navigated to {url}")
                elif action == "click":  # 点击元素
                    if index is None:
                        return ToolResult(error="Index is required for 'click' action")
                    element = await context.get_dom_element_by_index(index)
                    if not element:
                        return ToolResult(error=f"Element with index {index} not found")
                    download_path = await context._click_element_node(element)
                    output = f"Clicked element at index {index}"
                    if download_path:
                        output += f" - Downloaded file to {download_path}"
                    return ToolResult(output=output)
                elif action == "input_text":  # 输入文本
                    if index is None or not text:
                        return ToolResult(
                            error="Index and text are required for 'input_text' action"
                        )
                    element = await context.get_dom_element_by_index(index)
                    if not element:
                        return ToolResult(error=f"Element with index {index} not found")
                    await context._input_text_element_node(element, text)
                    return ToolResult(
                        output=f"Input '{text}' into element at index {index}"
                    )
                elif action == "screenshot":  # 截图操作
                    screenshot = await context.take_screenshot(full_page=True)
                    return ToolResult(
                        output=f"Screenshot captured (base64 length: {len(screenshot)})",
                        system=screenshot,
                    )
                elif action == "get_html":  # 获取HTML内容
                    html = await context.get_page_html()
                    truncated = html[:MAX_LENGTH] + "..." if len(html) > MAX_LENGTH else html
                    return ToolResult(output=truncated)
                elif action == "get_text":  # 获取页面文本
                    text = await context.execute_javascript("document.body.innerText")
                    return ToolResult(output=text)
                elif action == "read_links":  # 读取所有链接
                    links = await context.execute_javascript(
                        "document.querySelectorAll('a[href]').forEach((elem) => {if (elem.innerText) {console.log(elem.innerText, elem.href)}})"
                    )
                    return ToolResult(output=links)
                elif action == "execute_js":  # 执行JS代码
                    if not script:
                        return ToolResult(
                            error="Script is required for 'execute_js' action"
                        )
                    result = await context.execute_javascript(script)
                    return ToolResult(output=str(result))
                elif action == "scroll":  # 滚动页面
                    if scroll_amount is None:
                        return ToolResult(
                            error="Scroll amount is required for 'scroll' action"
                        )
                    await context.execute_javascript(f"window.scrollBy(0, {scroll_amount});")
                    direction = "down" if scroll_amount > 0 else "up"
                    return ToolResult(
                        output=f"Scrolled {direction} by {abs(scroll_amount)} pixels"
                    )
                elif action == "switch_tab":  # 切换标签页
                    if tab_id is None:
                        return ToolResult(
                            error="Tab ID is required for 'switch_tab' action"
                        )
                    await context.switch_to_tab(tab_id)
                    return ToolResult(output=f"Switched to tab {tab_id}")
                elif action == "new_tab":  # 新建标签页
                    if not url:
                        return ToolResult(error="URL is required for 'new_tab' action")
                    await context.create_new_tab(url)
                    return ToolResult(output=f"Opened new tab with URL {url}")
                elif action == "close_tab":  # 关闭当前标签页
                    await context.close_current_tab()
                    return ToolResult(output="Closed current tab")
                elif action == "refresh":  # 刷新页面
                    await context.refresh_page()
                    return ToolResult(output="Refreshed current page")
                else:
                    return ToolResult(error=f"Unknown action: {action}")
            except Exception as e:
                return ToolResult(error=f"Browser action '{action}' failed: {str(e)}")

    async def get_current_state(self) -> ToolResult:
        """获取浏览器当前状态"""
        async with self.lock:
            try:
                context = await self._ensure_browser_initialized()
                state = await context.get_state()
                state_info = {
                    "url": state.url,
                    "title": state.title,
                    "tabs": [tab.model_dump() for tab in state.tabs],
                    "interactive_elements": state.element_tree.clickable_elements_to_string(),
                }
                return ToolResult(output=json.dumps(state_info))
            except Exception as e:
                return ToolResult(error=f"Failed to get browser state: {str(e)}")

    async def cleanup(self):
        """清理浏览器资源"""
        async with self.lock:
            if self.context is not None:
                await self.context.close()
                self.context = None
                self.dom_service = None
            if self.browser is not None:
                await self.browser.close()
                self.browser = None

    def __del__(self):
        """对象销毁时的资源清理"""
        if self.browser is not None or self.context is not None:
            try:
                asyncio.run(self.cleanup())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self.cleanup())
                loop.close()
