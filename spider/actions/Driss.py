"""
主要解决人工校验问题
链接窗口，打开新标签
等待人工校验，并且打开
"""

import time
import traceback
from distutils.command.config import config

from DrissionPage import ChromiumPage, ChromiumOptions, WebPage
from DrissionPage.common import Keys, By

from config.gpt import gptConf


class Driss:
    def __init__(self, port):
        self.port = port
        self.driver = self.getDriver()

    def getDriver(self):
        co = ChromiumOptions()
        # 阻止“自动保存密码”的提示气泡
        co.set_pref('credentials_enable_service', False)
        # 阻止“要恢复页面吗？Chrome未正确关闭”的提示气泡
        co.set_argument('--hide-crash-restore-bubble')
        co_page = ChromiumOptions().set_local_port(self.port)
        return ChromiumPage(co_page)

    def initDriver(self):
        self.driver = self.getDriver()

    def check_robots(self):
        try:
            self.driver.ele((By.CSS_SELECTOR, 'div.main-wrapper[role="main"]'))
            return True
        except:
            return False

    def ask(self):
        import random
        input_box = self.driver.ele((By.ID, "userInput"))
        a = random.randint(1, 100)
        b = random.randint(1, 100)
        query = f"{a} + {b} = ?"
        input_box.input(query)
        time.sleep(1)
        input_box.input(Keys.ENTER)


    def auto_robots_by_ask(self):
        """
        针对询问才能触发的
        """
        try:
            idx = 0
            while True:
                idx += 1
                # 最大两次测试
                if idx > 3:
                    print("多次人工校验未解决")
                    return False
                # 先提问
                self.ask()
                time.sleep(5)
                # 检测：没有人工校验
                if not self.check_robots():
                    return True
                else:
                    try:
                        dom = self.driver. \
                            ele((By.CSS_SELECTOR, 'div.main-wrapper[role="main"]')). \
                            ele((By.TAG_NAME, "div")).shadow_root. \
                            ele((By.TAG_NAME, "iframe")).ele((By.TAG_NAME, "body")).shadow_root. \
                            ele((By.TAG_NAME, "input"))
                        dom.click()
                    except Exception as e:
                        continue
        except:
            print(traceback.format_exc())
            return False

    def auto_robots(self):
        """
        先检测人工校验是否存在，如果不存在则输入ask：两个随机数相加
        如果检测到了，则直接人工校验
        """
        time.sleep(5)
        try:
            dom = self.driver. \
                ele((By.CSS_SELECTOR, 'div.main-wrapper[role="main"]')). \
                ele((By.CSS_SELECTOR, "div[id]")).ele((By.TAG_NAME, "div")).ele((By.TAG_NAME, "div")).shadow_root. \
                ele((By.TAG_NAME, "iframe")).ele((By.TAG_NAME, "body")).shadow_root. \
                ele((By.TAG_NAME, "input"))
            dom.click()
        except Exception as e:
            return False


    def to_click(self):
        print("DISS create new tab")
        self.driver = self.driver.new_tab()

        time.sleep(2)
        print("DISS to chat page")
        self.driver.get(gptConf.url)

        time.sleep(10)
        self.auto_robots()
        print("DISS handle ok")
