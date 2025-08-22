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
        self.clear_user_data = True
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
        test_email = None
        # test_email = "xopgafgwef40@hotmail.com"
        # test_email = "tclpyddgtw61@hotmail.com"
        # test_email = "zhpaxvyrmb91@hotmail.com"
        product = MSessionQueue.get_unsync_data(test_std_email=test_email)
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

        # 先进入聊天页
        if not self.pageAction.switch_to_chat_page():
            self.going_restart(is_match_proxy=True)
            self.sysLog.log("switch_to_chat_page Failed!")
            self.waiting(20)
            return False

        # 清缓存，退出登录
        self.WDriver.clear_local_cache()

        self.waiting(10)
        self.sysLog.log("准备进行自动化人工校验检测")
        # 进行自动化人工校验
        if not self.pageAction.auto_robots():
            self.going_restart(is_match_proxy=True)
            return False

        # 进入登录界面
        self.sysLog.log("switch_to_login_page...")
        if not self.pageAction.switch_to_login_page():
            self.going_restart(is_match_proxy=True)
            self.sysLog.log("switch_to_login_page Failed!")
            self.waiting(20)
            return False
        self.sysLog.log("switch_to_login_page complete！")

        # 是否需要TODO 检测人工校验？

        if self.driver.current_url.startswith('https://auth.openai.com'):
            # 检测人工校验
            if not self.pageAction.auto_robots():
                self.going_restart(is_match_proxy=True)
                return False
        else:
            print("当前浏览器进入了未知页面。")
            self.going_restart(is_match_proxy=True)
            return False

        if not self.pageAction.select_microsoft_login():
            self.going_restart(is_match_proxy=True)
            self.sysLog.log("not in login page!")
            self.waiting(20)
            return False

        loop_num = 0
        retry_num = 1
        retry_mark = None

        while True:
            loop_num = loop_num + 1
            if retry_num > 3:
                self.sysLog.log(f"retry_num: {retry_mark} failed, restart browser and next product...")
                self.waiting(20)
                self.going_restart(is_match_proxy=True)
                return False

            if loop_num > 10:
                self.sysLog.log(f"loop_num: {loop_num} failed, restart browser and next product...")
                self.waiting(20)
                self.going_restart(is_match_proxy=True)
                return False
            print("current url---->", self.driver.current_url)
            # 设置等待时间 8-15s
            utils.common.action_wait(3000, 10000)


            if self.pageAction.check_email_recovery_identifier() or self.pageAction.login_step_check_identity():
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




            # 一般应该不会触发该问题
            if self.pageAction.auto_restart_button():
                self.sysLog.log(f"auto_restart_button, 检测到了重新开始异常问题，将回退重新来登录...")
                continue

            # 邮箱验证提示：部分账号有。大多数出现该状态会无效
            # input type="email" id=identifierId
            elif self.pageAction.login_step_check_email_method():
                # 点击下一步
                # div id=identifierNext 下面的button
                retry_mark = "login_step_input_email_next"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.login_step_skip_email_code_login():
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")

            # input type="email" id=identifierId
            elif self.pageAction.login_step_check_input_email():
                retry_mark = "login_step_input_email"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.login_step_input_email(product['std_email']):
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")

                self.waiting(2)

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

                self.waiting(2)

                # 点击下一步 xopgafgwef40@hotmail.com
                # div id=“passwordNext” 下 button
                retry_mark = "login_step_input_password_next"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.login_step_input_password_next():
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")

            elif self.pageAction.login_step_check_correction():
                retry_mark = "login_step_correction"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.login_step_correction():
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")
            elif self.pageAction.login_step_check_interrupt():
                retry_mark = "login_step_interrupt"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.login_step_interrupt():
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")

            # 欢迎界面点击我了解
            # input type="submit", id="confirm"
            elif self.pageAction.login_step_check_keep_login_status():
                retry_mark = "login_step_confirmation_protocol"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.login_step_keep_login_status():
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")

            elif self.pageAction.login_step_check_accept_consent():
                retry_mark = "login_step_accept_consent"
                self.sysLog.log(f"{retry_mark}...")
                if not self.pageAction.login_step_accept_consent():
                    self.sysLog.log(f"{retry_mark} failed, retry...")
                    retry_num = retry_num + 1
                    continue
                self.sysLog.log(f"{retry_mark} complete！")

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
                self.waiting(3)
                current_url = self.driver.current_url
                if current_url.startswith("https://chatgpt.com") or current_url.startswith("https://auth.openai.com"):
                    self.sysLog.log("google login complete！to target site...")
                    break
                else:
                    self.sysLog.log("google login failed, continue")
                    self.waiting(120)
                    self.going_restart(is_match_proxy=True)
                    return False


        # TODO 需要点击我接收协议选项
        self.driver.refresh()
        self.waiting(5)

        # 注意到这里已经成功了一般。如果执行了about，则认为登录成功。但是已经登录成功过的，可能会少了该步骤。
        # 检测是否成功

        # 自动化人工校验
        # 如果检测到已经登录成功，则无需要人工校验了
        # 这里不再做人工校验失败的判断。因为有可能能直接拿到登录信息


        # 连续刷新三次获取
        retry_idx = 0
        while True:

            self.pageAction.auto_robots()
            self.pageAction.about_you_init()
            self.pageAction.auto_robots()

            retry_idx = retry_idx + 1
            if retry_idx > 4:
                self.sysLog.log("current login failed!")
                self.going_restart(is_match_proxy=True)
                return False
            self.waiting(1)

            login_status = self.pageAction.check_login_auth()
            if not login_status:
                self.sysLog.log("current login failed! not find cookie:__Secure-next-auth.session-token cookie...")
                self.driver.refresh()
                self.waiting(5)
                continue
            else:
                break

        local_storage_data = self.pageAction.get_local_storage_data()
        cookie_data = self.pageAction.get_cookie_data()

        MSession.update_disabled_login_status(product, "success")
        MSession.update_one(condition={
            "std_email": product['std_email'],
        }, data={
            'localstorage_data_first': local_storage_data,
            'localstorage_data_last': local_storage_data,
            'cookie_data_first': cookie_data,
            'cookie_data_last': cookie_data,
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
                    self.waiting(300)

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
                    self.waiting(300)
                    continue

                if "email" not in product or "email_assist" not in product or "password" not in product:
                    self.sysLog.log("check primary filed email/email_assist/password failed, next product...")
                    continue

                # 上报主机状态
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
                    self.waiting(10)
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
                        self.waiting(600)
                    if self.get_resp_error_num > 15:
                        print("连续大于15次，重置状态。sleep 1h")
                        # 重置请求，并且直接sleep 1h
                        self.get_resp_error_num = 0
                        self.going_restart(is_match_proxy=True)
                        self.waiting(3600)
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
                            self.going_restart(is_match_proxy=True)

                        if err_retry >= 6:
                            self.sysLog.log("产品获取数据失败，切换下一个产品继续")
                            break
            except:
                print(traceback.format_exc())
                print("未知异常原因，程序等待10分钟再次运行。Error:%s" % traceback.format_exc())
                self.waiting(600)
