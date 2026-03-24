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

