import re
import os
from playwright.sync_api import sync_playwright

try:
    from .local_utils import get_data_path
except ImportError:
    from local_utils import get_data_path


class PlaywrightBrowserManager:
    """
    使用用户本机 Chrome 的持久化 context，减少打包体积。
    支持 with 用法和 start/close_tabs/disconnect 用法。
    """

    def __init__(self, user_data_dir=None, headless=False):
        self.user_data_dir = user_data_dir or get_data_path("chrome_profile")
        self.headless = headless
        self._playwright = None
        self.context = None

    def start(self):
        """启动 Chrome 持久化 context，返回 context。已启动时直接返回当前 context。"""
        if self.context is not None:
            return self.context
        os.makedirs(self.user_data_dir, exist_ok=True)
        self._playwright = sync_playwright().start()
        self.context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            channel="chrome",
            headless=self.headless,
            no_viewport=True,
            args=[
                "--start-maximized",
                "--remote-debugging-port=9222",
            ],
        )
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
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

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
