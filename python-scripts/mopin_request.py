import requests
import time
import random
_session = requests.Session()
awaken_url="https://jobdig.100dp.com/api/resume/awaken"
push_url="https://jobdig.100dp.com/api/resume/push"
def awaken_request(data):
    time.sleep(random.uniform(0.1, 0.2))
    response=_session.post(awaken_url,json=data)
    return response.json()

def push_request(data):
    response=_session.post(push_url,json=data)
    return response.json()


# import requests

# url='https://jobdig.100dp.com/api/version/check?currentVersion=1.0.0'
# response = requests.get(url)
# result = response.json()
# print(result)
# (python-scripts) /Users/lizhuang/person_project/resume-genie % /Users/lizhuang/person_project/resume-ge
# nie/python-scripts/.venv/bin/python /Users/lizhuang/person_project/resume-genie/python-scripts/demo.py
# {'code': 200, 'data': {'hasUpdate': True, 'ossUrl': 'https://pan.baidu.com/s/5iJ2jyUmnfhmpO0gn3boRrA', 'latestVersion': '1.0.9'}}

