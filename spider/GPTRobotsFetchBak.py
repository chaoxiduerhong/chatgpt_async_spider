# -*- coding:utf-8 -*-
"""
答案提取
"""

import json
import traceback
import time

import utils.common

from config import gpt_conf

from models import MSession
from models import MProductsResult

from spider.actions.page_action import PageAction
from spider.GPTBase import GPTBase

class GPTFetch(GPTBase):
    def __init__(self, thread_lock, browser_port=None):
        super(GPTFetch, self).__init__(thread_lock, browser_port)
        self.is_init = None

    def save(self, data, bid=None):
        """
        table:product_gpt_des
        """
        data['url'] = gpt_conf.url
        data['browser_port'] = self.browser_port
        data['hostname'] = utils.common.get_sys_uname()
        MProductsResult.update_one(condition={"bid":bid}, data=data)
        self.sysLog.log("save data success, bid:%s" % bid)

    def get_product(self, test_bid=None):
        """
        从失败的临时表中获取数据
        因为没有bid的分配逻辑，获取到的数据需要修改状态。 processing = answer_waiting
        """
        product = MProductsResult.getFirstProductByAsync(bid=test_bid)
        if product:
            print(f"get product for product_queue, start bid {product['bid']} / {gpt_conf.client_max_bid}...")
        else:
            print(f"not find product queue")
        return product

    def save_invalid_product(self, bid):
        """
        设置产品为无效的产品
        """
        data = {
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
                for chat in chat_list:
                    if "role" in chat and chat['role'] == "ASSISTANT":
                        return chat
            except:
                return None

            return None


        answer_content = None
        refs = []
        error = None
        current_mode = ["default"]
        url = "https://copilot.microsoft.com/c/api/conversations/%s/history" % request_url_uuid
        self.sysLog.log(f"Fetch:get-result():url={url}")
        script = '''
            const callback = arguments[arguments.length - 1];
            fetch("%s", {
                method: "GET",
                headers: {
                    "accept": "application/json",
                    "accept-language": "zh-CN,zh;q=0.9",
                    'Authorization': 'Bearer %s',
                  },
                credentials: "include"
            })
            .then(response => response.json())
            .then(data => callback(data))
            .catch(error => callback({error: error.toString()}));
            ''' % (url, self.session_token)
        # 设置最大请求超时时间
        self.driver.set_script_timeout(10)
        result = self.driver.execute_async_script(script)
        self.sysLog.log(f"Fetch:get-result():result={result}")
        time.sleep(11)
        if "data" not in result:
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
        if "search_enabled" in message and message["search_enabled"]:
            current_mode.append("search_enabled")
        if "thinking_enabled" in message and message["thinking_enabled"]:
            current_mode.append("thinking_enabled")

        if "search_results" in message:
            idx = 0
            for block in message["search_results"]:
                idx = idx + 1
                refs.append({
                    'number': idx,
                    'href': block['url'] if 'url' in block else None,
                    'text': block['title'] if 'title' in block else None,
                })
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
            'current_mode': current_mode
        }

    def simulator(self, product):
        # 上报running 状态。 只有远端才会上报
        self.report_running_status()

        self.sysLog.log("----->current page info START")
        self.sysLog.log("----->current page info account:%s" % product['account'])
        self.sysLog.log(f"----->current page info email:{product.get('email', '')}")
        self.sysLog.log("----->current page info URL: %s" % product['request_full_url'])
        self.sysLog.log("----->current page info BID: %s" % product['bid'])
        self.sysLog.log("----->current page info END")

        self.pageAction = PageAction(self.lock, self.browser_port, mark=self.mark, driver=self.driver, WDBrowser=self.WDriver)

        if not self.driver.current_url or "perplexity" not in self.driver.current_url:
            self.is_init = True

        # 进入新的聊天
        self.sysLog.log("go to target page")
        if self.is_init and not self.pageAction.switch_to_chat_page():
            self.going_restart(clear_cache=True, is_match_proxy=True)
            self.sysLog.log("to new_chat Failed!")
            time.sleep(20)
            return False

        # TODO 封装 和block的一起搞
        if not self.auto_login(product['account']):
            self.sysLog.log("check user login failed，continue")
            return False

        # TODO 检测到人工校验，直接重启+跳过 当前没有更好的方案来处理人工校验
        if self.pageAction.check_robots():
            self.going_restart(clear_cache=True, is_match_proxy=True)
            self.sysLog.log("auto_robots failed, continue")
            return False

        # 如果check_page 过久，可以取消该10s等待
        self.sysLog.log("go to checking page")
        if not self.pageAction.check_chat_page():
            # TODO 这时候如果检测失败，则说明没有提问成功。没有提问成功，则day_count -1
            day_count_info = MSession.lock_ask_failed_update_day_count(self.session_key)
            print("------》 处理之前day_count_info信息为", day_count_info)
            self.sysLog.log("check page failed, continue")
            return False

        self.sysLog.log("get ask msg")

        start_time = utils.common.get_second_utime()
        response = self.get_result(product['request_url_uuid'])
        end_time = utils.common.get_second_utime()
        duration_async = end_time - start_time

        if response["status"]:
            self.is_init = False
            answer = response['answer']
            current_mode = response['current_mode']
            refs = response['refs']

            self.get_resp_error_num = 0
            self.limit_account_error_num = 0
            data = {
                "answer": "",
                'answer_markdown': answer,
                "duration_async": duration_async,
                "text_length": len(answer),
                "processing": "answer_success",
                "status": "success",
                "current_mode": current_mode,
                'spider_type': 'js_fetch',
                'refs': refs
            }
            self.save(data, product['bid'])
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
                'spider_type': 'js_fetch'
            }
            self.save(data, product['bid'])
            self.sysLog.log("---->!!! 获取数据失败，并且已经成功存储到数据表")
        return "continue"


    def query(self):
        # 初始化浏览器信息
        self.sysLog.log("init browser info success. browser_port: %s" % self.browser_port)

        # 首次默认重启浏览器，并且下发代理，清缓存
        is_first = True
        start_while_true_loop = utils.common.get_second_utime()
        while True:
            try:
                self.sysLog.log("Query While-True-Loop START ...")
                start_while_true_loop = utils.common.get_second_utime()
                # opt - get & check bid before init-browser. Nov 08 2024
                product = None

                if not product:
                    product = self.get_product()

                if not product:
                    msg_title = "产品队列用尽通知"
                    msg_content = " 产品已经用尽，请尽快补充产品 "
                    self.sysLog.log(msg_content)

                    ret = MProductsResult.update_many(condition={
                        "processing": "answer_waiting"
                    }, data={
                        "processing": "ask_success"
                    })
                    if ret:
                        print("answer_waiting -> ask_success success!")
                    else:
                        print("answer_waiting -> ask_success failed!")

                    time.sleep(300)
                    continue

                if "account" not in product or "request_full_url" not in product:
                    self.sysLog.log("check primary filed account/request_full_url failed, next product...")
                    self.save_invalid_product(product['bid'])
                    continue

                self.mark = "[bid:%s]" % product['bid']
                self.sysLog.set_mark(self.mark)
                self.sysLog.log("QUERY async-fetch - check product complete")

                # 首次运行先分配下发一可用的代理
                if is_first:
                    self.going_restart(clear_cache=False, is_match_proxy=True)
                    is_first = False

                # 如果临时见到到代理失败，则重新获取新的代理。避免所有代理出现异常程序故障，需要sleep 120s
                if not self.check_proxy_status():
                    self.sysLog.log("check proxy status Failed switch proxy and sleep 60s...")
                    self.going_restart(clear_cache=True, is_match_proxy=True)
                    time.sleep(60)
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
                        time.sleep(600)
                    if self.get_resp_error_num > 15:
                        print("连续大于15次，重置状态。sleep 1h")
                        # 重置请求，并且直接sleep 1h
                        self.get_resp_error_num = 0
                        self.going_restart(clear_cache=True, is_match_proxy=True)
                        time.sleep(3600)
                self.sysLog.log(f"check get_resp_error_num={self.get_resp_error_num} Okay, proceeding")

                # 失败重试次数
                err_retry = 0
                while True:
                    err_retry = err_retry + 1
                    self.sysLog.log("start simulator...")
                    try:
                        # TODO 上一个和下一个时间间隔最大 172个。因为可能存在失败或者等待的情况，设置为150
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
                                time.sleep(left_ts)

                        if resp_status == "product_invalid":
                            data = {
                                "answer": "",
                                "duration_async": 0,
                                "text_length": 0,
                                "status": "product_invalid",
                                "req_num": 0,
                                "processing": "answer_failed",
                            }
                            self.save(data, product['bid'])

                        break
                    except:
                        _sleep_ts = 30
                        self.sysLog.err_log("获取数据异常, 原因：%s" % (traceback.format_exc()))
                        self.sysLog.log(f"获取数据异常，重新尝试{err_retry}/5。 sleep {_sleep_ts}s")
                        time.sleep(_sleep_ts)

                        if err_retry >= 4:
                            self.sysLog.log(
                                f"产品获取数据异常 {err_retry}/4，即将执行清缓存，重启 browser，重新匹配代理后继续尝试")
                            # 重启浏览器操作
                            self.going_restart(clear_cache=False, is_match_proxy=True)

                        if err_retry >= 6:
                            self.sysLog.log("产品获取数据失败，切换下一个产品继续")
                            break
            except:
                print(traceback.format_exc())
                self.sysLog.log("未知异常原因(while-true-Try/Exception)，程序等待10分钟再次运行。")
                self.sysLog.err_log("未知异常原因，程序等待10分钟再次运行。Error:%s" % traceback.format_exc())
                time.sleep(600)
            finally:
                end_while_true_loop = utils.common.get_second_utime()
                self.sysLog.log(f"Query While-True-Loop END, whole process cost {end_while_true_loop - start_while_true_loop} seconds.")
                pass
