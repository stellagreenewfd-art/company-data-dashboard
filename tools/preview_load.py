# -*- coding: utf-8 -*-
"""构建本地预览库：用 13 份真实文件灌入 data/preview.db（幂等，可重复跑）。"""
import sys, io, os, shutil
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

os.environ["DB_PATH"] = os.path.join(BASE, "data", "preview.db")
import app as A

class FakeFile:
    def __init__(self, path):
        self.filename = os.path.basename(path)
        self.path = path
    def save(self, dst):
        shutil.copy(self.path, dst)

FILES = [
    (r"C:\Users\R17\Downloads\太极武当金-自营-交易概况_不包括对比时间_离线_分天下载_2026-08-01_2026-08-31.xlsx", "京东", "奶粉"),
    (r"C:\Users\R17\Downloads\武当pop-交易概况__分天下载_2026-08-01_2026-08-31.xlsx", "京东", "奶粉"),
    (r"C:\Users\R17\Downloads\太极武当金顶自营--推广_报表中心_账户_30天_点击_不含赠品_成交订单_20260801_20260831.xlsx", "京东", "奶粉"),
    (r"C:\Users\R17\Downloads\营销场景报表_20260831_104334(1).csv", "天猫", "鸡蛋"),
    (r"C:\Users\R17\Downloads\8月红书鸡蛋销售数据表.xlsx", "小红书", "鸡蛋"),
    (r"C:\Users\R17\Downloads\抖音8月鸡蛋销售数据表.xlsx", "抖音", "鸡蛋"),
    (r"C:\Users\R17\Downloads\天猫鸡蛋订单.xlsx", "天猫", "鸡蛋"),
    (r"C:\Users\R17\Downloads\天猫订单.xlsx", "天猫", "鸡蛋"),
    (r"C:\Users\R17\Downloads\拼多多奶粉推广.xlsx", "拼多多", "奶粉"),
    (r"C:\Users\R17\Downloads\拼多多奶粉订单.csv", "拼多多", "奶粉"),
    (r"C:\Users\R17\Downloads\拼多多鸡蛋商品推广__20260801至20260831.xlsx", "拼多多", "鸡蛋"),
    (r"C:\Users\R17\Downloads\拼多多鸡蛋订单明细-2026.8.1-8.31.xlsx", "拼多多", "鸡蛋"),
    (r"C:\Users\R17\Downloads\营销场景报表_20260831_104334.csv", "天猫", "鸡蛋"),
]

conn = A.get_db()
ok = fail = 0
for path, plat, cat in FILES:
    res = A.process_upload(FakeFile(path), plat, cat, "", conn, user_id=1)
    if res.get("ok"):
        ok += 1
    else:
        fail += 1
        print("FAIL:", os.path.basename(path), res.get("error"))
conn.close()
print(f"preview.db loaded: ok={ok} fail={fail}")
