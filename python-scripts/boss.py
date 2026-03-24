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


class BossCrawler:
    def __init__(
        self,
        stop_event: Optional[threading.Event] = None,
        on_step: Optional[Callable[[int], None]] = None,
        **kwargs: Any, 
    ):
        """kwargs 为前端 run_script('boss', { ... }) 传来的参数，可按需使用。"""
        self.config: dict[str, Any] = kwargs
        self.stop_event: Optional[threading.Event] = stop_event
        self.on_step = on_step or (lambda step: print(f"STEP:{step}", flush=True))
        self.browser_manager: PlaywrightBrowserManager = PlaywrightBrowserManager()
        self.context: BrowserContext = self.browser_manager.start()
        self.browser_manager.close_tabs("zhipin")
        self.page: Page = self.context.new_page()
        self.page_params: dict[str, Any] = {}

    @property
    def stopped(self) -> bool:
        """检查是否收到终止信号。在循环中调用 if self.stopped: break"""
        return self.stop_event is not None and self.stop_event.is_set()

    def monitor_awake_response(self, response):
        if "searchRecommend.json" in response.url or 'geeks.json' in response.url:
            request_params=local_utils.get_url_params(response.url)
            self.page_params.update(request_params)
            self.awaken_list_request(response.json())

    def login(self):
        login_response=self.page.request.get("https://www.zhipin.com/wapi/hunter/h5/hunterManage/checkAuth")
        login_data=login_response.json()
        if login_data.get('message') != "Success":
            self.page.goto("https://www.baidu.com/")
            self.page.locator('//div[@id="chat-input-area"]/textarea').fill("boss直聘")
            self.page.locator('//div[@id="chat-input-area"]/textarea').press("Enter")
            time.sleep(2)
            boss_url=self.page.locator('//a[@data-url="www.zhipin.com/"]').get_attribute('href')
            self.page.goto(boss_url)
            self.page.locator('//span[text()="升级VIP"]').wait_for(state='visible',timeout=60000)
        self.on_step(1)  # 步骤1: 登录网站

    def awaken_list_request(self,response:dict):
        person_list=response['zpData']['geeks']
        for person in person_list:
            try:
                parse_data=parse_request.boss_parse_request(person)['data']
                mopin_data=mopin_request.awaken_request(parse_data)
                wake_resume_dict = json.loads(mopin_data['data']['wakeResume'])
                if wake_resume_dict['msg']=='成功':
                    print(f"唤醒成功: {person['geekCard']['name']}")
                else:
                    print(f"唤醒失败: {person['geekCard']['name']}")
            except Exception as e:
                print(f"处理失败: {e}")
                continue
    
    def run(self):
        # 监听网络响应
        self.page.on("response", self.monitor_awake_response)
        # 判断是否登陆成功，如果未登陆，则跳转登陆页面
        self.login()
        time.sleep(5)
        self.page.goto("https://www.zhipin.com/web/chat/search")
        self.on_step(2)  
        # 等待第二页加载出来，说明条件筛选完成
        contion_response=local_utils.wait_for_condition(self.page,lambda:self.page_params.get('page')=='2')
        if not contion_response:
            return '设置条件超过6分钟，终止脚本执行'
        self.on_step(3)  

        iframe=self.page.frame_locator('//iframe[@name="searchFrame"]')
        # 缓慢滚动，逐渐滚动到最下边
        scroll_func=lambda:iframe.locator('//p[text()="点击加载更多"]').scroll_into_view_if_needed()
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
    BossCrawler().start()
