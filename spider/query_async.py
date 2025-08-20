# -*- coding:utf-8 -*-
# Desc: 模拟在线gpt，切勿用于商业用途

from threading import Thread
from threading import Lock
import time

from models import MProductsResult
from spider.GPTRobotsFetch import GPTFetch as GPTRobots
from config import browser_conf

thread_lock = Lock()

def async_call(fn):
    def wrapper(*args, **kwargs):
        Thread(target=fn, args=args, kwargs=kwargs).start()
    return wrapper


@async_call
def go_running(browser_port):
    # 检测是否带了
    rob = GPTRobots(thread_lock=thread_lock, browser_port=browser_port)
    rob.query()

def get_active_browser():
    """
    query 脚本修改为 9600 - 9700
    后面异步获取数据的时候：9700+
    """
    result = []
    list_data = browser_conf.browser_user
    for row in list_data:
        if int(list_data[row]['port']) >= 9700 and list_data[row]['status'] == "actived":
            result.append(list_data[row])
    return result


# Jun 04 2024 - 启动线程时, thread 不再固定绑定一个 port
def run(mode):
    # 这里只是通过 browser 数量确定 thread 数量
    browser_list = get_active_browser()
    browser_count = len(browser_list)

    # 将原来等待的状态修改为 ask_success。 重新跑
    ret = MProductsResult.update_many(condition={
        "processing": "answer_waiting"
    }, data={
        "processing": "ask_success"
    })
    if ret:
        print("answer_waiting -> ask_success success!")
    else:
        print("answer_waiting -> ask_success failed!")

    time.sleep(10)

    print(f"query.py -> run() - {browser_count} will be running.")
    if browser_count > 0:
        idx = 0
        for browser in browser_list:
            idx += 1
            browser_port = int(browser['port'])
            print(f"Query start -> run, browser_port {browser_port}, processing:{idx}/{browser_count}")
            go_running(browser_port)
    else:
        print("No browser to run. No thread. ")


def start(mode):
    run(mode)