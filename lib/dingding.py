import requests
import json,time

DINGDING_INFO_API="https://oapi.dingtalk.com/robot/send?access_token=xxxxx"
API = "https://oapi.dingtalk.com/robot/send?access_token=xxxx"
REMINDERS = []

def send_alert_msg(title, content,REMINDERS,API,trun_on=True):
    content=content.replace("<br>","")
    headers = {
        "Content-Type": "application/json;charset=utf-8"
    }
    data = {
        "msgtype": "text",
        # "markdown": {
        #     "title": title,
        #     "text": title+"\n<br>"+content
        # },
        "text": {
            "content": title+"\n"+content
        },
        "at": {
            "atMobiles": REMINDERS,
            "isAtAll": False
        }
    }
    r = requests.post(API, data=json.dumps(data), headers=headers)
    if r.status_code != 200:
        print("dingding msg send failed, status code: %d", r.status_code)
        return
    rsp_data = r.json()
    if rsp_data["errcode"] == 0:
        print("dingding msg send successful.")
        time.sleep(3.5)
    else:
        print("dingding msg send failed, %s", rsp_data["errmsg"])



if __name__ == '__main__':
    send_alert_msg("test", "告警")
