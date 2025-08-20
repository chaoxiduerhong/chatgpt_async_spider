# -*- coding:utf-8 -*-
"""
自动化登录
两种登录方案：
1. 将已经登录过浏览器的，并且该账号不在auth数据库中，则提取出来存储到数据库中
该方案需要注意：一定要注意不要把个人常用账号错误添加到立列表。避免被封号
该方案需要env中配置一个常规的变量来控制。再需要的电脑上才会触发0

2. 走正常登录流程

相比 copilot 这里需要将auth数据提取出来

"""

import json
import traceback
import time
import queue
import utils.common
from config import gpt_conf
from models import MSession, SessionQueueModel, MProxyQueue
from models import MSessionQueue

from spider.logs.syslog import SysLog
from spider.product_queue.product import ProductQueue
from spider.wdriver.wdriver import WDriver as WDriverBrowser
from spider.browser_gpt import RBrowserManager as BrowserManager

from spider.GPTBase import GPTBase

class GPTLogin(GPTBase):
    def __init__(self, thread_lock, browser_port):
        super(GPTLogin, self).__init__(thread_lock, browser_port)
        self.is_init = None
        self.is_login_proxy_issue=True
        self.clear_user_data = False
        # 强制重新排序浏览器
        self.is_reorder=True

    def init_browser(self):
        """
        获取并且初始化一个浏览器
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

    def get_product(self):
        """
        从失败的临时表中获取数据 获取原则：没有hostname + 没有port的
        """
        product = MSessionQueue.get_unsync_data()
        return product


    def simulator(self, product):
        # 上报running 状态。 只有远端才会上报
        self.report_running_status()

        # 初始化浏览器连接
        self.init_webbrowser()
        self.init_page_action()

        self.sysLog.log("----->current page info START")
        self.sysLog.log(f"----->current page info email:{product.get('email', '')}")
        self.sysLog.log("----->current page info END")

        self.sysLog.log("switch_to_login_page...")
        if not self.pageAction.switch_to_login_page():
            self.going_restart(is_match_proxy=True)
            self.sysLog.log("switch_to_login_page Failed!")
            time.sleep(20)
            return False
        self.sysLog.log("switch_to_login_page complete！")

        # TODO 这里要进行以下人工校验
        self.pageAction.auto_robots()

        # 进入注册页面 如果当前url是 https://accounts.google.com/ 则认为是登录失败。这时候已经直接进入了登录流程。
        if self.driver.current_url.startswith('https://accounts.google.com'):
           self.sysLog.log("check google login complete, about skip target site")

        elif self.driver.current_url.startswith('https://chatgpt.com'):
            print("TODO 浏览器已经登录了----------")
            time.sleep(100)
            return False
            # 检测人工校验
            if not self.pageAction.auto_robots():
                self.going_restart(is_match_proxy=True)
                return False

            # 获取当前登录用户 radix-«rej»
            current_email = product['std_email'].strip().lower()
            login_email = self.pageAction.get_login_mark()
            if login_email:
                login_email = login_email.strip().lower()
            # 如果当前处理的用户就是登录用户。直接校验 并且存储到数据库。返回吓一跳
            if current_email == login_email:
                print("check browser is logged this account, save account and next...")
                MSession.update_disabled_login_status(product, "success")
                MSession.update_one(condition={
                    "std_email": product['std_email'],
                }, data={
                    'cookie_data_first': self.driver.get_cookies(),
                    'cookie_data_last': self.driver.get_cookies(),
                    'localstorage_data_first': self.pageAction.get_local_storage_data(),
                    'localstorage_data_last': self.pageAction.get_local_storage_data(),
                    'sync_status': "success",
                    "hostname": utils.common.get_sys_uname(),
                    "browser_port": self.browser_port,
                })

                MProxyQueue.set_proxy_login_success_num(indexId = self.browser_proxy['indexId'])
                self.add_account_log(
                    account=product['account'],
                    action_info="通过网页登录成功1",
                    action_type="page_login_success"
                )
                self.going_restart(is_match_proxy=True)
                return "continue"
        else:
            print("当前浏览器进入了未知页面。")
            self.going_restart(is_match_proxy=True)
            return False

        # 清缓存，退出登录
        self.WDriver.clear_local_cache()

        loop_num = 0
        retry_num = 1
        retry_mark = None
        is_login_google_failed = False
        while True:
            loop_num = loop_num + 1
            if retry_num > 3:
                self.sysLog.log(f"retry_num: {retry_mark} failed, restart browser and next product...")
                time.sleep(20)
                self.going_restart(is_match_proxy=True)
                return False

            if loop_num > 10:
                self.sysLog.log(f"loop_num: {loop_num} failed, restart browser and next product...")
                time.sleep(20)
                self.going_restart(is_match_proxy=True)
                return False
            print("current url---->", self.driver.current_url)
            # 检测是否需要输入验证码。检测到验证码 该账号作废
            if self.pageAction.check_email_verification_code():
                retry_mark = "check_email_verification_code"
                self.sysLog.log(f"{retry_mark},checked current account disabled")
                time.sleep(10)
                MSession.update_login_status_disabled(product['std_email'])
                MSession.update_disabled_login_status(product, "failed")
                MProxyQueue.set_proxy_login_failed_num(indexId=self.browser_proxy['indexId'])
                self.add_account_log(
                    account=product['account'],
                    action_info="通过网页登录失败，原因：检测到了需要验证码",
                    action_type="page_login_failed_on_verification_code"
                )
                self.going_restart(is_match_proxy=True)
                return False
            else:
                print("没有检测到输入验证码")


            if self.pageAction.check_email_recovery_identifier():
                retry_mark = "check_email_recovery_identifier"
                self.sysLog.log(f"{retry_mark},checked current account disabled2")
                MSession.update_login_status_disabled(product['std_email'])
                MSession.update_disabled_login_status(product, "failed")
                MProxyQueue.set_proxy_login_failed_num(indexId=self.browser_proxy['indexId'])
                self.add_account_log(
                    account=product['account'],
                    action_info="通过网页登录失败，原因：账号待恢复",
                    action_type="page_login_failed_on_recovery_identifier"
                )
                self.going_restart(is_match_proxy=True)
                return False
            else:
                print("没有检测到输入验证码")


            # 设置等待时间 8-15s
            utils.common.action_wait(3000, 10000)

            if self.pageAction.auto_restart_button():
                self.sysLog.log(f"auto_restart_button, 检测到了重新开始异常问题，将回退重新来登录...")
                continue

            # 检测当前页面是否为登录页面
            if self.pageAction.check_click_login_button():
                retry_mark = "auto_click_login_button"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.auto_click_login_button():
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")

            # 开始google自动化登录
            # 点击使用google 账号登录
            if self.pageAction.login_step_check_use_google_login():
                # google登录失败的清空，需要
                if is_login_google_failed:
                    self.sysLog.log(f"is_login_google_failed, restart browser and next product...")
                    time.sleep(20)
                    self.going_restart(is_match_proxy=True)
                    return False

                retry_mark = "login_step_use_google_login"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.login_step_use_google_login():
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")

            # 点击使用其他账号登录
            # div role="link" [-1] 最后一个
            # 使用其他账号登录需要
            elif self.pageAction.login_step_check_use_other_account_login():
                retry_mark = "login_step_use_other_account_login"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.login_step_use_other_account_login():
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")

            # 输入电子邮件+下一步
            # input type="email" id=identifierId
            elif self.pageAction.login_step_check_input_email():
                retry_mark = "login_step_input_email"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.login_step_input_email(product['std_email']):
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")

                time.sleep(2)

                # 点击下一步
                # div id=identifierNext 下面的button
                retry_mark = "login_step_input_email_next"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.login_step_input_email_next():
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")

            # 输入密码
            # input name="Passwd" type="password"
            elif self.pageAction.login_step_check_input_password():
                retry_mark = "login_step_input_password"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.login_step_input_password(product['password']):
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")

                time.sleep(2)

                # 点击下一步
                # div id=“passwordNext” 下 button
                retry_mark = "login_step_input_password_next"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.login_step_input_password_next():
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")

            # 欢迎界面点击我了解
            # input type="submit", id="confirm"
            elif self.pageAction.login_step_check_keep_login_status():
                retry_mark = "login_step_confirmation_protocol"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.login_step_confirmation_protocol():
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")

            # 登录到ds操作界面，点击continue
            # div data-is-touch-wrapper=“true” 最后一个下的 button
            elif self.pageAction.login_step_check_login_to_target():
                retry_mark = "login_step_login_to_target"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.login_step_login_to_target():
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")
                is_login_google_failed = True

            elif self.pageAction.login_step_check_chat_with_aistudio():
                retry_mark = "login_step_chat_with_aistudio"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.login_step_chat_with_aistudio():
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")
                is_login_google_failed = True

            elif self.pageAction.login_step_check_use_aistudio():
                retry_mark = "login_step_use_aistudio"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.login_step_use_aistudio():
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")
                is_login_google_failed = True

            # 检测到人工校验，强制绑定。
            elif self.pageAction.check_google_captcha():
                MSession.update_one(condition={
                    "std_email": product['std_email'],
                }, data={
                    'sync_status': "success",
                    "hostname": utils.common.get_sys_uname(),
                    "browser_port": self.browser_port,
                    "login_status": "invalid"
                })
                # 这里无需更新
                # MSession.update_disabled_login_status(product, "failed")
                MProxyQueue.set_proxy_login_failed_num(indexId=self.browser_proxy['indexId'])
                self.add_account_log(
                    account=product['account'],
                    action_info="通过网页登录失败，原因：检测到了Captcha",
                    action_type="page_login_failed_on_captcha"
                )
                self.sysLog.log("checked login page has google captcha! switch browser")
                self.going_restart(is_match_proxy=True)
                return "continue"

            # 自动化cf人工校验
            elif "sorry/index" in self.driver.current_url:
                self.going_restart(is_match_proxy=True)
                return False

            else:
                time.sleep(3)
                current_url = self.driver.current_url
                if current_url.startswith("https://copilot.microsoft.com") :
                    self.sysLog.log("google login complete！to target site...")
                    break
                else:
                    self.sysLog.log("google login failed, continue")
                    time.sleep(120)
                    self.going_restart(is_match_proxy=True)
                    return False

        # time.sleep(2)
        # self.sysLog.log("browser restart...")
        # self.going_restart(is_match_proxy=False)
        # self.sysLog.log("switch_to_chat_page...")
        # if not self.pageAction.switch_to_chat_page():
        #     self.going_restart(is_match_proxy=True)
        #     self.sysLog.log("switch_to_chat_page Failed!")
        #     time.sleep(20)
        #     return False
        # self.sysLog.log("switch_to_chat_page complete！")

        # TODO 需要点击我接收协议选项
        time.sleep(4)
        self.sysLog.log("login_step_welcome_got_it ...")
        self.pageAction.login_step_welcome_got_it()
        self.sysLog.log("login_step_welcome_got_it OK")

        # TODO 需要点击我接收协议选项
        self.driver.refresh()
        time.sleep(4)
        self.sysLog.log("accept_terms_service ...")
        self.pageAction.accept_terms_service()
        self.sysLog.log("accept_terms_service OK")

        self.driver.refresh()
        time.sleep(5)

        current_email = product['std_email'].strip().lower()
        login_email = self.pageAction.get_login_mark()

        if login_email:
            login_email = login_email.strip().lower()

        # 连续刷新三次获取
        retry_idx = 0
        while True:
            retry_idx = retry_idx + 1
            if retry_idx > 4:
                self.sysLog.log("current login failed!")
                self.going_restart(is_match_proxy=True)
                return False
            time.sleep(1)
            self.sysLog.log(f"current product email:{current_email}, logged email:{login_email}")
            if current_email != login_email:
                self.sysLog.log("current login failed! not find email! retry check...")
                self.driver.refresh()
                time.sleep(5)
                continue
            else:
                break

        MSession.update_disabled_login_status(product, "success")
        MSession.update_one(condition={
            "std_email": product['std_email'],
        }, data={
            'cookie_data_first': self.driver.get_cookies(),
            'cookie_data_last': self.driver.get_cookies(),
            'sync_status': "success",
            'login_status': "success",
            "hostname": utils.common.get_sys_uname(),
            "browser_port": self.browser_port,
            'login_at': utils.common.get_now_str()
        })

        MProxyQueue.set_proxy_login_success_num(indexId=self.browser_proxy['indexId'])
        self.add_account_log(
            account=product['account'],
            action_info="通过网页登录成功",
            action_type="page_login_success"
        )
        self.sysLog.log("current login success and save success! next")
        # 登录成功，则会清理
        self.going_restart(is_match_proxy=True, clear_user_data=True)
        return "continue"

    def query(self):
        # 初始化浏览器信息
        # 首次默认重启浏览器，并且下发代理，清缓存
        is_first = True
        while True:
            try:
                # 初始化浏览器信息
                if not self.init_browser():
                    print("浏览器队列已经用尽！")
                    time.sleep(300)

                product = None

                if not product:
                    product = self.get_product()

                if not product:
                    msg_content = "产品或者浏览器队列已经用尽，请尽快补充"
                    self.sysLog.log(msg_content)
                    self.host_report_status(f"copilot-login-{gpt_conf.login_status_mode}", "queue_empty",
                                            "当前未发现待登录账号")
                    # 产品队列用尽，这里将原来running 的修改为 waiting。 并且300s后重新尝试
                    ret = MSessionQueue.update_many(condition={
                        "sync_status": "running",
                    }, data={
                        "sync_status": "waiting"
                    })
                    if ret:
                        print("find status:answer_waiting -> ask_success success!")
                    else:
                        print("not find waiting.")
                    time.sleep(300)
                    continue

                if "email" not in product or "email_assist" not in product or "password" not in product:
                    self.sysLog.log("check primary filed email/email_assist/password failed, next product...")
                    continue

                self.host_report_status(f"copilot-login-{gpt_conf.login_status_mode}", "normal",
                                        "运行正常")

                self.mark = "[email:%s]" % product['std_email']
                self.sysLog.set_mark(self.mark)
                self.sysLog.log("QUERY async-fetch - check product complete")

                # 首次运行先分配下发一可用的代理
                if is_first:
                    self.going_restart(is_match_proxy=True, clear_user_data=True)
                    is_first = False

                # 如果临时见到到代理失败，则重新获取新的代理。避免所有代理出现异常程序故障，需要sleep 120s
                if not self.check_proxy_status():
                    self.sysLog.log("check proxy status Failed switch proxy and sleep 60s...")
                    self.going_restart(is_match_proxy=True)
                    time.sleep(60)
                    continue

                self.sysLog.log("Check proxy status Okay, proceeding")

                # 故障重试机制： 连续失败n次后会触发一些处理事件
                if self.get_resp_error_num >= 5:
                    if self.get_resp_error_num == 5:
                        print("连续失败5次，重启并且匹配代理")
                        self.going_restart(is_match_proxy=True)
                    else:
                        print("连续大于5次，每次重启")
                        self.going_restart(is_match_proxy=True)

                    if 10 <= self.get_resp_error_num <= 15:
                        print("连续大于10次，每次重启并且匹配代理")
                        # 连续超过10次，每次修改10分钟，并且切换代理
                        self.going_restart(is_match_proxy=True)
                        time.sleep(600)
                    if self.get_resp_error_num > 15:
                        print("连续大于15次，重置状态。sleep 1h")
                        # 重置请求，并且直接sleep 1h
                        self.get_resp_error_num = 0
                        self.going_restart(is_match_proxy=True)
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

                        left_ts = gpt_conf.fixed_running_loop_for_login - cost_ts
                        self.sysLog.log("current requests left ts %s" % left_ts)

                        if gpt_conf.is_fixed_running_time and resp_status:
                            if left_ts > 0:
                                self.sysLog.log("======>fixed sleep %s..." % left_ts)
                                time.sleep(left_ts)
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
                            self.going_restart(is_match_proxy=True)

                        if err_retry >= 6:
                            self.sysLog.log("产品获取数据失败，切换下一个产品继续")
                            break
            except:
                print(traceback.format_exc())
                print("未知异常原因，程序等待10分钟再次运行。Error:%s" % traceback.format_exc())
                time.sleep(600)
