# -*- coding:utf-8 -*-
"""
支持浏览器管理 + 数据上报接口管理
"""
import time
import psutil
import json
import random
from flask import Flask, request, render_template, jsonify
from flask_cors import CORS
import utils
import utils.common
from spider.browser import BrowserManager
import threading
from utils import log
from config.gpt import gptConf
from models import MProxyQueue, MSession

app = Flask(__name__, static_url_path='')
CORS(app, supports_credentials=True)
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['TEMPLATES_FOLDER'] = "templates"
app.config['STATIC_FOLDER'] = "static"

lock = threading.Lock()
report_ts = 0

def arg(rkey=None, default=None):
    jsonData = request.get_data()
    formData = request.values.to_dict()
    resData = {}
    if jsonData:
        jsonData = json.loads(jsonData.decode("utf-8"))
        resData = jsonData
    elif formData:
        resData = formData
    if not rkey and jsonData:
        return jsonData
    if not rkey and formData:
        return formData

    if rkey is not None:
        if rkey in resData:
            if not resData[rkey]:
                if default is None:
                    return None
                else:
                    return default
            return resData[rkey]
        else:
            if default is None:
                return None
            else:
                return default
    else:
        if not resData:
            if default is not None:
                return default
            else:
                return None
        return resData


@app.before_request
def host_report_status():
    """
    链接123 数据库上报信息
    notice_status: 上报的状态（子线程信息）  一般：normal/queue_empty 这两种状态
    notice_info： 上报的信息。只有当上报的状态异常的时候，才会显示（子线程信息）

    """
    global report_ts
    current_ts = utils.common.get_second_utime()
    if current_ts - report_ts > 120:
        report_ts = current_ts
        from models.HostStatus import HostStatusModel
        hostStatus = HostStatusModel()
        data = {
            "thread_id": "0",
            "thread_name": "0",
            "server_name": f"copilot-server",
            "project_name": "aistudio_spider",
            "thread_status": "normal",
            "thread_info": "运行正常",
        }
        hostStatus.report_status(data)
        time.sleep(30)

@app.route('/', methods=['GET'])
def index():
    """
    数据统计
    """

    memory = psutil.virtual_memory()
    memory_use_percent = "%s %%" % memory.percent
    memory_total = "%s" % (int(memory.total) / (1024.0 ** 3))
    memory_available = "%s GB" % (int(memory.available) / (1024.0 ** 3))
    data = {
        "memory_use_percent": memory_use_percent,
        "memory_total": memory_total,
        "memory_available": memory_available
    }
    return render_template("index.html", **data)


@app.route('/browser', methods=['GET'])
def browser():
    """
    请求方式：POST
    :return:
    """
    browserManager = BrowserManager()
    lists = browserManager.get_list()
    proxy_list = browserManager.get_proxy_list()
    data = {
        "lists": lists,
        "proxy_list": proxy_list
    }
    return render_template("browser.html", **data)


@app.route('/set_proxy', methods=['GET'])
def set_proxy():
    """
    设置单个浏览器的代理
    """
    port = arg("port")
    proxy_name = arg("proxy_name")
    if port and proxy_name:
        browserManager = BrowserManager()
        browserManager.set_proxy(port, proxy_name)
    response_data = {'msg': 'success', 'code': 200}
    return jsonify(response_data)


@app.route('/open_all_browser', methods=['GET'])
def open_all_browser():
    """
    打开所有浏览器
    请求方式：POST
    :return:
    """
    browserManager = BrowserManager()
    browserManager.start_all_browser()
    response_data = {'msg': 'success', 'code': 200}
    return jsonify(response_data)


@app.route('/open_browser', methods=['GET'])
def open_browser():
    """
    打开单个浏览器
    请求方式：POST
    :return:
    """
    uid = arg("uid")
    browserManager = BrowserManager()
    if uid:
        browserManager.open_browser(uid)
    response_data = {'msg': 'success', 'code': 200}
    return jsonify(response_data)


@app.route('/close_all_browser', methods=['GET'])
def close_all_browser():
    """
    关闭所有浏览器
    请求方式：POST
    :return:
    """
    browserManager = BrowserManager()
    browserManager.stop_all_browser()
    response_data = {'msg': 'success', 'code': 200}
    return jsonify(response_data)


