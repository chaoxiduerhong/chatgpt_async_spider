# -*- coding:utf-8 -*-
"""
提问 * 详情提问

"""
from utils import error_retry
import traceback
import time
import random
import utils.common

from config import gpt_conf

from models import MSession, SessionModel, MProducts

from models import MProducts, MProductsResult

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

    @staticmethod
    def get_ask_msg_with_alternatives(product):
        std_content_obj = product['std_content_obj'][gpt_conf.outline_ask_processing]
        std_content_info = std_content_obj['full_content'].strip()
        template_info = std_content_info.split(' ', 1)[1] if ' ' in std_content_info else std_content_info
        ask_msg = gpt_conf.ask_template

        # May 21 2025, 替换少量词组
        replacement_word_generate = [
            'Generate', "Create", "Produce", "Develop", "Formulate", "Prepare", "Compile", "Draft", "Provide", "Design",
        ]
        ask_msg = ask_msg.replace("GENERATE", random.choice(replacement_word_generate))
        # 替换结束

        ask_msg = ask_msg.replace("{keywords}", product['product_name'])
        ask_msg = ask_msg.replace("{template}", template_info)
        print(ask_msg, "====ask_msg INFO====")
        return ask_msg

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
            self.get_resp_error_num = self.get_resp_error_num + 1
            return False

        # https://chatgpt.com/?model=auto
        # 自动化人工校验
        # if not self.pageAction.auto_robots():
        #     self.sysLog.log("auto_robots failed, continue")
        #     return False

        # 登录
        if not self.auto_login():
            self.sysLog.log("auto_login failed，continue")
            return False
        self.sysLog.log("auto_login OK")

        # 检测 现在开始吧按钮，并且点击
        self.pageAction.auto_start_chat()

        # 自动化人工校验
        # if not self.pageAction.auto_robots():
        #     self.sysLog.log("auto_robots failed, continue")
        #     return False

        # 检测页面
        # 如果 check_page 过久，可以取消该10s等待
        self.sysLog.log("go to checking page")
        if not self.pageAction.check_chat_page():
            self.sysLog.log("check page failed, restart and continue")
            self.get_resp_error_num = self.get_resp_error_num + 1
            self.going_restart(clear_cache=False, is_match_proxy=True)
            return False

        # 设置 gpt 状态
        self.sysLog.log("set GPT5 Model")
        set_model_name = "think"
        current_mode_pre = self.pageAction.get_current_model()
        if current_mode_pre != set_model_name:
            if not self.pageAction.option_select_model(set_model_name):
                self.get_resp_error_num = self.get_resp_error_num + 1
                self.sysLog.log("option_select_gpt5 failed, continue")
                return False
        # 提问
        ask_msg = self.get_ask_msg_with_alternatives(product)
        start_time = utils.common.get_second_utime()
        ask_status = self.ask_js(ask_msg)
        if not ask_status:
            self.get_resp_error_num = self.get_resp_error_num + 1
            self.sysLog.log("ask_js failed, continue")
            day_count_info = MSession.lock_ask_failed_update_day_count(self.session_key)
            print("------》 处理之前day_count_info信息为", day_count_info)
            return False
        end_time = utils.common.get_second_utime()

        # 避免中间弹出了人工校验
        self.pageAction.auto_robots()
        time.sleep(5)

        # 保存提问结果
        request_full_url, url_session_uuid = self.get_url_uuid()
        if request_full_url and url_session_uuid:
            self.get_resp_error_num = 0
            self.limit_account_error_num = 0
            data = {
                "bid": product['bid'],
                "request_full_url": request_full_url,
                "request_url_uuid": url_session_uuid,
                "product_name": product['product_name'],
                "account": self.session_key,
                "processing": "ask_success",
                "ask": ask_msg,
                "proxy_port": self.browser_proxy['port'],
                "current_mode_pre": current_mode_pre,
                "status": "success",
                "duration": end_time - start_time,
            }
        else:
            data = {
                "bid": product['bid'],
                "request_full_url": "",
                "request_url_uuid": "",
                "product_name": product['product_name'],
                "account": self.session_key,
                "processing": "ask_failed",
                "ask": ask_msg,
                "proxy_port": self.browser_proxy['port'],
                "current_mode_pre": current_mode_pre,
                "status": "invalid",
                "duration": end_time - start_time,
            }

        self.save(data)
        self.report_success_status()
        MSession.open_ask_lock(self.session_key)
        return "continue"


    def separation_outline_item(self, content:str, title:str):
        """
        分割大纲子项
        直接返回模板可用的格式
        """
        max_line_num = 7
        content = content.strip()
        lines = content.split("\n")
        content_items = [lines[i:i + max_line_num] for i in range(0, len(lines), max_line_num)]
        result = []
        for idx, group in enumerate(content_items, start=1):
            item = '\n'.join(group)
            result.append("%s\n%s" % (title, item))
        return result

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
                    product = self.productQueue.get_product()

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

                # 检测 std_content_obj  对应的内容是否存在
                if "std_content_obj" not in product or not product["std_content_obj"] or gpt_conf.outline_ask_processing+1 > len(product["std_content_obj"]):
                    self.sysLog.log("not find std_content_obj or std_content_obj is ...")
                    continue

                # 长度太长，可能有问题
                if len(product["std_content_obj"]) <= 1 or len(product["std_content_obj"]) >=40:
                    self.sysLog.log("std_content_obj 结果不合法...")
                    continue

                self.sysLog.log("get product success, bid: %s" % product['bid'])

                self.mark = "[bid:%s, outline:%s]" % (product['bid'], gpt_conf.outline_ask_processing)
                self.sysLog.set_mark(self.mark)


                # 检测数据是否已经存在
                exists = MProductsResult.first(condition={
                    "bid": product['bid']
                })

                if exists:
                    self.sysLog.log("product.idx exists in table-result, continue")
                    continue

                self.sysLog.log("check product existence Okay, proceeding")

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
                if self.get_resp_error_num >= 3:
                    if self.get_resp_error_num == 3:
                        print("连续失败5次，重启并且匹配代理")
                        self.going_restart(clear_cache=True, is_match_proxy=True)
                    else:
                        print("连续大于5次，每次重启")
                        self.going_restart(clear_cache=True, is_match_proxy=True)

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
                self.sysLog.log(f"{self.browser_port} - 未知异常原因(while-true-Try/Exception)，程序等待10分钟再次运行。 ")
                self.sysLog.err_log(f"{self.browser_port} - 未知异常原因，程序等待10分钟再次运行。Error:%s" % traceback.format_exc())
                self.waiting(600)
