"""
将 产出表的索引同步到其他产出表

适用于details 批量表管理

"""

import json
from pymongo import MongoClient

# 连接 MongoDB
client = MongoClient("mongodb://192.168.0.123:27017")  # 根据你的实际地址修改
db = client["smolecule"]  # 替换为你的数据库名
# 参考，采集的数据集合
origin_collection = db["product_ast_bench_outline"]  # 替换为你的集合名



# 将索引转换为 JSON 可序列化格式（处理 BSON 类型）
def export_index():
    indexes = list(origin_collection.list_indexes())

    # 将索引转换为 JSON 可序列化格式（处理 BSON 类型）
    def convert_bson(obj):
        if isinstance(obj, dict):
            return {k: convert_bson(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_bson(i) for i in obj]
        elif hasattr(obj, 'to_dict'):  # bson.son.SON
            return obj.to_dict()
        else:
            return obj
    return convert_bson(indexes)

indexs = [
    {
        "v": 2,
        "unique": True,
        "key": {
            "bid": 1
        },
        "name": "bid_1"
    },
    {
        "v": 2,
        "key": {
            "created_at": -1
        },
        "name": "created_at_-1"
    },
    {
        "v": 2,
        "key": {
            "hostname": 1
        },
        "name": "hostname_1"
    },
    {
        "v": 2,
        "key": {
            "browser_port": 1
        },
        "name": "browser_port_1"
    },
    {
        "v": 2,
        "key": {
            "hostname": 1,
            "browser_port": 1
        },
        "name": "hostname_1_browser_port_1"
    },
    {
        "v": 2,
        "key": {
            "status": 1
        },
        "name": "status_1"
    },
    {
        "v": 2,
        "key": {
            "link_processing": 1,
            "status": 1
        },
        "name": "link_processing_1_status_1"
    },
    {
        "v": 2,
        "key": {
            "account": 1
        },
        "name": "account_1"
    },
    {
        "v": 2,
        "key": {
            "std_status": 1
        },
        "name": "std_status_1"
    },
    {
        "v": 2,
        "key": {
            "time": 1,
            "std_version": 1
        },
        "name": "time_1_std_version_1"
    },
    {
        "v": 2,
        "key": {
            "hostname": 1,
            "created_at": 1
        },
        "name": "hostname_1_created_at_1"
    },
    {
        "v": 2,
        "key": {
            "std_version": 1
        },
        "name": "std_version_1"
    },
    {
        "v": 2,
        "key": {
            "std_status": 1,
            "created_at": -1
        },
        "name": "std_status_1_created_at_-1"
    },
    {
        "v": 2,
        "key": {
            "proxy_port": 1,
            "created_at": 1
        },
        "name": "proxy_port_1_created_at_1"
    },
    {
        "v": 2,
        "key": {
            "is_complete": 1
        },
        "name": "is_complete_1"
    },
    {
        "v": 2,
        "key": {
            "bid": 1,
            "product_name_len": 1
        },
        "name": "bid_1_product_name_len_1"
    }
]

for idx in range(43):
    # if idx < 35:
    #     continue

    dbname = f"product_ast_bench_outline_detail_{idx}"
    print(f"开始执行表{dbname}")
    target = db[dbname]
    for index in indexs:
        key_list = list(index["key"].items())  # 转换为 [('bid', 1)] 的格式
        target.create_index(
            key_list,
            name=index["name"],
            unique=index.get("unique", False)
        )
    print(f"表{dbname}索引创建完成")