@app.route('/close_browser', methods=['GET'])
def close_browser():
    """
    关闭单个浏览器
    请求方式：POST
    :return:
    """
    uid = arg("uid")
    browserManager = BrowserManager()
    if uid:
        browserManager.stop_browser(uid)
    response_data = {'msg': 'success', 'code': 200}
    return jsonify(response_data)


@app.route('/restart_browser', methods=['GET'])
def restart_browser():
    """
    关闭单个浏览器
    请求方式：POST
    :return:
    """
    uid = arg("uid")
    proxy_name = arg("proxy_name")
    browserManager = BrowserManager()
    if uid:
        browserManager.restart_browser(uid, proxy_name)
    response_data = {'msg': 'success', 'code': 200}
    return jsonify(response_data)


@app.route('/reorder', methods=['GET'])
def reorder():
    """
    关闭单个浏览器
    请求方式：POST
    :return:
    """
    browserManager = BrowserManager()
    browserManager.reorder()
    response_data = {'msg': 'success', 'code': 200}
    return jsonify(response_data)


@app.route('/update_browser_port', methods=['GET'])
def update_browser_port():
    browser = BrowserManager()
    browser.browser_port_update()
    response_data = {'msg': 'success', 'code': 200}
    return jsonify(response_data)


# 代理分配相关
@app.route('/proxy_issue', methods=['GET'])
def proxy_issue():
    """
    分配一个可用的代理。
    1. running_ts: 必须为 30分钟内未使用的
    2. duration_ts: 正序排序
    3. status: 必须为"running"状态。
    4. 该接口必须添加 flask 线程锁
    分配完代理，设置当前 时间为 running_ts
    如果没有可用代理，则在当前可用的代理中随机获取一个。跟其他代理共用？
    """
    with lock:
        # 代理类型限制
        proxy_source_type = arg("proxy_source_type", "")
        proxy_source_list = []
        if proxy_source_type:
            proxy_source_list = proxy_source_type.strip().split(",")

        dis_source_list = []
        dis_source_type = arg("dis_source_type", "")
        if dis_source_type:
            dis_source_list = dis_source_type.strip().split(",")

        # 国家限制
        proxy_countries = arg("proxy_countries")
        print(f"proxy counties b4: {proxy_countries}")
        if proxy_countries:
            proxy_countries = proxy_countries.split(",")
            proxy_countries = list(set(proxy_countries))# Remove duplicates from proxy_countries list
            converted_countries = []
            for country in proxy_countries:
                if country.lower() == 'hk':
                    converted_countries.extend(['香港'])
                elif country.lower() == 'tw':
                    converted_countries.extend(['台湾'])
                elif country.lower() == 'us':
                    converted_countries.extend(['美国'])
                else:
                    converted_countries.append(country)
            proxy_countries = converted_countries
        print(f"proxy counties after convertion: {proxy_countries}")

        condition = {}
        if proxy_source_list:
            condition['source_type'] = {"$in": proxy_source_list}
        elif dis_source_list:
            condition['source_type'] = {"$nin": dis_source_list}

        if proxy_countries:
            regex_pattern = '|'.join(proxy_countries)  # Create regex pattern to match any of the countries
            condition['remarks'] = {
                "$regex": regex_pattern
            }

        # 获取20分钟内没有使用过的一条代理路线
        curr_ts = utils.common.get_second_utime()
        exp_ts = curr_ts - 1200
        data = None
        response_data = {'msg': 'Not enough proxy server have been assigned. please try again later', 'code': 4000, 'data': {}}

        if not data:
            # 活跃代理池有数据，随机在活跃代理池中获取一条数据
            condition['running_ts'] = {"$lte": exp_ts}
            condition['status'] = "running"
            data_list = MProxyQueue.get(condition=condition)
            if data_list:
                data = random.choice(data_list)
                data['data_source_mode'] = "optimal"
                data['condition'] = condition


        # 20分钟没有被运行，并且只要原来成功过的。
        # dis_source_type 如果禁用了某些代理商，说明是大规模运行，需要预备兜底方案。
        if not data and dis_source_type:
            condition['running_ts'] = {"$lte": exp_ts}
            condition['success_num'] = {"$gte": 10}

            data_list = MProxyQueue.get(condition=condition, length=20, order_by={
                "running_ts": -1,
                "success_num": -1
            })
            if data_list:
                data = random.choice(data_list)
                data['data_source_mode'] = "success_num_gte_10"
                data['condition'] = condition

        # TODO 兜底方案：api检测成功的
        if data:
            data['_id'] = str(data['_id'])
            MProxyQueue.update_one(condition={
                "indexId": data['indexId'],
            }, data={
                "running_ts": utils.common.get_second_utime()
            })
            response_data = {'msg': 'success', 'code': 200, 'data': data, 'condition': condition}
        return jsonify(response_data)

