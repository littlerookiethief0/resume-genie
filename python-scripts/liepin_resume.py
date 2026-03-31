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


class LiepinResumeCrawler:
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
        # 判断liepin直聘是否登陆了
        time.sleep(random.uniform(1, 2))
        login_response=self.page.request.post("https://api-lpt.liepin.com/api/com.liepin.future.common.access")
        if not login_response.ok:
            self.page.goto("https://lpt.liepin.com/login")
            self.page.locator('//span[text()="招聘数据"]').wait_for(state='visible',timeout=60000)
        if self.stopped:
            return
        # 打开网址
        self.page.goto("https://lpt.liepin.com/chat/im")
        # 点击有简历
        self.page.locator('//div[contains(text(),"有简历")]').click()
        if self.sleep_with_stop(10):
            return
        # 获取第一个简历
        next_element=self.page.locator('//div[@class="im-ui-contact-info"]').first
        # 循环获取简历
        while next_element.is_visible():
            if self.stopped:
                break
            # 获取时间
            try:
                time_text=next_element.locator('div.im-ui-system-tip.contact-time').text_content().strip()
                time_timestamp=local_utils.date_str_to_timestamp(time_text)
            except Exception as e:
                next_element=next_element.locator('xpath=./following-sibling::div[1]')
                continue
           
            # 超过某个时间就终止
            if not local_utils.is_in_past_days(time_timestamp, days=days):
                print(f"超过某个时间就终止")
                break
            # ui点击停止
            if self.stopped:
                break
            try:
                # 点击左侧，拿到响应信息
                self.browser_manager.action_and_capture(
                    self.page, lambda: next_element.click(), 'get-resume-card'
                )
                # 点击查看简历，获取在线简历信息
                resume_detail_response = self.browser_manager.action_and_capture(
                    self.page, lambda: self.page.locator('//span[text()="查看简历"]').click(), 'get-resume-detail'
                )['data']
                # 如果没有简历，关闭后跳过
                if self.sleep_with_stop(random.uniform(3, 5)):
                    break
                if not resume_detail_response.get('attachmentResume'):
                    self.page.locator('//span[@class="antlpticon antlpticon-close"]').last.click()
                    next_element = next_element.locator('xpath=./following-sibling::div[1]')
                    continue
                # 找到下载元素，等待加载完成
                resume_element = self.page.locator('//a[text()="下载"]')
                resume_element.wait_for(state='visible', timeout=10000)
                # 调用后端清洗请求
                parse_data = parse_request.liepin_parse_request(resume_detail_response)['data']
                # 调用mopin唤醒请求
                mopin_request.awaken_request(parse_data)
                save_path = os.path.join(
                    local_utils.get_data_path("liepin_resume"),
                    f"{resume_detail_response['resumeDetailed']['baseInfo']['name']}_{resume_detail_response['extInfoDto']['usercId']}.pdf"
                )
                if os.path.exists(save_path):
                    print(f"文件已存在,跳过下载: {save_path}")
                    self.page.locator('//span[@class="antlpticon antlpticon-close"]').last.click()
                    next_element = next_element.locator('xpath=./following-sibling::div[1]')
                    continue
                if self.sleep_with_stop(random.uniform(3, 5)):
                    break

                if resume_element.is_visible():
                    click_download = lambda: resume_element.click()
                    binary_data = self.browser_manager.action_and_download_binary(
                        self.page, click_download, save_path
                    )

                    basic_info = parse_request.pdf_parse_request_basic(binary_data)
                    if not basic_info['data']['mobile']:
                        print(f"手机号不存在,跳过下载: {save_path}")
                        self.page.locator('//span[@class="antlpticon antlpticon-close"]').last.click()
                        next_element = next_element.locator('xpath=./following-sibling::div[1]')
                        continue
                    clearn_pdf_data = parse_request.pdf_parse_request(binary_data)
                    parse_data['cookie'] = mopin_cookie
                    parse_data['clean_pdf_data'] = clearn_pdf_data
                    parse_data['cleaned']['liepin']['data']['baseInfo']['name'] = clearn_pdf_data['data']['baseInfo']['name'] or ''
                    parse_data['cleaned']['liepin']['data']['baseInfo']['nickName'] = clearn_pdf_data['data']['baseInfo']['name'] or ''
                    parse_data['cleaned']['liepin']['data']['baseInfo']['emailBlur'] = clearn_pdf_data['data']['baseInfo']['email'] or ''
                    parse_data['cleaned']['liepin']['data']['baseInfo']['account'] = clearn_pdf_data['data']['baseInfo']['phone'] or ''
                    parse_data['cleaned']['liepin']['data']['expectList'] = clearn_pdf_data['data']['expectList'] or []
                    parse_data['cleaned']['liepin']['data']['workExpList'] = clearn_pdf_data['data']['workExpList'] or []
                    parse_data['cleaned']['liepin']['data']['projectExpList'] = clearn_pdf_data['data']['projectExpList'] or []
                    iphone = parse_data['cleaned']['liepin']['data']['baseInfo']['account']
                    name = parse_data['cleaned']['liepin']['data']['baseInfo']['name']
                    push_response = mopin_request.push_request(parse_data)
                    if json.loads(push_response['data']['createOrUpdateResume']).get('msg') == '成功':
                        print(f"简历推送保存成功: {name}")
                        self.on_data({'name': name or '', 'phone': iphone or ''})
                    else:
                        print(f"简历推送保存失败: {name}")
                    self.page.locator('//span[@class="antlpticon antlpticon-close"]').last.click()
                next_element = next_element.locator('xpath=./following-sibling::div[1]')
            except Exception as e:
                print(f"猎聘处理失败: {e}")
                try:
                    close_btn = self.page.locator('//span[@class="antlpticon antlpticon-close"]').last
                    if close_btn.is_visible():
                        close_btn.click()
                except Exception:
                    pass
                next_element = next_element.locator('xpath=./following-sibling::div[1]')
                continue
        if self.stopped:
            print("收到停止信号，结束猎聘解析任务")










        # while person_list_el:
        #     for person_el in person_list_el:
        #         try:
        #             uid=person_el.get_attribute('data-id').strip()[:-2]
        #             if int(uid) <2000:continue
        #             if uid in set_uid:
        #                 return
        #             set_uid.add(uid)
        #             person_el.scroll_into_view_if_needed()

        #             time = person_el.locator('//span[@class="time time-shadow"]').text_content().strip()
        #             name=person_el.locator('//span[@class="geek-name"]').get_attribute('title').strip()
        #             print(time,name)
        #             # print(person_el.get_attribute('data-id'))
        #         except Exception as e:
        #             continue
        #     person_list_el=self.page.locator('//div[@class="user-container"]//div[@role="group"]//div[@data-id]').all()

        # response = self.page.request.post(
        #     "https://www.zhipin.com/wapi/zprelation/friend/filterByLabel",
        #     form={  # 注意：同步版也用 form/json，不是 data
        #         "labelId": 4,
        #         "encJobId": "",
        #         "sort": "",
        #     }
        # )
        # resume_list_uid=response.json().get('zpData',{}).get('result',[])
        # # 找出当前目录下的所有文件
        # file_list=local_utils.concat_boss_resume_files('boss_resume')

        # for user_info in resume_list_uid:
        #     if self.stopped:
        #         break
        #     friendId=user_info.get('friendId','')
        #     encryptFriendId=user_info.get('encryptFriendId','')
        #     if encryptFriendId in file_list:
        #         print(f"文件已存在: {encryptFriendId}")
        #         continue
        #     history_url=f'https://www.zhipin.com/wapi/zpchat/boss/historyMsg?src=0&gid={friendId}&maxMsgId=0&c=20&page=1'
        #     response = self.page.request.get(history_url)
        #     pdf_check_url=f'https://www.zhipin.com/wapi/zpgeek/resume/boss/preview/check.json?geekId={encryptFriendId}'
        #     pdf_check_response = self.page.request.get(pdf_check_url)
        #     zpData=pdf_check_response.json().get('zpData',{})
        #     date_flag=self.is_expire_date_valid(zpData.get('expireDate',''))
        #     if date_flag:
        #         try:
        #             pdf_url=f"https://www.zhipin.com/wflow/zpgeek/download/preview4boss/{zpData['geekId']}?d={zpData['d']}&previewType=1"
        #             pdf_response = self.page.request.get(pdf_url)
        #             pdf_response=pdf_response.body()
        #             pdf_parse_response=parse_request.pdf_parse_request(pdf_response)
        #             base_info=pdf_parse_response['data']['baseInfo']
        #             phone=base_info.get('phone','-----')
        #             name=base_info.get('name','未知')
        #             filename = f"{name}_{phone}_{zpData['geekId']}.pdf"
        #             file_path=local_utils.save_pdf(pdf_response, filename,save_dir="boss_resume")
        #             print(f"保存成功: {filename}")
        #             del pdf_response
        #             del pdf_parse_response
        #             del base_info
        #             self.on_data({'name': name, 'phone': phone})
        #         except Exception as e:
        #             print(f"处理失败: {e}")
        #             continue
           
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
    LiepinResumeCrawler(days=args.days).start()
