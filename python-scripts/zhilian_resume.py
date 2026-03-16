import time
import threading
from typing import Any, Callable, Optional
import random
from playwright.sync_api import BrowserContext, Page
import os, json

# 作为包使用时用相对导入；直接 python scripts/boss.py 时用绝对导入
try:
    from . import local_utils, parse_request, mopin_request
    from .playwright_runner import PlaywrightBrowserManager
except ImportError:
    import local_utils
    import parse_request
    import mopin_request
    from playwright_runner import PlaywrightBrowserManager


class ZhilianResumeCrawler:
    def __init__(
        self,
        stop_event: Optional[threading.Event] = None,
        on_step: Optional[Callable[[int], None]] = None,
        on_data: Optional[Callable[[dict], None]] = None,
        **kwargs: Any,
    ):
        """kwargs 为前端 run_script('boss', { ... }) 传来的参数，可按需使用。"""
        self.config: dict[str, Any] = kwargs
        self.stop_event: Optional[threading.Event] = stop_event
        self.on_step = on_step or (lambda step: None)
        self.on_data = on_data or (lambda data: None)
        self.browser_manager: PlaywrightBrowserManager = PlaywrightBrowserManager()
        # 自动判断：有浏览器就CDP连接，没有就新启动
        self.context: BrowserContext = self.browser_manager.start()
        self.browser_manager.close_tabs("liepin")
        self.page: Page = self.context.new_page()

    @property
    def stopped(self) -> bool:
        """检查是否收到终止信号。在循环中调用 if self.stopped: break"""
        return self.stop_event is not None and self.stop_event.is_set()

    def sleep_with_stop(self, seconds: float, interval: float = 0.2) -> bool:
        """可中断睡眠；返回 True 表示期间收到停止信号。"""
        end = time.time() + max(0.0, seconds)
        while time.time() < end:
            if self.stopped:
                return True
            remaining = end - time.time()
            time.sleep(min(interval, remaining))
        return self.stopped


    def is_expire_date_valid(self,expire_date_str, threshold_date="2026-05-10"):
        """
        检查有效期字符串，若有效期大于指定日期，返回 False，否则返回 True。
        :param expire_date_str: 例 '有效期至2026年05月10日'
        :param threshold_date: 'YYYY-MM-DD'
        """
        if not expire_date_str:
            return True
        import re
        m = re.search(r'有效期至(\d{4})年(\d{2})月(\d{2})日', expire_date_str)
        if m:
            expire_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            from datetime import datetime
            expire_dt = datetime.strptime(expire_date, "%Y-%m-%d")
            threshold_dt = datetime.strptime(threshold_date, "%Y-%m-%d")
            return expire_dt <= threshold_dt
        return True
    
    
    def run(self):
        raw_days = self.config.get("days") or 66
        try:
            days = int(raw_days)
            if days <= 0:
                raise ValueError
        except (TypeError, ValueError):
            print(f"参数错误: days 必须为正整数，当前值: {raw_days!r}")
            return

        # 判断mopin 是否登陆了 是否正常
        mopin_login_response=self.page.request.get("https://mopinapi.58.com/account/currentInfo")
        mopin_login_data=mopin_login_response.json()
        if mopin_login_data.get('msg') != "成功":
            self.page.goto("https://mopin.58.com/login")
            self.page.locator('//span[contains(text(),"做单")]').wait_for(state='visible',timeout=60000)
        mopin_cookie = local_utils.get_cookie_string(self.context,urls=["https://lpt.liepin.com/account/info"])

        # 判断liepin直聘是否登陆了
        login_response=self.page.request.post("https://api-lpt.liepin.com/api/com.liepin.future.common.access")
        if not login_response.ok:
            self.page.goto("https://lpt.liepin.com/login")
            self.page.locator('//span[text()="招聘数据"]').wait_for(state='visible',timeout=60000)
        if self.stopped:
            return
        # 打开网址
        self.page.goto("https://rd6.zhaopin.com/app/im")
        # 点击有简历
        self.page.locator('//div[contains(text(),"已获取电话")]').click()
        # if self.sleep_with_stop(10):
        #     return
        # 获取第一个简历
        print(1111)
           
    def start(self):
        try:
            self.run()
        finally:
            print('finally')
            self.page.close()
            self.browser_manager.disconnect()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=99, help='过滤天数')
    args = parser.parse_args()
    ZhilianResumeCrawler(days=args.days).start()