@app.route('/proxy_issue_random', methods=['GET'])
def proxy_issue_random():
    """
    直接获取一个随机代理。无需关心代理的质量
    """
    data_list = MProxyQueue.get(condition={
        "status": "running"
    })
    data = None
    if data_list:
        data = random.choice(data_list)
        data['_id'] = str(data['_id'])
    response_data = {'msg': 'success', 'code': 200, 'data': data}
    return jsonify(response_data)

@app.route('/proxy_issue_random_with_option', methods=['GET'])
def proxy_issue_random_with_option():
    """ 直接获取一个随机代理。无需关心代理的质量 """
    # proxy_source_type = arg("proxy_source_type")
    proxy_source_type = None
    proxy_source_type_list = []
    if proxy_source_type:
        proxy_source_type_list = proxy_source_type.strip().split(",")
        
    condition = {
        "status_check_base": "running",
    }
    if proxy_source_type_list:
        condition['source_type'] = {
            "$in": proxy_source_type_list
        }
    print(condition)

    data_list = MProxyQueue.get(condition=condition)
    data = None
    if data_list:
        data = random.choice(data_list)
        data['_id'] = str(data['_id'])
    response_data = {'msg': 'success', 'code': 200, 'data': data}
    return jsonify(response_data)

@app.route('/proxy_issue_for_login', methods=['GET'])
def proxy_issue_for_login():
    """
    1. 关于google登录，最好用美国节点。使用美国节点后会大大降低登录提示输入验证码的情况
    2. 同一个代理地址不要连续登录。连续登录会增加验证码的概率
    """
    print("收到了请求", utils.common.get_now_str())
    proxy_source_type = arg("proxy_source_type")
    proxy_source_list = []
    data = None
    if proxy_source_type:
        proxy_source_list = proxy_source_type.strip().split(",")

    with lock:
        curr_ts = utils.common.get_second_utime()
        # 400个代理 1h一个
        exp_ts = curr_ts - 3600

        # 活跃代理池有数据，随机在活跃代理池中获取一条数据
        condition = {
            "status": "running",
            "$or": [
                {"login_ts": {"$exists": False}},
                {"login_ts": {"$lte": exp_ts}}
            ],
            'remarks': {
                "$regex": "美国"
            }}

        if proxy_source_list:
            condition['source_type'] = {
                "$in": proxy_source_list
            }
        print(condition)
        data_list = MProxyQueue.get(condition=condition, length=10, order_by={
            "duration_ts": 1,
            "login_success_num": -1,
            "login_failed_num": 1,
            "login_ts": 1,
            "running_ts": 1
        })
        if data_list:
            data = random.choice(data_list)

        if not data:
            response_data = {'msg': 'not find active proxy. please try again later', 'code': 4000, 'data': {}}
            return jsonify(response_data)

        data['_id'] = str(data['_id'])
        ret = MProxyQueue.update_one(condition={
            "indexId": data['indexId']
        }, data={
            "running_ts": utils.common.get_second_utime(),
            "login_ts": utils.common.get_second_utime(),
        })
        response_data = {'msg': 'success', 'code': 200, 'data': data, 'condition': condition, "ret": ret}
        return jsonify(response_data)

