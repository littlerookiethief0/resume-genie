import requests
import time
import random

_session = requests.Session()
boss_parse_url="https://jobdig.100dp.com/api/resume/convert/convertBoss"
zhilian_parse_url="https://jobdig.100dp.com/api/resume/convert/convertZhilian"
liepin_parse_url="https://jobdig.100dp.com/api/resume/convert/convertLiepin"

def boss_parse_request(data):
    time.sleep(random.uniform(0.1, 0.4))
    response=_session.post(boss_parse_url,json=data)
    return response.json()

def zhilian_parse_request(data):
    time.sleep(random.uniform(0.1, 0.4))
    response=_session.post(zhilian_parse_url,json=data)
    return response.json()

def liepin_parse_request(data):
    time.sleep(random.uniform(0.1, 0.4))
    response=_session.post(liepin_parse_url,json=data)
    return response.json()


def pdf_parse_request(pdf_data: bytes) -> dict:
    """
    调用远程 PDF 解析接口，将 PDF 文件内容发送为 multipart/form-data 并返回解析结果。
    :param pdf_data: PDF 文件二进制内容
    :return: 解析后的 JSON 数据
    """

    url = "https://jobdig.100dp.com/api/resume/convert/pdf-parse"
    files = {
        "file": ("resume.pdf", pdf_data, "application/pdf")
    }
    for i in range(3):
        try:
            response = requests.post(url, files=files)
            if response.json()['data']['name'] or response.json()['data']['mobile']:
                return response.json()
        except Exception as e:
            continue
    return response.json()



def pdf_parse_request_basic(pdf_data: bytes) -> dict:
    url = "https://jobdig.100dp.com/api/resume/convert/pdf-parse-basic"
    files = {
        "file": ("resume.pdf", pdf_data, "application/pdf")
    }
    response = requests.post(url, files=files)
    return response.json()

