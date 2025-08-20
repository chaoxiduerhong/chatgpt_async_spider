"""
更新浏览器账号数据： -1的未未绑定
有端口的则认为绑定成功，并且登录成功的


"""

data = [
]

# 每次新增替换上面的数据（来自于飞书文档：）
# https://svv17uppgnx.feishu.cn/wiki/P7Vewa9Lwi5Fv8k2tk3cKDwQnz2?sheet=oxcnda

from pymongo import MongoClient
import hashlib


# 1. 连接 MongoDB
client = MongoClient("mongodb://192.168.0.123:27017")
db = client["smolecule"]
collection = db["ast_browser_auth_data"]

# 2. 更新数据
for item in data:
    if item['browser_port'] > 0:
        print(item['browser_port'])
        collection.update_one({
            "email": item['email'],
        }, {
            "$set": {
                "login_status": "success",
                "browser_port": item['browser_port'],
            }
        })
    else:
        collection.update_one({
            "email": item['email'],
        }, {
            "$set": {
                "login_status": "invalid",
                "browser_port": -1,
            }
        })