@app.route('/proxy_report_error', methods=['GET'])
def proxy_report_error():
    """
    上报一个异常的代理。直接通过端口
    """
    proxy_port = arg("proxy_port")
    current = MProxyQueue.first(condition={
        'port': int(proxy_port)
    })
    print(current)
    current_ts = utils.common.get_second_utime()
    # 当前状态为running 并且 上次正常运行时间到当前不足n分钟，则不上报该代理为异常。
    # 原因：部分机器会产生误报的情况。这种情况可以切换代理，但是该代理只能在半个小时后才能设置为异常
    if current['status'] == "running" and current_ts - current['running_ts'] < 1200:
        response_data = {'msg': 'success', 'code': 200, 'data': "exp 20min"}
        return jsonify(response_data)

    MProxyQueue.update_one(condition={
        'port': int(proxy_port)
    }, data={
        "status": "fault"
    })
    response_data = {'msg': 'success', 'code': 200, 'data': ""}
    return jsonify(response_data)


@app.route('/proxy_report_success', methods=['GET'])
def proxy_report_success():
    """
    上报一个正常的代理心跳信息 直接通过端口
    上报成功次数
    """
    proxy_port = arg("proxy_port")
    current = MProxyQueue.first(condition={
        'port': int(proxy_port)
    })
    if current:
        success_num = 1
        if "success_num" in current:
            success_num = current['success_num'] + 1
        MProxyQueue.update_one(condition={
            'port': int(proxy_port)
        }, data={
            "success_num": success_num,
            "status": "running",
            "success_ts": utils.common.get_second_utime()
        })
        response_data = {'msg': 'success', 'code': 200, 'data': ""}
    else:
        response_data = {'msg': 'error', 'code': 2001, 'data': ""}
    return jsonify(response_data)


@app.route('/proxy_report_running', methods=['GET'])
def proxy_report_running():
    """
    上报running状态 直接通过端口
    只更新 running_ts
    """
    proxy_port = arg("proxy_port")
    MProxyQueue.update_one(condition={
        'port': int(proxy_port)
    }, data={
        "running_ts": utils.common.get_second_utime()
    })
    response_data = {'msg': 'success', 'code': 200, 'data': ""}
    return jsonify(response_data)

@app.route('/session_issue_test', methods=['GET'])
def session_issue_test():
    browser_port = arg("browser_port")
    hostname = arg("hostname")
    # 代理端口
    proxy_port = arg("proxy_port")
    data = MSession.lock_get_session_issue(browser_port, hostname, proxy_port)
    response_data = {'msg': 'success', 'code': 200, 'data': data}
    return jsonify(response_data)

