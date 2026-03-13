import re
import os
from playwright.sync_api import sync_playwright


class PlaywrightBrowserManager:
    """简化的 Playwright 浏览器管理器，支持 context manager"""

    def __init__(self, user_data_dir=None, headless=False):
        self.user_data_dir = user_data_dir
        self.headless = headless
        self._playwright = None
        self.context = None

    def __enter__(self):
        self._playwright = sync_playwright().start()
        self.context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            channel="chrome",
            headless=self.headless,
            no_viewport=True,
            args=["--start-maximized", "--remote-debugging-port=9222"]
        )
        return self.context

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            self.context.close()
        if self._playwright:
            self._playwright.stop()


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
