import time
import threading
from typing import Any, Callable, Optional
import re
from playwright.sync_api import BrowserContext, Page
import mopin_request
import parse_request
import json
import random

import local_utils
# 作为包使用时用相对导入；直接 python scripts/boss.py 时用绝对导入
try:
    from .playwright_runner import PlaywrightBrowserManager
except ImportError:
    from playwright_runner import PlaywrightBrowserManager


class ZhilianCrawler:
    def __init__(
        self,
        stop_event: Optional[threading.Event] = None,
        on_step: Optional[Callable[[int], None]] = None,
        **kwargs: Any,
    ):
        """kwargs 为前端 run_script('boss', { ... }) 传来的参数，可按需使用。"""
        self.config: dict[str, Any] = kwargs
        self.stop_event: Optional[threading.Event] = stop_event
        self.on_step = on_step or (lambda step: None)
        self.browser_manager: PlaywrightBrowserManager = PlaywrightBrowserManager()
        self.context: BrowserContext = self.browser_manager.start()
        self.browser_manager.close_tabs("zhaopin")
        self.page: Page = self.context.new_page()
        self.page_params: dict[str, Any] = {}

    @property
    def stopped(self) -> bool:
        """检查是否收到终止信号。在循环中调用 if self.stopped: break"""
        return self.stop_event is not None and self.stop_event.is_set()

    def monitor_awake_response(self, response):
        if "search/list" in response.url:
            self.awaken_list_request(response.json())

    def login(self):
        login_response=self.page.request.get("https://rd6.zhaopin.com/api/im/user")
        login_data=login_response.json()
        if login_data.get('code') != 200:
            self.page.goto("https://passport.zhaopin.com/org/login")
            self.page.locator('//span[text()="服务中心"]').wait_for(state='visible',timeout=60000)
        self.on_step(1)  # 步骤1: 登录网站


    def awaken_list_request(self,response:dict):
        person_list=response['data']['list']
        for person in person_list:
            try:
                parse_data=parse_request.zhilian_parse_request(person)['data']
                mopin_data=mopin_request.awaken_request(parse_data)
                wake_resume_dict = json.loads(mopin_data['data']['wakeResume'])
                if wake_resume_dict['msg']=='成功':
                    print(f"唤醒成功: {person['userName']}")
                else:
                    print(f"唤醒失败: {person['userName']}")
            except Exception as e:
                print(f"处理失败: {e}")
                continue
    
    def run(self):
        # 监听网络响应
        self.page.on("response", self.monitor_awake_response)
        # 判断是否登陆成功，如果未登陆，则跳转登陆页面
        self.login()

        self.page.goto("https://rd6.zhaopin.com/app/search")

        # 等待第二页加载出来，说明条件筛选完成

        self.page.locator('xpath=//a[@class="km-pagination__pager km-pagination__pager--current" and text()="2"]').wait_for(state='visible',timeout=60000)
        self.on_step(2)  

        self.on_step(3)  

        scroll_func=lambda:self.page.locator('//i[@class="km-icon sati sati-angle-right"]').click()
        scroll_flag=local_utils.scroll_load_bottom(scroll_func)
        print(scroll_flag)



    def start(self):
        try:
            self.run()
        finally:
            print('finally')
            self.page.close()
            self.browser_manager.disconnect()


if __name__ == "__main__":
    ZhilianCrawler().start()