@app.route('/session_issue', methods=['GET'])
def session_issue():
    """
    perplexity 无需批次batch
    """
    with lock:
        batch = "1"
        browser_port = arg("browser_port")
        hostname = arg("hostname")
        # 代理端口
        proxy_port = arg("proxy_port")
        init_day_count = 0

        log("/session_issue, batch: %s, browser_port:%s, hostname:%s" % (batch, browser_port, hostname), level=2, sub_path="%s_server_session_issue_log" % gptConf.log_file_path)

        # 参数校验
        if not browser_port or not hostname or not batch:
            response_data = {'msg': 'error params. miss browser_port or hostname', 'code': 2001, 'data': ""}
            return jsonify(response_data)

        batch = str(batch)
        browser_port = str(browser_port)
        hostname = str(hostname)

        # 按未进行任何分配
        # 这是时候无需判断 day_count 和 lock的限制
        condition = {
            "ask_last_time": {"$exists": False}
        }
        data_type=None
        res = MSession.find_one_and_update(condition=condition)
        print(condition)
        if res:
            data_type = "askLastTimeNotExists"
            log("/session_issue success, batch: %s, browser_port:%s, hostname:%s, by askLastTimeNotExists" % (batch, browser_port, hostname), level=2,
                sub_path="%s_server_session_issue_log" % gptConf.log_file_path)

        # 按 最远更新时间来获取 ask_last_time 并且该时间大于 24h。
        # 这是时候无需判断 day_count 和 lock的限制
        # 出现大于24h的需要将count重置为 1
        if not res:
            current_ts = utils.common.get_second_utime()-86400
            current_time_str = utils.common.formatTime(current_ts)
            condition = {
                "ask_last_time": {'$lte': current_time_str},
                "$or": [{"failed_num": {"$exists": False}},{"failed_num": {"$lte": 2}}]
            }
            print("conditon2", condition)
            reses = MSession.get(condition=condition, order_by={
                "ask_last_time": 1
            }, length=1)

            if reses:
                data_type = "askLastTimeLTE24hForCustom"
                log("/session_issue success, batch: %s, browser_port:%s, hostname:%s, by askLastTimeLTE24hForCustom" % (
                batch, browser_port, hostname), level=2,
                    sub_path="%s_server_session_issue_log" % gptConf.log_file_path)
                res = reses[0]
                print("---获取到了数据-初始化---")
                init_day_count = 1

        # 获取未上锁，次数不到100次，间隔 300s 的数据
        # 获取PRO
        if not res:
            current_ts = utils.common.get_second_utime() - 360
            current_time_str = utils.common.formatTime(current_ts)
            condition = {
                "ask_last_time": {'$lte': current_time_str},
                "day_count": {'$lt': gptConf.account_day_max_req_num_for_pro},
                "ask_lock": False,
                "account_type": "pro",
                "$or": [{"failed_num": {"$exists": False}}, {"failed_num": {"$lte": 2}}]
            }
            print("conditon3", condition)
            reses = MSession.get(condition=condition, order_by={
                "ask_last_time": 1
            }, length=1)

            if reses:
                data_type = "askLastTimeLTE300sForPro"
                log("/session_issue success, batch: %s, browser_port:%s, hostname:%s, by askLastTimeLTE300sForPro" % (
                    batch, browser_port, hostname), level=2,
                    sub_path="%s_server_session_issue_log" % gptConf.log_file_path)
                res = reses[0]

        # 已经上锁 ask_last_time 超过30分钟的, 并且次数没有超过 gptConf.account_day_max_req_num_for_pro
        # 这是时候无需判断lock的限制
        # 获取 PRO
        if not res:
            current_ts = utils.common.get_second_utime() - 1800
            current_time_str = utils.common.formatTime(current_ts)
            condition = {
                "ask_last_time": {'$lte': current_time_str},
                "day_count": {'$lt': gptConf.account_day_max_req_num_for_pro},
                "account_type": "pro",
                "$or": [{"failed_num": {"$exists": False}}, {"failed_num": {"$lte": 2}}]
            }
            print("conditon4", condition)
            reses = MSession.get(condition=condition, order_by={
                "ask_last_time": 1
            }, length=1)

            if reses:
                data_type = "askLastTime1800sForPRO"
                log("/session_issue success, batch: %s, browser_port:%s, hostname:%s, by askLastTime1800sForPRO" % (
                    batch, browser_port, hostname), level=2,
                    sub_path="%s_server_session_issue_log" % gptConf.log_file_path)
                res = reses[0]

        # 获取 custom
        if not res:
            current_ts = utils.common.get_second_utime() - 300
            current_time_str = utils.common.formatTime(current_ts)
            condition = {
                "ask_last_time": {'$lte': current_time_str},
                "day_count": {'$lt': gptConf.account_day_max_req_num_for_custom},
                "ask_lock": False,
                "account_type": "custom",
                "$or": [{"failed_num": {"$exists": False}}, {"failed_num": {"$lte": 2}}]
            }
            print(condition)
            print("conditon3-custom", condition)
            reses = MSession.get(condition=condition, order_by={
                "ask_last_time": 1
            }, length=1)

            if reses:
                data_type = "askLastTimeLTE300sForCustom"
                log("/session_issue success, batch: %s, browser_port:%s, hostname:%s, by askLastTimeLTE300sForCustom" % (
                    batch, browser_port, hostname), level=2,
                    sub_path="%s_server_session_issue_log" % gptConf.log_file_path)
                res = reses[0]

        # 获取 Custom
        if not res:
            current_ts = utils.common.get_second_utime() - 1800
            current_time_str = utils.common.formatTime(current_ts)
            condition = {
                "ask_last_time": {'$lte': current_time_str},
                "day_count": {'$lt': gptConf.account_day_max_req_num_for_custom},
                "account_type": "custom",
                "$or": [{"failed_num": {"$exists": False}}, {"failed_num": {"$lte": 2}}]
            }
            print("conditon4-custom", condition)
            reses = MSession.get(condition=condition, order_by={
                "ask_last_time": 1
            }, length=1)

            if reses:
                data_type = "askLastTime1800sForCustom"
                log("/session_issue success, batch: %s, browser_port:%s, hostname:%s, by askLastTime1800sForCustom" % (
                    batch, browser_port, hostname), level=2,
                    sub_path="%s_server_session_issue_log" % gptConf.log_file_path)
                res = reses[0]

        if not res:
            log("/session_issue failed, batch: %s, browser_port:%s, hostname:%s, not_enough_session_assign" % (
                batch, browser_port, hostname), level=2,
                sub_path="%s_server_session_issue_log" % gptConf.log_file_path)
            response_data = {'msg': 'Not enough session assign', 'code': 2002, 'data': {}}
            return jsonify(response_data)

        if not init_day_count:
            try:
                init_day_count = res['day_count']+1 if "day_count" in res else 1
            except:
                init_day_count = 1

        MSession.update_one(
            condition={
                "_id": res['_id']
            },
            data={
                "hostname": hostname,
                "browser_port": browser_port,
                "proxy_port": proxy_port,
                "batch": batch,
                "updated_at": utils.common.get_now_str(),
                "ask_last_time": utils.common.get_now_str(),
                "day_count": init_day_count,
                "ask_lock": True
            }
        )

        # 绑定了，但是没有 cookie_data_first
        res['_id'] = str(res['_id'])
        session_info = res['cookie_data_first']
        response_data = {'msg': 'success', 'code': 200, 'data': {
            "session": session_info,
            "hostname": hostname,
            "browser_port": browser_port,
            "batch": batch,
            "session_key": res['account'],
            "data_type": data_type,
            "ask_last_time": res['ask_last_time'] if "ask_last_time" in res else None,
            "account": res['account'],
        }}
        return jsonify(response_data)


