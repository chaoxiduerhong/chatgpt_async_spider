import traceback
import time
import queue
import utils.common
from bs4 import BeautifulSoup
import urllib.parse
import datetime
import requests
import json
from fake_useragent import UserAgent

def crawl(req_url):
    """
    开始爬取
    """

    def req(url):
        """
        通过requests的方式
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;"
                          "q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            }
            response = requests.get(url, allow_redirects=True, headers=headers)
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

            # 设置无头模式
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")  # 可选
            chrome_options.add_argument("--no-sandbox")  # 可选
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # 可选
            # 初始化驱动
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            try:
                driver.get(url)
                final_url = driver.current_url
            finally:
                driver.quit()
        except:
            pass
        return final_url

    target_url = None
    if req_url:
        target_url = req(req_url)
    if not target_url:
        target_url = web_req(req_url)
    if not target_url:
        pass
    return target_url

print(crawl("https://vertexaisearch.cloud.google.com/grounding-api-redirect/AbF9wXGIx4VCKpO28xSoViAg6M6adClEMmsHy_xX0IVNbop5dsdPgQZxJDTYuGlyqqGiFt0HMA3bXZO1TGaEYQm984tld1MmwJ6s4kTNK_Wpoa693R0ltxyb8hLKtdKe4xrJo6iqh2mvp8mNmyiBDtMmq-ujyL9TN-Hr25FYn7mIHl3sjkNmjxBSWz_fTtEg8yAF8cPaMFK48isepaDk8d9HnnmudBCwYkI="))