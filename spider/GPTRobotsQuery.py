# -*- coding:utf-8 -*-
"""
负责爬取和提取答案 并行操作
"""

import traceback
import time
import utils.common

from config import gpt_conf

from models import MSession, SessionModel
from models import MProductsResult

from spider.GPTBase import GPTBase
from spider.logs.syslog import SysLog
from spider.product_queue.product import ProductQueue
from spider.wdriver.wdriver import WDriver as WDriverBrowser
from spider.browser_gpt import RBrowserManager as BrowserManager

class GPTQuery(GPTBase):
    def __init__(self, thread_lock, browser_port):
        super(GPTQuery, self).__init__(thread_lock, browser_port)
        # 是否正常运行。触发浏览器重启后，将该值设置为False， 成功回答后将该值设置为True
        # 如果为True，则减少相应的等待时间
        self.is_success_run = False
        self.is_prod_account = False

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
        MProductsResult.add_one(data)
        self.sysLog.log("save data success, bid:%s" % data['bid'])


    def simulator(self, product):
        # 上报running 状态。 只有远端才会上报
        self.report_running_status()

        # 初始化浏览器连接
        self.init_webbrowser()
        self.init_page_action()

        # 进入新的聊天
        self.sysLog.log("go to target home page")
        if not self.pageAction.switch_to_home_page():
            self.sysLog.log("to new_chat home Failed!")
            time.sleep(15)
            return False
        # 这1秒必须等待。避免有异步的js 生成cookie
        time.sleep(1)

        # 清理缓存
        self.WDriver.clear_local_cache()

        # 执行登录
        self.sysLog.log("auto_login ...")
        if not self.auto_login():
            self.sysLog.log("auto_login failed，continue")
            return False
        self.sysLog.log("auto_login OK")

        self.sysLog.log("login_step_welcome_got_it ...")
        self.pageAction.login_step_welcome_got_it()
        self.sysLog.log("login_step_welcome_got_it OK")
        time.sleep(2)

        # 接受协议
        if self.is_prod_account:
            accept_terms_ts = 10
        else:
            accept_terms_ts = 10
        self.sysLog.log("accept_terms_service ...")
        if  self.pageAction.check_accept_terms_service(accept_terms_ts):
            self.pageAction.accept_terms_service()
        self.sysLog.log("accept_terms_service OK")
        time.sleep(2)

        # 只需要检测，如果发现用户未登录，则发起通知，并且sleep 1h。
        if not self.pageAction.check_login_mark():
            self.sysLog.log("检测到当前浏览器可能未登录，切换浏览器")
            return False

        # 如果 check_page 过久，可以取消该10s等待
        self.sysLog.log("go to checking page")
        if not self.pageAction.check_chat_page():
            self.sysLog.log("check page failed, continue")
            return False

        # 设置 model
        self.sysLog.log("set option_select_flash_pre_0520 ...!")
        if not self.pageAction.option_select_flash_pre_0520():
            self.sysLog.log("set option_select_flash_pre_0520 failed!")
            return False
        self.sysLog.log("set option_select_flash_pre_0520 success!")
        time.sleep(2)
        # 设置 temperature
        self.sysLog.log("set option_set_temperature ...")
        if not self.pageAction.option_set_temperature():
            self.sysLog.log("set option_set_temperature failed!")
            return False
        self.sysLog.log("set option_set_temperature success!")
        time.sleep(2)
        # 设置 thinking
        self.sysLog.log("set option_set_thinking ...")
        if not self.pageAction.option_set_thinking():
            self.sysLog.log("set option_set_thinking failed!")
            return False
        self.sysLog.log("set option_set_thinking success!")
        time.sleep(2)
        # 设置 google search
        self.sysLog.log("set option_set_google_search ...")
        if not self.pageAction.option_set_google_search():
            self.sysLog.log("set option_set_google_search failed!")
            return False
        self.sysLog.log("set option_set_google_search success!")

        time.sleep(5)
        self.sysLog.log("get ask msg")
        first_msg = self.get_ask_msg(product)

        # 开始时间
        start_time = utils.common.get_second_utime()
        # 异步回答不需要支持
        ask_msg = first_msg
        time.sleep(1)
        ask_status = self.ask_js(ask_msg)

        if not ask_status:
            self.sysLog.log("ask_js failed, continue")
            return False

        # 等待相应
        time.sleep(10)
        self.sysLog.log("waiting_response ...")
        if not self.pageAction.waiting_response():
            self.sysLog.log("waiting_response failed, continue")
            return False
        self.sysLog.log("waiting_response success!")

        time.sleep(5)

        # 检测是否触发限制
        self.sysLog.log("check_limited ...")
        if self.pageAction.check_limited():
            self.sysLog.log("check_limited!!!!!, continue")
            # 检测到limited 后应该短时间内不在调用该账号
            MSession.delay_ask_ts(account=self.session_key)
            return False
        self.sysLog.log("check_limited complete,not find limited ...")

        # 获取相应结果

        response = self.pageAction.get_response()
        end_time = utils.common.get_second_utime()

        query_status = "failed"
        if not response:
            self.limit_account_error_num = 0
            data = {
                "bid": product['bid'],
                "product_name": product['product_name'],
                "ask": first_msg,
                "duration": end_time - start_time,
                "status": "failed",
                "error": "not find response",
                "current_mode_pre": self.pageAction.get_current_model(),
                "proxy_port": self.browser_proxy['port'],
                "account": self.session_key,
                "answer": "",
                "origin_refs": "",
                "answer_text": "",
            }
        else:
            query_status = "success"
            data = {
                "bid": product['bid'],
                "product_name": product['product_name'],
                "ask": ask_msg,
                "status": "success",
                "current_mode_pre": self.pageAction.get_current_model(),
                "proxy_port": self.browser_proxy['port'],
                "account": self.session_key,
                "answer": response['origin_html'],
                "origin_refs": response['refs_html'],
                "answer_text": response['text'],
            }

        self.report_success_status()
        self.save(data)
        self.sysLog.log(f"current product query complete, status:{query_status}. save and next")
        return "continue"

    def query(self):
        is_first = True
        while True:
            try:
                if not self.init_browser():
                    print(f"{self.browser_port} - 浏览器队列已经用尽！")
                    time.sleep(300)
                    continue

                product = None

                if not product:
                    product = self.productQueue.get_product()

                if not product:
                    msg_title = "产品队列用尽通知"
                    msg_content = " 产品已经用尽，请尽快补充产品 "
                    self.sysLog.log(msg_content)
                    time.sleep(600)
                    continue

                # 产品数据检测
                if "bid" not in product or "product_name" not in product:
                    self.sysLog.log("check primary filed failed, next product...")
                    continue
                self.sysLog.log("get product success, bid: %s" % product['bid'])

                self.mark = "[bid:%s]" % (product['bid'], )
                self.sysLog.set_mark(self.mark)

                # 检测是否存在，存在则跳过
                if MProductsResult.total(
                        condition={"bid": {"$eq": product['bid']}}) > 0:
                    self.sysLog.log("check product exists in gpt, continue")
                    continue
                else:
                    self.sysLog.log("check product not exists in gpt, continue,bid: %s" % product['bid'])

                self.sysLog.log("check product existence Okay, proceeding")

                # 首次运行先分配下发一可用的代理
                if is_first:
                    self.going_restart(is_match_proxy=True)
                    is_first = False

                # 如果临时见到到代理失败，则重新获取新的代理。避免所有代理出现异常程序故障，需要sleep 120s
                if not self.check_proxy_status():
                    self.sysLog.log("check proxy status Failed switch proxy and sleep 60s...")
                    self.going_restart(is_match_proxy=True)
                    time.sleep(60)
                    continue
                self.sysLog.log("check proxy status Okay, proceeding")

                # 故障重试机制： 连续失败n次后会触发一些处理事件
                self.sysLog.log(f"正在进行故障次数统计，当前故障次数：{self.get_resp_error_num}")
                if self.get_resp_error_num >= 3:
                    # 到这里有可能所有的账号都耗尽了
                    if self.get_resp_error_num >= 5:
                        print("连续失败5次，并且重新切换了代理3次。 判定当前浏览器账号故障或者代理大面积故障。 浏览器将sleep 1h后继续")
                        self.get_resp_error_num = 0
                        time.sleep(3600)
                        continue
                    self.going_restart(is_match_proxy=True)

                self.sysLog.log("start simulator...")
                try:
                    start_ts = utils.common.get_second_utime()
                    resp_status = self.simulator(product)

                    # 不管成功还是失败，都应该解锁
                    if self.session_key:
                        MSession.open_ask_lock(self.session_key)
                    if resp_status:
                        self.is_success_run = True
                        self.get_resp_error_num = 0
                        # 提取答案
                    else:
                        self.is_success_run = False
                        self.get_resp_error_num = self.get_resp_error_num + 1

                    end_ts = utils.common.get_second_utime()
                    cost_ts = int(end_ts - start_ts)
                    self.sysLog.log(f"Done Simulator, Cost {cost_ts} s.")

                    left_ts = gpt_conf.fixed_running_loop_ts - cost_ts
                    self.sysLog.log("current requests left ts %s" % left_ts)

                    if gpt_conf.is_fixed_running_time and resp_status:
                        if left_ts > 0:
                            self.sysLog.log("当前轮询结束，下一个轮询前需要休眠: %s s" % left_ts)
                            time.sleep(left_ts)
                except:
                    self.get_resp_error_num = self.get_resp_error_num + 1
                    _sleep_ts = 30
                    self.sysLog.log(f"获取数据异常， sleep {_sleep_ts}s next, {traceback.format_exc()}")
                    time.sleep(_sleep_ts)

            except:
                print(traceback.format_exc())
                self.sysLog.log(f"{self.browser_port} - 未知异常原因(while-true-Try/Exception)，程序等待10分钟再次运行。 ")
                self.sysLog.err_log(f"{self.browser_port} - 未知异常原因，程序等待10分钟再次运行。Error:%s" % traceback.format_exc())
                time.sleep(600)
