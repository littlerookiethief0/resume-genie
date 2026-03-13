"""
用用户本机 Chrome 持久化 context 的 demo，可直接运行验证 Playwright 是否正常。
运行方式（在项目根目录）:
  python python-scripts/demo.py
或:
  cd python-scripts && python demo.py
"""
import sys
import os

# 允许作为脚本直接运行时导入同目录模块
if __name__ == "__main__":
    _dir = os.path.dirname(os.path.abspath(__file__))
    if _dir not in sys.path:
        sys.path.insert(0, _dir)

from playwright.sync_api import sync_playwright
from local_utils import get_data_path

with sync_playwright() as p:
    user_data_dir = get_data_path("chrome_profile")
    os.makedirs(user_data_dir, exist_ok=True)
    context = p.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        channel="chrome",
        headless=False,
        no_viewport=True,
        args=[
            "--start-maximized",
            "--remote-debugging-port=9222",
        ],
    )
    page = context.new_page()
    page.goto("https://www.baidu.com")
    input("按回车关闭...")
    context.close()
