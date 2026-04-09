import hashlib
import json
import os
import re
import time
import random
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

try:
    from .app_logger import get_logger
except ImportError:
    from app_logger import get_logger

_log = get_logger(__name__)

# 全局配置：唤醒脚本翻页/滚动的最大次数（所有脚本共用）
# 可通过环境变量覆盖（由前端/启动器注入），不传则默认 100
WAKE_SCROLL_MAX_TIMES = int(os.getenv("WAKE_SCROLL_MAX_TIMES", "100"))


def get_data_path(*names):
    """
    返回应用数据目录下的路径，用于浏览器 profile 等持久化数据。
    优先使用 ~/.resume-genie/data，保证在所有平台（含 Windows MSI 安装到
    Program Files 的场景）下都可写，且应用升级后数据不丢失。
    """
    _data_dir = os.path.join(os.path.expanduser("~"), ".resume-genie", "data")
    path = os.path.join(_data_dir, *names)
    return path


def get_cookie_string(context, urls=None):
    """
    从 Playwright 的 context 取出所有 cookie，返回单个字符串（可直接做 Cookie 请求头）。

    参数:
        context: browser_context（如 self.context）
        urls: 可选，不传则取全部；传列表则只取这些 URL 下的 cookie，如 ["https://mopinapi.58.com/account/currentInfo"]
    返回:
        "name1=value1; name2=value2; ..."
    """
    cookies = context.cookies(urls) if urls else context.cookies()
    return "; ".join(f'{c["name"]}={c["value"]}' for c in cookies)


def save_pdf(pdf_response, file_name, save_dir="boss_resume"):
    save_dir = get_data_path(save_dir)
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, file_name)
    with open(file_path, "wb") as f:
        f.write(pdf_response)
    return file_path

def concat_boss_resume_files(directory="boss_resume"):
    """取出这个目录下的所有文件"""
    directory = get_data_path(directory)
    file_list = [os.path.join(directory, f) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    file_string='\n'.join(file_list)
    return file_string






def date_str_to_timestamp(date_str, year=None):
    """
    将 '02月10日'、'2025年02月10日'、'15:04'、'昨天' 或 '02-06' 转成 Unix 时间戳（秒）。
    '15:04' 表示当天 15:04；'昨天' 表示昨天 0 点；'02-06' 表示月-日（用当前年）。

    参数:
        date_str: 如 '02月10日'、'2025年02月10日'、'15:04'、'昨天'、'02-06'
        year: 若 date_str 只有月日，用该年；不传则用当前年
    返回:
        int 时间戳（秒）
    """
    date_str = (date_str or "").strip()
    now = datetime.now()
    if year is None:
        year = now.year
    # 昨天：当天 0 点往前推 1 天
    if date_str == "昨天":
        yesterday = (now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1))
        return int(yesterday.timestamp())
    # 当天时分：15:04 或 9:04
    m_time = re.match(r"^(\d{1,2}):(\d{2})$", date_str)
    if m_time:
        hour, minute = int(m_time.group(1)), int(m_time.group(2))
        dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return int(dt.timestamp())
    # 带年份：2025年02月10日
    m_full = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", date_str)
    if m_full:
        y, mon, day = int(m_full.group(1)), int(m_full.group(2)), int(m_full.group(3))
    else:
        # 仅月日：02月10日 或 02-06（月-日）
        m_md = re.match(r"(\d{1,2})月(\d{1,2})日", date_str)
        if not m_md:
            m_dash = re.match(r"^(\d{1,2})-(\d{1,2})$", date_str)
            if m_dash:
                mon, day = int(m_dash.group(1)), int(m_dash.group(2))
                y = year
            else:
                raise ValueError(f"无法解析日期字符串: {date_str}")
        else:
            mon, day = int(m_md.group(1)), int(m_md.group(2))
            y = year
    dt = datetime(y, mon, day)
    return int(dt.timestamp())


def is_in_past_days(timestamp_10: int, days: int) -> bool:
    """
    判断10位时间戳是否在过去指定天数内
    :param timestamp_10: 10位整数时间戳（单位：秒）
    :param days: 要判断的天数（3/5等）
    :return: True=在过去days天内，False=不在
    """
    # 1. 把10位时间戳转成datetime对象（本地时间）
    # 注：如果要按UTC时间判断，把fromtimestamp换成utcfromtimestamp
    target_time = datetime.fromtimestamp(timestamp_10)
    
    # 2. 计算“当前时间 - days天”的时间（即时间阈值）
    now = datetime.now()
    threshold_time = now - timedelta(days=days)
    
    # 3. 核心判断：目标时间 在 阈值时间 和 当前时间 之间
    is_in_range = threshold_time <= target_time <= now
    
    return is_in_range


def get_url_params(url: str, single_value: bool = True) -> dict:
    """
    从 URL 中解析出查询参数（? 后面的部分）。

    :param url: 完整 URL 或仅 query 字符串
    :param single_value: True 时每个参数返回一个值（dict[str, str]），
                         False 时每个参数返回列表（dict[str, list]，兼容同名多值）
    :return: 参数名 -> 值 的字典
    """
    if "?" in url:
        query = urlparse(url).query
    else:
        query = url
    params = parse_qs(query)
    if single_value:
        return {k: v[0] for k, v in params.items()}
    return params



def wait_for_condition(page, check_func, timeout_ms=600000): 
    """
    :param timeout_ms: 超时时间，单位是 **毫秒**
    """
    start_time = time.time()
    timeout_sec = timeout_ms / 1000.0  # 👈 转换为秒
    
    while True:        
        if check_func():
            return True
            
        if time.time() - start_time > timeout_sec:
            _log.warning("⏰ 等待超时")
            return False
            
        page.wait_for_timeout(200) 


def scroll_load_bottom(func,timeout_ms=3600000,max_times=101):
    start_time = time.time()
    timeout_sec = timeout_ms / 1000.0  # 👈 转换为秒
    # while True:
    #     try:
    #         # 随机延时，模拟人类阅读和思考时间
    #         time.sleep(random.uniform(2, 5))
    #         func()
    #         # 操作后再随机停留
    #         time.sleep(random.uniform(1, 3))
    #     except Exception as e:
    #         return 'finish'
    #     finally:
    #         if time.time() - start_time > timeout_sec:
    #             return 'timeout'
    for page_index in range(2,max_times):
        try:
            # 随机延时，模拟人类阅读和思考时间
            time.sleep(random.uniform(2, 5))
            func()
            # 操作后再随机停留
            time.sleep(random.uniform(1, 3))
        except Exception as e:
            return 'finish'
        finally:
            if time.time() - start_time > timeout_sec:
                return 'timeout'
