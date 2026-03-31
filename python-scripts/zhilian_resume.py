import time
import threading
from typing import Any, Callable, Optional
import random
from urllib import request
from patchright.sync_api import BrowserContext, Page
import os, json
import base64
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
        self.on_data = on_data or (lambda data: print(f"RESUME_DATA:{json.dumps(data, ensure_ascii=False)}", flush=True))
        self.browser_manager: PlaywrightBrowserManager = PlaywrightBrowserManager()
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
    
    def login(self):
        login_response=self.page.request.get("https://rd6.zhaopin.com/api/im/user")
        login_data=login_response.json()
        if login_data.get('code') != 200:
            self.page.goto("https://passport.zhaopin.com/org/login")
            self.page.locator('//span[text()="服务中心"]').wait_for(state='visible',timeout=60000)
    
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
        time.sleep(random.uniform(1, 3))
        mopin_login_response=self.page.request.get("https://mopinapi.58.com/account/currentInfo")
        mopin_login_data=mopin_login_response.json()
        if mopin_login_data.get('msg') != "成功":
            self.page.goto("https://mopin.58.com/login")
            self.page.locator('//span[contains(text(),"做单")]').first.wait_for(state='visible',timeout=60000)
        mopin_cookie = mopin_login_response.headers.get('set-cookie')


        time.sleep(random.uniform(1, 2))
        self.login()
        if self.stopped:
            return
        # 打开网址
        self.page.goto("https://rd6.zhaopin.com/app/im")
        # 点击有简历
        click_func=lambda:self.page.locator('//div[contains(text(),"已获取电话")]').click()
        first_response=self.browser_manager.action_and_capture(self.page, click_func, 'https://rd6.zhaopin.com/api/im/session/list')
        person_list=first_response['data']
        while person_list:
            for person in person_list:
                name=person['name']
                uid=person['userId']
                job_title=person['jobTitle']
                time_step=json.loads(person['lastSentence'])['sendTime']//1000
                if not local_utils.is_in_past_days(time_step, days=days):
                    return
                save_path=os.path.join(local_utils.get_data_path("zhilian_resume"), f"{name}_{uid}_{job_title}.pdf")
                os.makedirs(local_utils.get_data_path("zhilian_resume"), exist_ok=True)
                if os.path.exists(save_path):
                    print(f"文件已存在,跳过下载: {save_path}")
                    continue
                img=person['avatar'].split('avatar')[-1]
                xpath=f'//img[contains(@src,"{img}")]/../../../..//span[@title="{name}"]'
                click_func=lambda:self.page.locator(xpath).click()
                click_response=self.browser_manager.action_and_capture(self.page, click_func, 'https://rd6.zhaopin.com/api/im/session/detail')
                awaken_parse_response=parse_request.zhilian_parse_request(click_response['data'])['data']
                awaken_request_response=mopin_request.awaken_request(awaken_parse_response)['data']
                wake_resume_dict = json.loads(awaken_request_response['wakeResume'])
                if wake_resume_dict['msg']=='成功':
                    print(f"唤醒成功: {name}_{uid}_{job_title}")
                else:
                    print(f"唤醒失败: {name}_{uid}_{job_title}")
                
                try:
                    self.page.locator('//span[text()="查看附件简历"]').wait_for(state='visible',timeout=10000)
                except Exception as e:
                    print(f"处理失败: {e}")
                    continue
                click_download = lambda:self.page.locator('//span[text()="查看附件简历"]').click()
                download_response=self.browser_manager.action_and_capture(self.page, click_download, 'api/resume/getAttachResumeInfo')
                download_url=download_response['data']['url']
                response=self.context.request.get(download_url)
                with open(save_path, 'wb') as f:
                    f.write(response.body())
                print(f"下载成功: {name}_{uid}_{job_title}")
                pdf_parse_data = parse_request.pdf_parse_request(response.body())
                parse_data = awaken_parse_response  # 先用唤醒后的数据作为推送基准
                # 补充pdf解析后的信息
                parse_data['cookie'] = mopin_cookie
                parse_data['clean_pdf_data'] = pdf_parse_data
                # 补充基础信息（如有为空的字段，进行覆盖）
                parse_data['cleaned']['zhilian']['data']['baseInfo']['name'] = pdf_parse_data['data']['baseInfo']['name'] or ''
                parse_data['cleaned']['zhilian']['data']['baseInfo']['nickName'] = pdf_parse_data['data']['baseInfo']['name'] or ''
                parse_data['cleaned']['zhilian']['data']['baseInfo']['emailBlur'] = pdf_parse_data['data']['baseInfo']['email'] or ''
                parse_data['cleaned']['zhilian']['data']['baseInfo']['account'] = pdf_parse_data['data']['baseInfo']['phone'] or ''
                parse_data['cleaned']['zhilian']['data']['expectList'] = pdf_parse_data['data'].get('expectList') or []
                parse_data['cleaned']['zhilian']['data']['workExpList'] = pdf_parse_data['data'].get('workExpList') or []
                parse_data['cleaned']['zhilian']['data']['projectExpList'] = pdf_parse_data['data'].get('projectExpList') or []
                iphone = parse_data['cleaned']['zhilian']['data']['baseInfo']['account']
                name = parse_data['cleaned']['zhilian']['data']['baseInfo']['name']
                push_response = mopin_request.push_request(parse_data)
                if json.loads(push_response['data']['createOrUpdateResume']).get('msg') == '成功':
                    print(f"简历推送保存成功: {name}")
                    self.on_data({'name': name or '', 'phone': iphone or ''})
                else:
                    print(f"简历推送保存失败: {name}")
                print(pdf_parse_data)

                self.browser_manager.close_tabs("attachment.zhaopin.com/resumeapi/parsev2/downloadFileTemporary?file")
                time.sleep(random.uniform(1, 2))
            scroll_response=self.browser_manager.action_and_capture(self.page, lambda:self.page.evaluate("""
                const container = document.querySelector('.im-session-list__virtual');
                container.scrollTop = container.scrollHeight;
            """), 'https://rd6.zhaopin.com/api/im/session/list')
            person_list=scroll_response['data']






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
