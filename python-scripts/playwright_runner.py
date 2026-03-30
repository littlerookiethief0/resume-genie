import re
import os
import platform
import struct
import subprocess
import sys
from pathlib import Path
from playwright.sync_api import Browser, BrowserContext, Page

try:
    from .local_utils import get_data_path
except ImportError:
    from local_utils import get_data_path


class PlaywrightBrowserManager:
    def __init__(self, user_data_dir=None, headless=False):
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None

        self._playwright = None

    def start(self):

        from playwright.sync_api import sync_playwright

        if self._playwright is None:
            self._playwright = sync_playwright().start()

        self.browser = self._playwright.chromium.connect_over_cdp(
            "ws://127.0.0.1:9222/devtools/browser"
        )

        self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
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
