import re
import os
from camoufox.sync_api import Camoufox

try:
    from .local_utils import get_data_path
except ImportError:
    from local_utils import get_data_path


class _FirefoxContextWrapper:
    """
    包装 Firefox 持久化 context：new_page() 优先复用已有页面，避免多窗口。
    Firefox 中 new_page() 会开新窗口而非新标签。配合 viewport=None 使用实际窗口尺寸，显示与正常浏览器一致。
    """

    def __init__(self, context):
        self._context = context

    def new_page(self):
        if self._context.pages:
            return self._context.pages[0]
        return self._context.new_page()

    def __getattr__(self, name):
        return getattr(self._context, name)


class PlaywrightBrowserManager:
    """
    使用 Camoufox(Firefox) 持久化 context。
    支持 with 用法和 start/close_tabs/disconnect 用法。
    """

    def __init__(self, user_data_dir=None, headless=False):
        self.user_data_dir = user_data_dir or get_data_path("camoufox_profile")
        self.headless = headless
        self._camoufox = None
        self.context = None
        # 固定 UA，避免每次启动 UA 变化；可用环境变量覆盖
        self.user_agent = os.environ.get(
            "RESUME_GENIE_USER_AGENT",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
        )

    def start(self):
        """启动 Camoufox 持久化 context，返回 context。已启动时直接返回当前 context。"""
        if self.context is not None:
            return self.context
        os.makedirs(self.user_data_dir, exist_ok=True)
        launch_kw = dict(
            persistent_context=True,
            user_data_dir=self.user_data_dir,
            headless=self.headless,
            os="macos",
            locale="zh-CN,zh,en-US",
            user_agent=self.user_agent,
            viewport=None,  # 使用实际窗口尺寸，与正常打开浏览器一致
            color_scheme="light",
            fonts=[
                "PingFang SC",
                "Hiragino Sans GB",
                "Helvetica Neue",
                "Arial",
            ],
            config={
                # 固定字体度量随机种子，减少中文站点字体抖动/乱码
                "fonts:spacing_seed": 0,
                # 关闭深色主题，使用标准 Firefox 浅色 UI
                "disableTheming": True,
            },
        )
        # 可选：通过环境变量指定系统 Firefox 可执行文件
        # 例如 macOS: /Applications/Firefox.app/Contents/MacOS/firefox
        firefox_path = os.environ.get("RESUME_GENIE_FIREFOX_PATH")
        if firefox_path and os.path.isfile(firefox_path):
            launch_kw["executable_path"] = firefox_path

        self._camoufox = Camoufox(**launch_kw)
        raw_context = self._camoufox.__enter__()
        self.context = _FirefoxContextWrapper(raw_context)

        return self.context

    def close_tabs(self, keyword: str):
        """关闭 URL 中包含 keyword 的页面。"""
        if self.context is None:
            return
        for page in list(self.context.pages):
            try:
                if keyword in page.url:
                    page.close()
            except Exception:
                pass

    def disconnect(self):
        """关闭 context 并停止 Playwright。"""
        if self.context:
            try:
                self.context.close()
            except Exception:
                pass
            self.context = None
        if self._camoufox:
            try:
                self._camoufox.__exit__(None, None, None)
            except Exception:
                pass
            self._camoufox = None

    def __enter__(self):
        self.start()
        return self.context

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


    @staticmethod
    def action_and_capture(page, action, url_pattern, timeout=30000):
        """执行动作并捕获匹配的网络响应"""
        def match(resp):
            return url_pattern in resp.url if isinstance(url_pattern, str) else re.search(url_pattern, resp.url)
        try:
            with page.expect_response(match, timeout=timeout) as resp_info:
                action()
            return resp_info.value.json()
        except Exception:
            return {}

    @staticmethod
    def action_and_capture_binary(page, action, url_pattern, timeout=30000):
        """执行动作并捕获二进制响应"""
        def match(resp):
            return url_pattern in resp.url if isinstance(url_pattern, str) else re.search(url_pattern, resp.url)
        try:
            with page.expect_response(match, timeout=timeout) as resp_info:
                action()
            return resp_info.value.body()
        except Exception:
            return b""

    @staticmethod
    def action_and_download(page, action, save_path, timeout=30000):
        """执行动作触发下载并保存文件"""
        with page.expect_download(timeout=timeout) as download_info:
            action()
        download = download_info.value
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        with open(download.path(), "rb") as f:
            binary_data = f.read()
        with open(save_path, "wb") as f:
            f.write(binary_data)
        return binary_data

    
    def action_and_download_binary(self, page, action, save_path, timeout=30000):
        """
        执行动作触发下载，将文件保存到 save_path，并返回 PDF 二进制数据。

        参数:
            page: Playwright 页面
            action: 触发下载的 lambda，如 lambda: page.locator("...").click()
            save_path: 保存文件的完整路径（含文件名）
        返回:
            bytes: 文件二进制数据
        """
        with page.expect_download(timeout=timeout) as download_info:
            action()
        download = download_info.value
        with open(download.path(), "rb") as f:
            binary_data = f.read()
        dirpart = os.path.dirname(save_path)
        if dirpart:
            os.makedirs(dirpart, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(binary_data)
        return binary_data
