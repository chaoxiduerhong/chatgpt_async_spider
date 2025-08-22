# -*- coding:utf-8 -*-
"""
提问 * 详情提问

"""
from utils import error_retry
import traceback
import time
import random
import json
import utils.common

from config import gpt_conf

from models import MSession, SessionModel, MProducts

from models import MProducts, MProductsResult

from spider.GPTBase import GPTBase
from spider.logs.syslog import SysLog
from spider.product_queue.product import ProductQueue
from spider.wdriver.wdriver import WDriver as WDriverBrowser
from spider.browser_gpt import RBrowserManager as BrowserManager

class GPTFetch(GPTBase):
    def __init__(self, thread_lock, browser_port):
        super(GPTFetch, self).__init__(thread_lock, browser_port)
        # 是否正常运行。触发浏览器重启后，将该值设置为False， 成功回答后将该值设置为True
        # 如果为True，则减少相应的等待时间
        self.is_success_run = False
        self.is_prod_account = False
        self.test_bid=None

    def init_browser(self):
        """
        切换浏览器方案
        更登录不一样，登录是把一个队列循环完成 则用尽
        这里浏览器是循环利用的
        """
        try:
            # 初始化和端口相关的
            # 因为是基于浏览器，并且可切换的，所有的数据都得重新初始化
            # 后期修改 根据切换浏览器状态来初始化这些信息
            self.MBrowser = BrowserManager()
            self.sysLog = SysLog(thread_lock=self.lock, browser_port=self.browser_port)
            self.productQueue = ProductQueue(self.lock, self.browser_port)
            self.WDriver = WDriverBrowser(self.lock, self.browser_port, interceptor_urls=gpt_conf.interceptor_urls)
            return True
        except:
            return False

    def save(self, data, bid=None):
        """
        table:product_gpt_des
        """
        data['url'] = gpt_conf.url
        data['browser_port'] = self.browser_port
        data['hostname'] = utils.common.get_sys_uname()
        if "bid" in data:
            bid = data['bid']

        MProductsResult.update_one(condition={"bid": bid}, data=data)
        self.sysLog.log("save data success, bid:%s" % bid)

    def save_invalid_product(self, bid):
        """
        设置产品为无效的产品
        """
        data = {
            "bid":bid,
            "answer": "",
            "duration_async": 0,
            "text_length": 0,
            "status": "product_invalid",
            "req_num": 0,
            "processing": "answer_failed",
        }
        self.save(data, bid)

    def get_result(self, request_url_uuid):
        """
        通过接口检测接口是否有效
        直接在页面请求，无需再次设置cookie信息（浏览器会自带）
        # TODO
        """
        def parse_content(res):
            """
            解析内容
            """
            try:
                chat_list = res['mapping']
                for key in chat_list:
                    try:
                        author = chat_list[key]['message']['author']
                    except:
                        author = None
                    try:
                        content_type = chat_list[key]['message']['content']['content_type']
                    except:
                        content_type = None
                    try:
                        content = chat_list[key]['message']['content']['parts'][0]
                    except:
                        content = None

                    try:
                        complete_status = chat_list[key]['message']['status']
                    except:
                        complete_status = None

                    try:
                        metadata = chat_list[key]['message']['metadata']
                    except:
                        metadata = None

                    try:
                        current_model = chat_list[key]['message']['metadata']['model_slug']
                    except:
                        current_model = None

                    if author and "role" in author and author['role'] and str(author['role']).lower() == "assistant" and content_type and content_type == "text":
                        return {
                            "gpt_model": current_model,
                            "content": content,
                            "complete_status": complete_status,
                            "metadata": metadata,
                        }
            except:
                print("parse_content ERROR",traceback.format_exc())
                return None

            return None

        def get_auth_Bearer():
            """
            获取 Header  Authorization: Bearer 值
            """
            url = "https://chatgpt.com/api/auth/session"
            script = '''
                const callback = arguments[arguments.length - 1];
                fetch("%s", {
                    method: "GET",
                    headers: {
                        "accept": "*/*",
                        "accept-language": "zh-CN,zh;q=0.9"
                      },
                    credentials: "include"
                })
                .then(response => response.json())
                .then(data => callback(data))
                .catch(error => callback({error: error.toString()}));
                ''' % (url, )
            self.driver.set_script_timeout(10)
            result = self.driver.execute_async_script(script)
            return result['accessToken']

        answer_content = None
        refs = {}
        error = None
        current_mode = ["default"]
        content_complete_status = None
        url = "https://chatgpt.com/backend-api/conversation/%s" % request_url_uuid
        self.sysLog.log(f"Fetch:get-result():url={url}")
        script = '''
            const callback = arguments[arguments.length - 1];
            fetch("%s", {
                method: "GET",
                headers: {
                    "accept": "*/*",
                    "accept-language": "zh-CN,zh;q=0.9",
                    'Authorization': 'Bearer %s',
                  },
                credentials: "include"
            })
            .then(response => response.json())
            .then(data => callback(data))
            .catch(error => callback({error: error.toString()}));
            ''' % (url, get_auth_Bearer())

        self.sysLog.log(f"Fetch:get-result():script={script}")
        # 设置最大请求超时时间
        self.driver.set_script_timeout(10)
        result = self.driver.execute_async_script(script)
        self.sysLog.log(f"Fetch:get-result():result={result}")
        self.waiting(5)
        if "mapping" not in result:
            return {
                "status": False,
                "error": json.dumps(result),
                "answer": answer_content,
                'refs': refs,
                'current_mode': current_mode
            }

        message = parse_content(result)
        if not message:
            return {
                "status": False,
                "error": "not parse content",
                "answer": answer_content,
                'refs': refs,
                'current_mode': current_mode
            }

        # 获取模型
        if "gpt_model" in message and message["gpt_model"]:
            current_mode=message["gpt_model"]

        refs = message['metadata'] if "metadata" in message else {}

        content_complete_status = message['status'] if "status" in message else None

        answer_content = message['content'] if 'content' in message else None

        status = False
        if answer_content:
            status = True
        else:
            error = "parse_content_error"
        return {
            "status": status,
            "answer": answer_content,
            'refs': refs,
            'error': error,
            'current_mode': current_mode,
            "content_complete_status": content_complete_status
        }

    def get_product(self):
        """
        从失败的临时表中获取数据
        因为没有bid的分配逻辑，获取到的数据需要修改状态。 processing = answer_waiting
        """
        product = MProductsResult.getFirstProductByAsync(bid=self.test_bid)
        if product:
            print(f"get product for product_queue, start bid {product['bid']} / {gpt_conf.client_max_bid}...")
        else:
            print(f"not find product queue")
        return product

    def simulator(self, product):
        """
        子项通过 outline_items 字段获取
        """
        # 上报running 状态。 只有远端才会上报
        self.report_running_status()

        # 初始化浏览器连接
        self.init_webbrowser()
        self.init_page_action()

        # 如果 check_page 过久，可以取消该10s等待
        self.sysLog.log("go to chat page")
        if not self.pageAction.switch_to_chat_page():
            self.sysLog.log("chat page failed, continue")
            self.going_restart(clear_cache=False, is_match_proxy=True)
            self.get_resp_error_num = 0
            return False

        # 登录
        if not self.auto_login(product['account']):
            self.sysLog.log("auto_login failed，continue")
            self.get_resp_error_num = 0
            return False
        self.sysLog.log("auto_login OK")

        # 检测 现在开始吧按钮，并且点击
        self.pageAction.auto_start_chat()

        # 检测页面
        # 如果 check_page 过久，可以取消该10s等待
        self.sysLog.log("go to checking page")
        if not self.pageAction.check_chat_page():
            self.sysLog.log("check page failed, restart browser and switch proxy ... continue")
            self.going_restart(clear_cache=False, is_match_proxy=True)
            self.get_resp_error_num = 0
            return False

        start_time = utils.common.get_second_utime()
        response = self.get_result(product['request_url_uuid'])
        end_time = utils.common.get_second_utime()
        duration_async = end_time - start_time

        if response["status"]:
            self.is_init = False
            answer = response['answer']
            current_mode = response['current_mode']
            refs = response['refs']
            content_complete_status = response['content_complete_status']

            self.get_resp_error_num = 0
            self.limit_account_error_num = 0
            data = {
                "answer": "",
                'answer_markdown': answer,
                "duration_async": duration_async,
                "text_length": len(answer),
                "processing": "answer_success",
                "status": "success",
                # ChatGpt 返回的内容进度，不知道有没有用。可用于定位或者调试
                "content_complete_status": content_complete_status,
                # 这里实际获取不到当时提问选择的工具，但是能获取到当时用的那个语言模型生成的内容。可以用来标志内容的可用度
                "gpt_model": current_mode,
                'spider_type': 'js_fetch',
                'refs': refs
            }
            self.sysLog.log("---->*** 获取数据成功，并且已经成功存储到数据表")
        else:
            self.is_init = True
            data = {
                "answer": "",
                'answer_markdown': None,
                "duration_async": duration_async,
                "text_length": 0,
                "status": "invalid",
                "req_num": 0,
                "processing": "answer_failed",
                "error": response["error"],
                "content_complete_status": None,
                'spider_type': 'js_fetch'
            }
            self.sysLog.log("---->!!! 获取数据失败，并且已经成功存储到数据表")

        self.save(data, product['bid'])
        self.report_success_status()
        return "continue"

    def query(self):
        """
        结果表名称： product_ast_bench_outline_detail_{idx}
        """
        is_first = True
        while True:
            try:
                if not self.init_browser():
                    print(f"{self.browser_port} - 初始化失败！")
                    self.waiting(300)
                    continue

                product = None
                if not product:
                    product = self.get_product()

                if not product:
                    msg_title = "产品队列用尽通知"
                    msg_content = " 产品已经用尽，请尽快补充产品 "
                    self.sysLog.log(msg_content)
                    self.host_report_status(f"{gpt_conf.spider_name}-ask", "queue_empty", "产品已经用尽，请尽快补充产品")
                    self.waiting(600)
                    continue

                # 产品数据检测
                if "bid" not in product or "product_name" not in product:
                    self.sysLog.log("check primary filed failed, next product...")
                    continue

                if "account" not in product or "request_full_url" not in product:
                    self.sysLog.log("check primary filed account/request_full_url failed, next product...")
                    self.save_invalid_product(product['bid'])
                    continue

                self.sysLog.log("get product success, bid: %s" % product['bid'])

                # 设置mark
                self.mark = "[bid:%s, outline:%s]" % (product['bid'], gpt_conf.outline_ask_processing)
                self.sysLog.set_mark(self.mark)

                # 首次运行先分配下发一可用的代理
                if is_first:
                    self.going_restart(clear_cache=False, is_match_proxy=True)
                    is_first = False

                # 如果临时见到到代理失败，则重新获取新的代理。避免所有代理出现异常程序故障，需要sleep 120s
                if not self.check_proxy_status():
                    self.sysLog.log("check proxy status Failed ，120s later switch proxy...")
                    self.waiting(20)
                    self.going_restart(clear_cache=True, is_match_proxy=True)
                    continue
                self.sysLog.log("check proxy status Okay, proceeding")

                # 故障重试机制： 连续失败n次后会触发一些处理事件
                if self.get_resp_error_num >= 5:
                    if self.get_resp_error_num == 5:
                        print("连续失败5次，重启并且匹配代理")
                        self.going_restart(clear_cache=True, is_match_proxy=True)
                    else:
                        print("连续大于5次，每次重启")
                        self.going_restart(clear_cache=True)

                    if 10 <= self.get_resp_error_num <= 15:
                        print("连续大于10次，每次重启并且匹配代理")
                        # 连续超过10次，每次修改10分钟，并且切换代理
                        self.going_restart(clear_cache=True, is_match_proxy=True)
                        self.waiting(600)
                    if self.get_resp_error_num > 15:
                        print("连续大于15次，重置状态。sleep 1h")
                        # 重置请求，并且直接sleep 1h
                        self.get_resp_error_num = 0
                        self.going_restart(clear_cache=True, is_match_proxy=True)
                        self.waiting(3600)
                self.sysLog.log(f"check get_resp_error_num={self.get_resp_error_num} Okay, proceeding")

                # 失败重试次数
                err_retry = 0
                while True:
                    err_retry = err_retry + 1
                    self.sysLog.log("start simulator...")
                    try:
                        start_ts = utils.common.get_second_utime()
                        resp_status = self.simulator(product)
                        end_ts = utils.common.get_second_utime()
                        cost_ts = int(end_ts - start_ts)
                        self.sysLog.log(f"Done Simulator, Cost {cost_ts} s.")

                        left_ts = gpt_conf.fixed_running_loop_ts - cost_ts
                        self.sysLog.log("current requests left ts %s" % left_ts)

                        if gpt_conf.is_fixed_running_time and resp_status:
                            if left_ts > 0:
                                self.sysLog.log("======>fixed sleep %s..." % left_ts)
                                self.waiting(left_ts)
                        break

                    except:
                        _sleep_ts = 30
                        self.sysLog.err_log("获取数据异常, 原因：%s" % (traceback.format_exc()))
                        self.sysLog.log(f"获取数据异常，重新尝试{err_retry}/5。 sleep {_sleep_ts}s")
                        self.waiting(_sleep_ts)

                        if err_retry >= 2:
                            self.sysLog.log(
                                f"产品获取数据异常 {err_retry}/4，即将执行清缓存，重启 browser，重新匹配代理后继续尝试")
                            # 重启浏览器操作
                            self.going_restart(clear_cache=False, is_match_proxy=True)

                        if err_retry >= 3:
                            self.sysLog.log("产品获取数据失败，切换下一个产品继续")
                            break
            except:
                print(traceback.format_exc())
                self.sysLog.log(f"{self.browser_port} - 未知异常原因(while-true-Try/Exception)，程序等待10分钟再次运行。 ")
                self.sysLog.err_log(f"{self.browser_port} - 未知异常原因，程序等待10分钟再次运行。Error:%s" % traceback.format_exc())
                self.waiting(600)
