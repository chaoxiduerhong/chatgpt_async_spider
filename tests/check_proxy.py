import traceback
from fake_useragent import UserAgent
import requests

proxies = {"http": "192.168.0.113:11395", "https": "192.168.0.113:11395"}


def check_proxy_status():
    # TODO
    try:
        url = "https://chatgpt.com"
        response = requests.get(url, verify=False,
                                proxies=proxies, timeout=15, headers={
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"})
        if response.status_code == 200:
            return True
        return False
    except:
        return False

print(check_proxy_status())