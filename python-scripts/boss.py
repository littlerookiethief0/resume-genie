import time
import threading
from typing import Any, Callable, Optional
import re
from patchright.sync_api import BrowserContext, Page
import mopin_request
import parse_request
import json
import random

import local_utils
# 作为包使用时用相对导入；直接 python scripts/boss.py 时用绝对导入
try:
    from .app_logger import emit_step, get_logger
    from .playwright_runner import PlaywrightBrowserManager
except ImportError:
    from app_logger import emit_step, get_logger
    from playwright_runner import PlaywrightBrowserManager

_log = get_logger(__name__)


class BossCrawler:
    def __init__(
        self,
        stop_event: Optional[threading.Event] = None,
        on_step: Optional[Callable[[int], None]] = None,
        **kwargs: Any, 
    ):
        """kwargs 为前端 run_script('boss', { ... }) 传来的参数，可按需使用。"""
        self.config: dict[str, Any] = kwargs
        # 前端可传 wakeMaxPages / max_times，统一落到 self.max_times
        self.max_times: int = int(
            self.config.get("wakeMaxPages")
            or self.config.get("max_times")
            or local_utils.WAKE_SCROLL_MAX_TIMES
        )
        self.stop_event: Optional[threading.Event] = stop_event
        self.on_step = on_step or emit_step
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
        login_response = self.page.request.get(
            "https://www.zhipin.com/wapi/hunter/h5/hunterManage/checkAuth"
        )
        raw = login_response.text() or ""
        try:
            login_data = login_response.json()
        except json.JSONDecodeError:
            _log.warning(
                "checkAuth 非 JSON（status=%s 前200字符）: %r",
                login_response.status,
                raw[:200],
            )
            login_data = {}
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
                    _log.info("唤醒成功: %s", person['geekCard']['name'])
                else:
                    _log.info("唤醒失败: %s", person['geekCard']['name'])
            except Exception as e:
                _log.exception("处理失败")
                continue


    def scroll_load_bottom(self):
        self.page.evaluate("window.scrollTo({top:document.documentElement.scrollHeight, behavior:'smooth'})")
        time.sleep(random.uniform(0.2, 0.5))
        self.page.locator('//p[text()="点击加载更多"]').click()


    def run(self):
        _log.info('开始执行boss直聘脚本')

        # 监听网络响应
        self.page.on("response", self.monitor_awake_response)
        _log.info('开始执行boss直聘脚本2')

        # 判断是否登陆成功，如果未登陆，则跳转登陆页面
        self.login()
        _log.info('开始执行boss直聘脚本3')

        time.sleep(5)
        _log.info('开始执行boss直聘脚本4')

        self.page.goto("https://www.zhipin.com/web/frame/search/?jobId=&keywords=&t=&source=&city=")
        self.on_step(2)  
        # 等待第二页加载出来，说明条件筛选完成
        contion_response=local_utils.wait_for_condition(self.page,lambda:self.page_params.get('page')=='2')
        if not contion_response:
            return '设置条件超过6分钟，终止脚本执行'
        self.on_step(3)  
        scroll_flag=local_utils.scroll_load_bottom(lambda:self.scroll_load_bottom(),max_times=self.max_times)
        _log.info("scroll_load_bottom: %s", scroll_flag)



    def start(self):
        try:
            self.run()
        finally:
            _log.debug("finally")
            self.page.close()
            self.browser_manager.disconnect()


if __name__ == "__main__":
    BossCrawler().start()
