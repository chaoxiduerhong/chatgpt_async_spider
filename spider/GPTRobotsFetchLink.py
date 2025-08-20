# -*- coding:utf-8 -*-
"""
异步抓取页面链接

使用最原始的请求方式，非浏览器模式。

启用100个线程，针对100个不同的产品

link_processing: waiting success failed

需要将原来的数据解析出来
"""

import traceback
import time
import utils.common
from bs4 import BeautifulSoup
import urllib.parse

import datetime
from config import gpt_conf
import requests
import json
from fake_useragent import UserAgent

from models import MProductsResult, MProductsResultLink
from models import ProductsResultModel
from models import ProductsResultFullModel
from pymongo import ReturnDocument
from models.HostStatus import HostStatusModel


class GPTFetchLink:
    def __init__(self, thread_lock, thread_num):
        self.lock = thread_lock
        self.thread_name = "THREAD_%s" % thread_num
        self.thread_num = thread_num
        self.bid = None
        self.test_bid = None
        self.product_table_idx = -1
        self.product_table_max_idx = -1
        self.proxies = None
        self.proxy_source_type=None
        self.proxy_remarks = None
        self.proxy_status = None
        # 需要设置一个版本。跟清理规则类似。每次按版本遍历
        self.link_version = 1
        self.mark = ""
        # 认为必须0表成功，才可能有其他数据集
        self.queue_product_table = "product_ast_bench_outline_detail_0"
        self.queue_product_full_table = "product_ast_bench_outline_detail_full"
        self.target_table_template = "product_ast_bench_outline_detail_{idx}"
        self.MProductsResult = ProductsResultModel()
        self.MProductsResultFull = ProductsResultFullModel()
        # 2025-06-17 09:08:33 必须要有固定时间，因为最新数据不全的概率太高
        self.end_time = gpt_conf.query_link_end_time
        self.start_time = gpt_conf.query_link_start_time
        self.time_ts = None
        self.report_ts = 0

    def host_report_status(self, notice_status, notice_info):
        """
        链接123 数据库上报信息
        notice_status: 上报的状态（子线程信息）  一般：normal/queue_empty 这两种状态
        notice_info： 上报的信息。只有当上报的状态异常的时候，才会显示（子线程信息）

        """
        current_ts = utils.common.get_second_utime()
        if current_ts - self.report_ts > 120:
            self.report_ts = current_ts
            from models.HostStatus import HostStatusModel
            hostStatus = HostStatusModel()
            data = {
                "thread_id": str(self.thread_num),
                "thread_name": str(self.thread_num),
                "server_name": f"copilot-Link-{gpt_conf.query_detail_mode}",
                "project_name": "aistudio_spider",
                "thread_status": notice_status,
                "thread_info": notice_info,
            }
            hostStatus.report_status(data)
            time.sleep(30)

    def get_product(self):

        def get_details0():
            with self.lock:
                self.MProductsResult.set_table_name(self.queue_product_table)
                product_data = self.MProductsResult.getFirstProductByFetchLink(link_version=self.link_version, bid=self.test_bid, end_time=self.end_time, start_time=self.start_time)
                return product_data

        def get_full_detail():
            """
            补充数据，从总表中筛选
            1. 帅选状态完成，但是 link_status 这个字段的。获取后的数据将 link_status 设置为 running，成功运行结束后修改为 completed 。失败运行设置为 waiting
            2. link_status 状态为 waiting的。
            当没有结果集后，
            """
            with self.lock:
                product_data = self.MProductsResultFull.lock_find_one_and_update(
                {
                        "link_status": "waiting"
                    },
                {
                        "$set": {
                            "link_status": "running"
                        }
                    },
                    sort=None,
                    return_document=ReturnDocument.AFTER
                )

                if not product_data:
                    print("current full data is empty. 1500s set link_status waiting->running")
                    time.sleep(1500)
                    self.MProductsResultFull.update_many(data={
                        "link_status": "waiting"
                    }, condition={
                        "link_status": "running"
                    })
                return product_data

        if gpt_conf.query_detail_mode == "fill":
            product = get_full_detail()
            print("----*** current query_detail_mode fill")
        else:
            print("----*** current query_detail_mode add")
            product = get_details0()
        result = {}
        if product:
            # 根据bid 获取其他对应表的数据
            for table_idx in range(43):
                current_table_name = self.target_table_template.replace("{idx}", str(table_idx))
                self.MProductsResult.set_table_name(current_table_name)
                sub_product = self.MProductsResult.getFirstProductByFetchLink(link_version=self.link_version, bid=product['bid'])
                result[str(table_idx)] = sub_product

        return result

    def log(self, msg):
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        mark = f" [{self.thread_name}] - [{self.bid}] - [{self.time_ts}] - [{self.product_table_idx}/{self.product_table_max_idx}]"
        msg = "[%s]%s%s\n" % (now, mark, msg)
        print(msg)


    def api_proxy_issue(self):
        # req_url = f"{gpt_conf.remote_server}/proxy_issue_random"
        req_url = f"{gpt_conf.remote_server}/proxy_issue_random_with_option?proxy_source_type=yep,yeshayun,swiftnet,jikeyun"
        print( f"api_proxy_issue: {req_url}")

        resp = requests.get(url=req_url, timeout=3)
        resp_json = json.loads(resp.content)
        return resp, resp_json


    def proxy_issue(self):
        """
        获取下发的代理，并且远端上报error状态
        下发代理成功，更新本地浏览器代理配置
        """
        with self.lock:
            try:
                resp, resp_json = self.api_proxy_issue()
                browser_proxy = resp_json['data']
                try:
                    proxy_address = "http://%s:%s" % (gpt_conf.proxy_host, browser_proxy['port'])
                    self.proxies = {"http": proxy_address, "https": proxy_address}
                    self.log("proxy issue success:%s" % resp.content)
                    self.proxy_source_type = browser_proxy['source_type']
                    self.proxy_remarks = browser_proxy['remarks']
                    self.proxy_status = browser_proxy['status'] if "status" in browser_proxy else None
                except:
                    self.proxies = None
                    self.log("proxy issue failed:%s" % resp.content)

            except Exception as e:
                self.log("*** proxy_issue failed: %s" % traceback.format_exc())
                self.proxies = None

    def get_urls(self, origin_refs_html):
        """
        这里获取urls
        """
        def decode_url(url):
            """
            获取q参数并且解码
            """
            url = url.replace('&amp;', '&')
            parsed_url = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            q_param = query_params.get('q', [None])[0]
            if q_param:
                decoded_q = urllib.parse.unquote(q_param)
                return decoded_q
            else:
                return None

        result = []
        html = origin_refs_html
        soup = BeautifulSoup(html, 'html.parser')
        # 原始链接 https://www.google.com/url?sa=E&amp;q=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Fgrounding-api-redirect%2FAbF9wXF9RzX3AUNOvRUr639fJez1QLIpoSuXYFny7RQhTqkAmU4zH-r-ZdZ6G7lYANMpN6VyslJQn4CSXJFKnEAlUiP3z7xSmvzggX9dh5c9EUAPu0s70dHn0SuLds6bHg%3D%3D
        # 解析后的链接
        for li in soup.find_all('li'):
            a_tag = li.find('a')
            if a_tag:
                item = {
                    'google_url': a_tag.get('href'),
                    'origin_url': decode_url(a_tag.get('href')),
                    'text': a_tag.get_text(strip=True),
                }
                result.append(item)
        return result

    def crawl(self, urls):
        """
        开始爬取
        """

        def req(url):
            """
            通过requests的方式
            """
            ua = UserAgent()
            try:
                headers = {
                    "User-Agent": ua.random,
                    "Accept": "text/html,application/xhtml+xml,application/xml;"
                              "q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                }
                response = requests.get(url, allow_redirects=True, headers=headers, proxies=self.proxies, timeout=5)
                final_url = response.url
                return final_url
            except:
                return None

        def req_by_head(url):
            ua = UserAgent()
            try:
                headers = {
                    "User-Agent": ua.random,
                    "Accept": "text/html,application/xhtml+xml,application/xml;"
                              "q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                }
                response = requests.head(url, allow_redirects=True, headers=headers, proxies=self.proxies, timeout=5)
                if response.status_code == 405:  # 服务器不支持 HEAD，fallback 到 GET（加 stream 避免读内容）
                    response = requests.get(url, allow_redirects=True, headers=headers, proxies=self.proxies, timeout=5)
                final_url = response.url
                return final_url
            except:
                return None

        def web_req(url):
            final_url = None
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service
                from selenium.webdriver.chrome.options import Options
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

                caps = DesiredCapabilities().CHROME.copy()
                caps["pageLoadStrategy"] = "eager"  # 或 "none"

                # 设置无头模式
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--disable-gpu")  # 可选
                chrome_options.add_argument("--no-sandbox")   # 可选
                chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # 可选

                chrome_options.add_argument(f"--proxy-server=%s" % self.proxies['http'])

                chrome_options.set_capability("pageLoadStrategy", "eager")

                # 初始化驱动
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
                try:
                    driver.set_page_load_timeout(5)
                    driver.get(url)
                    final_url = driver.current_url
                finally:
                    driver.quit()
            except:
                pass
            return final_url

        result = []
        for url_info in urls:
            req_url = url_info['origin_url']

            if not req_url:
                self.log("not find origin_url")
                continue

            # 优先检测链接数据库中是否存在
            url_key = utils.md5(req_url)
            url_pre = MProductsResultLink.first(condition={
                "uuid": url_key
            })
            if url_pre:
                target_url = url_pre['target_url']
                self.log("by google_ast_urls get url, current url:%s" % req_url)
            else:
                retry_num = 0
                target_url = None
                while True:
                    retry_num = retry_num + 1
                    if retry_num > 3:
                        break
                    try:
                        self.log("by requests get url, [%s/3]current url:%s" % (retry_num,req_url))
                        target_url = req_by_head(req_url)
                        if target_url:
                            self.log("by requests get url, success url:%s" % target_url)
                            break
                        else:
                            self.log("by requests get url failed， \n url:%s, \n proxy_source_type:%s, \n proxy_remarks:%s, \n proxy_status:%s" %
                                 (req_url, self.proxy_source_type, self.proxy_remarks, self.proxy_status))
                            # 爬取失败 应该切换代理
                            self.log("switch proxy...")
                            self.proxy_issue()


                        # target_url = web_req(req_url)
                        # if target_url:
                        #     self.log("by web_req get url, success url:%s" % target_url)
                        #     break
                        # self.log("by web_req get url failed， retry...")

                    except Exception as e:
                        print(traceback.format_exc())
                        time.sleep(1)
                        continue
                if target_url:
                    try:
                        url_pre = MProductsResultLink.first(condition={
                            "uuid": url_key
                        })
                        # 这里做判断是因为，同一个id，两个不通的outline（比如0，1表）可能有相同的引用链接. 即使这里做判断 也有可能会触发下面的异常
                        # 后期考虑不做link入库。不然会越来越慢
                        if url_pre:
                            self.log("Exists url key: %s" % url_key)
                        else:
                            MProductsResultLink.add_one(
                                data={
                                    'target_url': target_url,
                                    'uuid': url_key,
                                    "origin_url": req_url,
                                    "hostname": utils.common.get_sys_uname()
                                }
                            )
                    except:
                        # 插入失败 可能是已经存在
                        pass
            self.log("get target_url success: %s" % target_url)
            url_info['url'] = target_url
            result.append(url_info)
        return result

    def query(self):
        is_first = True
        while True:
            try:
                self.bid = None
                self.product_table_idx = -1
                self.product_table_max_idx = -1
                products = None

                if not products:
                    products = self.get_product()

                if not products:
                    msg_title = "产品队列用尽通知"
                    msg_content = " 产品已经用尽，请尽快补充产品 "
                    self.host_report_status("queue_empty", "产品已经用尽，请尽快补充产品")
                    self.log(msg_content)
                    time.sleep(600)
                    continue



                self.product_table_max_idx = len(products)

                # 首次运行先分配下发一可用的代理
                if is_first:
                    # TODO 这里下发一个代理
                    self.proxy_issue()
                    is_first = False

                # 注意 每一个product 代表的是一个表中对应的数据
                for product_idx in products:

                    # 因为爬取链接一个轮询比较慢。有时候超过10分钟
                    self.host_report_status("normal", "运行正常")
                    
                    product = products[product_idx]
                    current_table_name = self.target_table_template.replace("{idx}", str(product_idx))
                    self.product_table_idx = int(product_idx)

                    if not product:
                        self.log("current %s by bid:%s not find data"% (current_table_name, self.bid))
                        continue

                    self.MProductsResult.set_table_name(current_table_name)

                    # 产品数据检测
                    if "bid" not in product or "answer_list" not in product:
                        self.log("check primary filed failed, next product...")
                        continue

                    self.bid = product["bid"]
                    self.time_ts = product["time"]

                    answer_list = product['answer_list']

                    if len(answer_list) == 0:
                        self.log("current product answer_list is empty!")
                        time.sleep(1)
                        continue

                    self.log("get product success, bid: %s" % product['bid'])

                    self.log("check product check Okay, proceeding")


                    for product_answer in answer_list:
                        # TODO 这里解析待爬取列表
                        urls = self.get_urls(product_answer['origin_refs'])
                        if not urls:
                            self.log("current product not find urls, next table...")
                            continue

                        # 补充模式不做以下验证
                        if gpt_conf.query_detail_mode != "fill" and "link_status" in product_answer and product_answer["link_status"] == "success":
                            self.log("current item link_status is success, next table...")
                            continue

                        # TODO 这里执行爬取
                        link_status = "failed"
                        try:
                            result = self.crawl(urls)
                        except:
                            result = []
                            print(traceback.format_exc())
                            self.log("current product crawl refs failed! switch proxy")
                            self.proxy_issue()

                        # 这里获取存储 更新refs字段
                        if not result:
                            self.log("current product get refs failed!")
                        else:
                            link_status = "success"
                        product_answer['link_status'] = link_status
                        product_answer['refs'] = result

                    # 更新结果集
                    self.MProductsResult.update_one(data={
                        "answer_list": answer_list,
                        "link_processing": "complete"
                    }, condition={
                        "bid": product['bid']
                    })

                    self.log("current product get refs complete! next table...")
                if self.bid and gpt_conf.query_detail_mode == "fill":
                    self.MProductsResultFull.update_one(data={
                        "link_status": "completed"
                    }, condition={
                        "bid": self.bid
                    })

            except:
                print(traceback.format_exc())
                self.log(f"未知异常原因，程序等待10分钟再次运行。Error:%s" % traceback.format_exc())
                time.sleep(600)



            if self.test_bid:
                print("test mode end")
                return
