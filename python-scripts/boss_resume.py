import time
import threading
from typing import Any, Callable, Optional
import random
from patchright.sync_api import BrowserContext, Page
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


class BossCrawler:
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
        self.on_data = on_data or (lambda data: print(f"RESUME_DATA:{json.dumps(data, ensure_ascii=False)}", flush=True))
        self.browser_manager: PlaywrightBrowserManager = PlaywrightBrowserManager()
        self.context: BrowserContext = self.browser_manager.start()
        self.browser_manager.close_tabs("zhipin")
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
        raw_days = self.config.get("days") or 99
        try:
            days = int(raw_days)
            if days <= 0:
                raise ValueError
        except (TypeError, ValueError):
            print(f"参数错误: days 必须为正整数，当前值: {raw_days!r}")
            return

        mopin_login_response=self.page.request.get("https://mopinapi.58.com/account/currentInfo")
        mopin_login_data=mopin_login_response.json()
        if mopin_login_data.get('msg') != "成功":
            self.page.goto("https://mopin.58.com/login")
            self.page.locator('//span[contains(text(),"做单")]').first.wait_for(state='visible',timeout=60000)
        mopin_cookie = mopin_login_response.headers.get('set-cookie')

        login_response=self.page.request.get("https://www.zhipin.com/wapi/hunter/h5/hunterManage/checkAuth")
        login_data=login_response.json()
        if login_data.get('message') != "Success":
            self.page.goto("https://www.baidu.com/")
            time.sleep(random.uniform(1, 2))
            self.page.locator('//div[@id="chat-input-area"]/textarea').fill("boss直聘")
            self.page.locator('//div[@id="chat-input-area"]/textarea').press("Enter")
            time.sleep(random.uniform(2, 4))
            boss_url=self.page.locator('//a[@data-url="www.zhipin.com/"]').get_attribute('href')
            self.page.goto(boss_url)
            self.page.locator('//span[text()="升级VIP"]').wait_for(state='visible',timeout=60000)

        if self.stopped:
            return

        self.page.goto("https://www.zhipin.com/web/chat/index",wait_until="domcontentloaded",timeout=60000)
        self.page.locator('//span[contains(text(),"已获取简历")]').click()
        if self.sleep_with_stop(5):
            return
        next_element=self.page.locator('//div[@role="listitem" and @key]').first

        while next_element.is_visible():
            time.sleep(random.uniform(1, 5))
            if self.stopped:
                break
            current_key = next_element.get_attribute('key')
            if not current_key:
                print("当前简历项缺少 key，终止任务")
                break

            try:
                time_text=next_element.locator('span.time.time-shadow').text_content().strip()
                time_timestamp=local_utils.date_str_to_timestamp(time_text)
            except Exception as e:
                print(f"时间解析失败, 跳过该条: key={current_key}, error={e}")
                next_element = self.page.locator(
                    f'//div[@role="listitem" and @key="{current_key}"]/following-sibling::div[1]'
                )
                continue
            # 超过某个时间就终止
            if not local_utils.is_in_past_days(time_timestamp, days=days):
                break
            if self.stopped:
                break
            next_element=next_element.first
            next_element.scroll_into_view_if_needed()
            user_data=self.browser_manager.action_and_capture(self.page,lambda:next_element.click(),'geek/info')['zpData']['data']
            awaken_response=parse_request.boss_parse_request(user_data)['data']
            awaken_request_response=mopin_request.awaken_request(awaken_response)['data']
            next_uid=next_element.get_attribute('key')[:-2]
            if self.sleep_with_stop(random.uniform(3, 5)):
                break
            next_element=self.page.locator(f'//div[@role="listitem" and @key="{next_uid}-0"]/following-sibling::div[1]')
            resume_element=self.page.locator('//a[@class="btn resume-btn-file"]')
            save_path = os.path.join(local_utils.get_data_path("boss_resume"), f"{awaken_response['cleaned']['boss']['data']['baseInfo']['name']}_{next_uid}.pdf")
            if os.path.exists(save_path):
                print(f"文件已存在,跳过下载: {save_path}")
                continue
            time.sleep(random.uniform(1, 3))
            if resume_element.is_visible():
                resume_element.click()
                click_download = lambda: self.page.locator('//div[contains(text(),"下载")]/../..').click()
                binary_data = self.browser_manager.action_and_download_binary(
                    self.page, click_download, save_path
                )

                basic_info=parse_request.pdf_parse_request_basic(binary_data)
                if not basic_info['data']['mobile']:
                    print(f"手机号不存在,跳过下载: {save_path}")
                    self.page.locator('//div[@class="boss-popup__close"]').click()
                    continue
                clearn_pdf_data=parse_request.pdf_parse_request(binary_data)
                awaken_response['cookie']=mopin_cookie
                # awaken_response['clean_pdf_data']=clearn_pdf_data 
                awaken_response['cleaned']['boss']['data']['baseInfo']['name']=clearn_pdf_data['data']['baseInfo']['name'] or ''
                awaken_response['cleaned']['boss']['data']['baseInfo']['nickName']=clearn_pdf_data['data']['baseInfo']['name'] or ''
                awaken_response['cleaned']['boss']['data']['baseInfo']['emailBlur']=clearn_pdf_data['data']['baseInfo']['email'] or ''
                awaken_response['cleaned']['boss']['data']['baseInfo']['account']=clearn_pdf_data['data']['baseInfo']['phone'] or ''
                awaken_response['cleaned']['boss']['data']['expectList']=clearn_pdf_data['data']['expectList'] or []
                awaken_response['cleaned']['boss']['data']['workExpList']=clearn_pdf_data['data']['workExpList'] or []
                awaken_response['cleaned']['boss']['data']['projectExpList']=clearn_pdf_data['data']['projectExpList'] or []
                iphone=awaken_response['cleaned']['boss']['data']['baseInfo']['account']
                name=awaken_response['cleaned']['boss']['data']['baseInfo']['name']
                push_response=mopin_request.push_request(awaken_response)
                if json.loads(push_response['data']['createOrUpdateResume']).get('msg') == '成功':
                    print(f"简历推送保存成功: {name}-{iphone}")
                    self.on_data({'name': name or '', 'phone': iphone or ''})
                else:
                    print(f"简历推送保存失败: {name}")
                self.page.locator('//div[@class="boss-popup__close"]').click()

        if self.stopped:
            print("收到停止信号，结束 Boss 解析任务")

           
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
    BossCrawler(days=args.days).start()