@app.route('/session_issue_list', methods=['GET'])
def session_issue_list():
    """
    perplexity 无需批次batch
    """
    with lock:
        max_num = 5
        batch = "1"
        browser_port = arg("browser_port")
        hostname = arg("hostname")
        # 代理端口
        proxy_port = arg("proxy_port")
        init_day_count = 0

        log("/session_issue, batch: %s, browser_port:%s, hostname:%s" % (batch, browser_port, hostname), level=2, sub_path="%s_server_session_issue_log" % gptConf.log_file_path)

        # 参数校验
        if not browser_port or not hostname or not batch:
            response_data = {'msg': 'error params. miss browser_port or hostname', 'code': 2001, 'data': ""}
            return jsonify(response_data)

        batch = str(batch)
        browser_port = str(browser_port)
        hostname = str(hostname)

        # 按未进行任何分配
        # 这是时候无需判断 day_count 和 lock的限制
        condition = {
            "ask_last_time": {"$exists": False}
        }
        data_type=None
        result = MSession.get(condition=condition, length = max_num)
        print(condition)
        if result:
            data_type = "askLastTimeNotExists"
            log("/session_issue success, batch: %s, browser_port:%s, hostname:%s, by askLastTimeNotExists" % (batch, browser_port, hostname), level=2,
                sub_path="%s_server_session_issue_log" % gptConf.log_file_path)

        # 按 最远更新时间来获取 ask_last_time 并且该时间大于 24h。
        # 这是时候无需判断 day_count 和 lock的限制
        # 出现大于24h的需要将count重置为 1
        if not result:
            current_ts = utils.common.get_second_utime()-86400
            current_time_str = utils.common.formatTime(current_ts)
            condition = {
                "ask_last_time": {'$lte': current_time_str},
                "$or": [{"failed_num": {"$exists": False}},{"failed_num": {"$lte": 2}}]
            }
            print("conditon2", condition)
            result = MSession.get(condition=condition, order_by={
                "ask_last_time": 1
            }, length = max_num)

            if result:
                data_type = "askLastTimeLTE24hForCustom"
                log("/session_issue success, batch: %s, browser_port:%s, hostname:%s, by askLastTimeLTE24hForCustom" % (
                batch, browser_port, hostname), level=2,
                    sub_path="%s_server_session_issue_log" % gptConf.log_file_path)
                print("---获取到了数据-初始化---")
                init_day_count = 1

        # 获取未上锁，次数不到100次，间隔 300s 的数据
        # 获取PRO
        if not result:
            current_ts = utils.common.get_second_utime() - 360
            current_time_str = utils.common.formatTime(current_ts)
            condition = {
                "ask_last_time": {'$lte': current_time_str},
                "day_count": {'$lt': gptConf.account_day_max_req_num_for_pro},
                "ask_lock": False,
                "account_type": "pro",
                "$or": [{"failed_num": {"$exists": False}}, {"failed_num": {"$lte": 2}}]
            }
            print("conditon3", condition)
            result = MSession.get(condition=condition, order_by={
                "ask_last_time": 1
            }, length = max_num)

            if result:
                data_type = "askLastTimeLTE300sForPro"
                log("/session_issue success, batch: %s, browser_port:%s, hostname:%s, by askLastTimeLTE300sForPro" % (
                    batch, browser_port, hostname), level=2,
                    sub_path="%s_server_session_issue_log" % gptConf.log_file_path)

        # 已经上锁 ask_last_time 超过30分钟的, 并且次数没有超过 gptConf.account_day_max_req_num_for_pro
        # 这是时候无需判断lock的限制
        # 获取 PRO
        if not result:
            current_ts = utils.common.get_second_utime() - 1800
            current_time_str = utils.common.formatTime(current_ts)
            condition = {
                "ask_last_time": {'$lte': current_time_str},
                "day_count": {'$lt': gptConf.account_day_max_req_num_for_pro},
                "account_type": "pro",
                "$or": [{"failed_num": {"$exists": False}}, {"failed_num": {"$lte": 2}}]
            }
            print("conditon4", condition)
            result = MSession.get(condition=condition, order_by={
                "ask_last_time": 1
            }, length = max_num)

            if result:
                data_type = "askLastTime1800sForPRO"
                log("/session_issue success, batch: %s, browser_port:%s, hostname:%s, by askLastTime1800sForPRO" % (
                    batch, browser_port, hostname), level=2,
                    sub_path="%s_server_session_issue_log" % gptConf.log_file_path)

        # 获取 custom
        if not result:
            current_ts = utils.common.get_second_utime() - 300
            current_time_str = utils.common.formatTime(current_ts)
            condition = {
                "ask_last_time": {'$lte': current_time_str},
                "day_count": {'$lt': gptConf.account_day_max_req_num_for_custom},
                "ask_lock": False,
                "account_type": "custom",
                "$or": [{"failed_num": {"$exists": False}}, {"failed_num": {"$lte": 2}}]
            }
            print(condition)
            print("conditon3-custom", condition)
            result = MSession.get(condition=condition, order_by={
                "ask_last_time": 1
            }, length = max_num)

            if result:
                data_type = "askLastTimeLTE300sForCustom"
                log("/session_issue success, batch: %s, browser_port:%s, hostname:%s, by askLastTimeLTE300sForCustom" % (
                    batch, browser_port, hostname), level=2,
                    sub_path="%s_server_session_issue_log" % gptConf.log_file_path)

        # 获取 Custom
        if not result:
            current_ts = utils.common.get_second_utime() - 1800
            current_time_str = utils.common.formatTime(current_ts)
            condition = {
                "ask_last_time": {'$lte': current_time_str},
                "day_count": {'$lt': gptConf.account_day_max_req_num_for_custom},
                "account_type": "custom",
                "$or": [{"failed_num": {"$exists": False}}, {"failed_num": {"$lte": 2}}]
            }
            print("conditon4-custom", condition)
            result = MSession.get(condition=condition, order_by={
                "ask_last_time": 1
            }, length = max_num)

            if result:
                data_type = "askLastTime1800sForCustom"
                log("/session_issue success, batch: %s, browser_port:%s, hostname:%s, by askLastTime1800sForCustom" % (
                    batch, browser_port, hostname), level=2,
                    sub_path="%s_server_session_issue_log" % gptConf.log_file_path)

        if not result:
            log("/session_issue failed, batch: %s, browser_port:%s, hostname:%s, not_enough_session_assign" % (
                batch, browser_port, hostname), level=2,
                sub_path="%s_server_session_issue_log" % gptConf.log_file_path)
            response_data = {'msg': 'Not enough session assign', 'code': 2002, 'data': {}}
            return jsonify(response_data)

        res_data = []

        for res in result:
            if not init_day_count:
                try:
                    init_day_count = res['day_count']+1 if "day_count" in res else 1
                except:
                    init_day_count = 1

            # todo 上线打开

            # MSession.update_one(
            #     condition={
            #         "_id": res['_id']
            #     },
            #     data={
            #         "hostname": hostname,
            #         "browser_port": browser_port,
            #         "proxy_port": proxy_port,
            #         "batch": batch,
            #         "updated_at": utils.common.get_now_str(),
            #         "ask_last_time": utils.common.get_now_str(),
            #         "day_count": init_day_count,
            #         "ask_lock": True
            #     }
            # )

            # 绑定了，但是没有 cookie_data_first
            res['_id'] = str(res['_id'])
            session_info = res['cookie_data_first']
            res_data.append({
                "session": session_info,
                "hostname": hostname,
                "browser_port": browser_port,
                "batch": batch,
                "session_key": res['account'],
                "data_type": data_type,
                "ask_last_time": res['ask_last_time'] if "ask_last_time" in res else None,
                "account": res['account'],
            })

        response_data = {'msg': 'success', 'code': 200, 'data': res_data}
        return jsonify(response_data)

