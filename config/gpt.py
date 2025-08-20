# -*- coding:utf-8 -*-
# Desc: project app configuration
"""
"""
from utils import env, template
import subprocess,re

class gptConf:

    # --------------------- -*- 基础配置 -*- ---------------------
    debug: bool = bool(int(env("DEBUG", 0)))

    # 输入类型 letter(字母), word（单词）, sentence（句子）
    input_type = env("INPUT_TYPE", "sentence")

    # 项目名称 对应具体的项目，比如爬取提纲是一个名称，爬取内容是另外一个名称
    project_name = env("project_name", "chatgpt_spider")

    # spider_name 蜘蛛名称，固定不变化
    spider_name = "chatgpt"

    # 日志文件存储路径
    log_file_path = env("log_file_path", project_name)

    error_log_file_path = env("error_log_file_path", f"{project_name}_error")

    log_root = env("log_root", f"./storage/logs/{project_name}")

    start_bid_file = env("start_bid_file", project_name)

    browser_config_path = env("browser_config_path", "browser")

    proxy_config_path = env("proxy_config_path", "proxy")

    browser_status_file_path = env("browser_status_file_path", "browser_status")

    proxy_stop_queue_file = env("proxy_stop_queue_file", "stop_proxy_queue")

    chrome_executable_path = env("chrome_executable_path", "C:/Program Files/Google/Chrome/Application/chrome.exe")

    # 用户浏览器数据
    browser_data_path = env("browser_data_path", "D:/dev/perplexity_spider_start")

    # 源数据表
    product_queue_table = env("PRODUCT_TABLE", "bid_queue_for_%s_sm_detail_article" % spider_name)

    # 待注册邮箱队列表
    email_queue_table = env("EMAIL_QUEUE_TABLE", "email_addr")

    # 注册邮件临时存储表- 临时
    auth_table = env("AUTH_TABLE", "%s_auth" % spider_name)

    # 注册邮件存储到目标浏览器账号表- 正式
    browser_auth_table = env("BROWSER_AUTH_TABLE", "%s_browser_auth_data" % spider_name)

    # 爬取产品结果为失败表
    product_table_result_failed = env("PRODUCT_FAILED_RESULT_TABLE", "product_%s_sm_failed" % spider_name)
    # 异步获取产品
    product_table_result_failed_async = env("PRODUCT_FAILED_ASYNC_RESULT_TABLE", "product_%s_failed_async" % spider_name)

    # 爬取产品结果成功表
    product_table_result = env("PRODUCT_RESULT_TABLE", "product_%s_sm" % spider_name)
    # 将所有的数据整合到一起 合并表
    product_table_result_full = env("PRODUCT_RESULT_TABLE_FULL", "product_ast_bench_outline_detail_full")

    # 避免重复多次爬取同一个链接。这里将已经爬取到的存储到数据库中
    product_table_result_urls = env("PRODUCT_RESULT_TABLE_URLS", "google_ast_urls")

    # 账号对列表
    auth_data_table = env("AUTH_DATA_TABLE", "%s_browser_auth_data" % spider_name)

    # 是否启用将失败的数据保存到失败表中。如果保存到失败表中会一直重新尝试该数据，直到失败。0启用，0关闭
    is_save_failed_to_table = bool(int(env("is_save_failed_to_table", 0)))

    # 是否固定运行时长
    # is_fixed_running_time = bool(int(env("is_fixed_running_time", 0)))
    is_fixed_running_time = True

    # 固定运行时长周期
    fixed_running_loop_ts = 80  # 15 0windows, total 25.9w/day

    fixed_running_loop_for_login = 50  # 150windows, total 25.9w/day

    fixed_running_loop_ts_async = int(env("fixed_running_loop_ts_async", 5))

    # 入口/首页/新聊天等入口
    url = "https://chatgpt.com/"

    # login 如果未登录，会跳转到登录界面
    login_url = "https://auth.openai.com/log-in"

    # 设置一个dirver 初始化后默认的页面
    driver_default_page = url

    # TODO 必须配置 默认加载template文件，evite加载 template_evitachem
    ask_template = template(env("template_name", "template"))
    # 后面需要配置多个端口，同时登录，同时开启
    # --------------------- -*- 浏览器窗口相关配置 -*- ---------------------
    # 浏览器窗口
    window_x = int(env("window_x", 300))
    window_y = int(env("window_y", 250))
    window_rate = env("window_rate", 1)

    # 浏览器排列x位置
    position_x = int(env("position_x", 0))
    # 浏览器排列y位置
    position_y = int(env("position_y", 1))
    # 起始id
    position_start_id = int(env("position_start_id", 0))
    # 每行排列的数量：
    max_x_id = int(env("max_x_nums", 5))
    # 宽度
    window_width = int(env("window_width", 515))
    # 高度
    window_height = int(env("window_height", 250))
    # 最小限制 ID
    client_min_bid = int(env("CLIENT_MIN_BID", 0))
    # 最大限制 ID
    client_max_bid = int(env("CLIENT_MAX_BID", 9999999))

    product_name_len_lte = int(env("product_name_len_lte", 10))

    # 最小限制 ID
    client_min_bid_for_queue = int(env("CLIENT_MIN_BID_FOR_QUEUE", client_min_bid))
    # 最大限制 ID
    client_max_bid_for_queue = int(env("CLIENT_MAX_BID_FOR_QUEUE", client_max_bid))

    proxy_source_type = env("proxy_source_type", "") # "anyland", "jikeyun", feijiyunduijie-lz, tagss, suyunti, lanfan
    proxy_countries = env("proxy_countries", "") # "hk,tw"

    # 禁用的，多个用逗号隔开
    dis_source_type = env("dis_source_type", "")

    clear_cache = env("clear_cache", True)

    need_switch_language_model = bool(int(env("need_switch_language_model", 1)))

    # pro账号最大限制 500
    account_day_max_req_num_for_pro=int(env("account_day_max_req_num_for_pro", 500))
    # custom 普通账号最大3次
    account_day_max_req_num_for_custom = int(env("account_day_max_req_num_for_custom", 500))

    # 是否需要登录以token来执行。如果以token来执行
    is_token_auto_login = bool(int(env("is_token_auto_login", True)))

    # 登录凭证方式：cookie/localstorage/localstorage + cookie 支持多重校验方式
    auth_login_mode = ['localstorage', "cookie"]

    # 登录凭证，如果未定义，则直接同步所有的 localstorage 和 cookie
    auth_login_cert = {
        "type": "cookie",
        "key": "__Secure-next-auth.session-token"
    }

    # token/file 每次获取最新的token文件 文件：9600-1/9600-2  9601-1/9601-2  不存在则从原始的key文件中获取
    origin_token_file = env("origin_token_file", "origin_tokens")
    new_token_file = env("new_token_file", "./storage/data/token")

    is_save_log= bool(int(env("is_save_log", 0)))

    # 代理 server 服务器
    proxy_server = env("proxy_server", "127.0.0.1")

    proxy_server_for_login = env("proxy_server_for_login", f"{proxy_server}")

    # 代理主机ip地址
    proxy_host = env("proxy_host", proxy_server)

    # 远程服务器地址：
    remote_server = env("remote_server", f"http://{proxy_server}:8053")

    # 远程服务器地址：
    remote_server_for_login = env("remote_server_for_login", f"http://{proxy_server_for_login}:8053")

    # webdirver 拦截地址  TODO 如果启用，以下方案需要验证。当前只是修改了域名，并没有实际校验过
    interceptor_urls = [
        "challenges.cloudflare.com/cdn-cgi/challenge-platform/*",
        "https://challenges.cloudflare.com/cdn-cgi/challenge-platform/*"
    ]


    # 登录补号模式 waiting 和disabled模式
    # waiting  未触发登录验证码的账号
    # disabled 触发过登录验证码的账号
    login_status_mode = env("login_status_mode", "waiting")

    # 当前批次
    outline_ask_processing = int(env("deep_app_processing", 0))

    # 是否开启账号活动记录
    enable_account_log = bool(int(env("enable_account_log", 0)))