@app.route('/session_issue_by_account', methods=['GET'])
def session_issue_by_account():
    """
    出队列的时候，需要直接获取账号来登录
    该账号只用来登录，不需要更新任何数据
    """

    with lock:
        # batch = "1"
        # browser_port = arg("browser_port")
        # hostname = arg("hostname")
        account = arg("account")
        # 代理端口
        # proxy_port = arg("proxy_port")

        # 参数校验
        if not account:
            response_data = {'msg': 'error params. miss account', 'code': 2001, 'data': ""}
            return jsonify(response_data)

        account = str(account)

        # 按未进行任何分配
        # 这是时候无需判断 day_count 和 lock的限制
        condition = {
            "account": account
        }
        res = MSession.first(condition=condition)

        if not res:
            response_data = {'msg': 'not find account: %s' % account, 'code': 2002, 'data': ""}
            return jsonify(response_data)

        # 绑定了，但是没有 cookie_data_first
        res['_id'] = str(res['_id'])
        session_info = res['cookie_data_first']
        response_data = {'msg': 'success', 'code': 200, 'data': {
            "session": session_info,
            "session_key": res['account']
        }}
        return jsonify(response_data)




@app.route('/session_report_success', methods=['GET', 'POST'])
def session_report_success():
    """
    每次请求成功，上报一次最新的 账号认证信息
    batch = 1
    """
    batch = "1"
    browser_port = str(arg("browser_port"))
    hostname = str(arg("hostname"))

    session_key = arg("session_key")
    session_token = arg("session_token")

    cookie_session = {
        "__Secure-next-auth.session-token": session_token
    }
    condition = {
        "account": str(session_key)
    }
    ret = MSession.update_one(
        condition=condition,
        data={
            "updated_at": utils.common.get_now_str(),
            "cookie_data_last": cookie_session,
            "ask_lock": False,
            "ask_last_time": utils.common.get_now_str(),
            "browser_port": browser_port,
            "hostname": hostname
        }
    )

    response_data = {'msg': 'success', 'code': 200, 'data': {
        "localstorage_data_last": cookie_session,
        "condition": condition
    }}

    return jsonify(response_data)



def start():
    # 检测本程序正在运行，则退出
    print("address: 127.0.0.1:8053")
    app.run(
        host="0.0.0.0",
        port=8053,
        debug=gptConf.debug
    )

# if __name__ == '__main__':
#     start()
