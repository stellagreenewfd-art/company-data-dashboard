# -*- coding: utf-8 -*-
"""用 13 份真实文件验证新管线：逐份 process_upload 落库 + overview 抽查。"""
import sys, io, os, shutil, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

tmpdb = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["DB_PATH"] = tmpdb
import app as A

class FakeFile:
    def __init__(self, path):
        self.filename = os.path.basename(path)
        self.path = path
    def save(self, dst):
        shutil.copy(self.path, dst)

FILES = [
    # (路径, 平台覆盖, 品类覆盖, 店铺覆盖)——模拟运营上传时的手动选择
    (r"C:\Users\R17\Downloads\太极武当金-自营-交易概况_不包括对比时间_离线_分天下载_2026-08-01_2026-08-31.xlsx", "京东", "奶粉", ""),
    (r"C:\Users\R17\Downloads\武当pop-交易概况__分天下载_2026-08-01_2026-08-31.xlsx", "京东", "奶粉", ""),
    (r"C:\Users\R17\Downloads\太极武当金顶自营--推广_报表中心_账户_30天_点击_不含赠品_成交订单_20260801_20260831.xlsx", "京东", "奶粉", ""),
    (r"C:\Users\R17\Downloads\营销场景报表_20260831_104334(1).csv", "天猫", "鸡蛋", ""),
    (r"C:\Users\R17\Downloads\8月红书鸡蛋销售数据表.xlsx", "小红书", "鸡蛋", ""),
    (r"C:\Users\R17\Downloads\抖音8月鸡蛋销售数据表.xlsx", "抖音", "鸡蛋", ""),
    (r"C:\Users\R17\Downloads\天猫鸡蛋订单.xlsx", "天猫", "鸡蛋", ""),
    (r"C:\Users\R17\Downloads\天猫订单.xlsx", "天猫", "鸡蛋", ""),
    (r"C:\Users\R17\Downloads\拼多多奶粉推广.xlsx", "拼多多", "奶粉", ""),
    (r"C:\Users\R17\Downloads\拼多多奶粉订单.csv", "拼多多", "奶粉", ""),
    (r"C:\Users\R17\Downloads\拼多多鸡蛋商品推广__20260801至20260831.xlsx", "拼多多", "鸡蛋", ""),
    (r"C:\Users\R17\Downloads\拼多多鸡蛋订单明细-2026.8.1-8.31.xlsx", "拼多多", "鸡蛋", ""),
    (r"C:\Users\R17\Downloads\营销场景报表_20260831_104334.csv", "天猫", "鸡蛋", ""),
]

conn = A.get_db()
print("=" * 96)
for path, plat, cat, shop in FILES:
    res = A.process_upload(FakeFile(path), plat, cat, "", conn, user_id=1, shop_override=shop)
    if res.get("ok"):
        sheets = " | ".join(f"{s['sheet']}:{s['data_type']}:{s['rows']}" for s in res.get("sheets", []))
        print(f"OK  {res['filename'][:38]:38s} -> {res['platform']}/{res['shop'] or '-'}/{res['category']} "
              f"rows={res['rows']:4d}  {res['date_min']}~{res['date_max']}")
        print(f"    sheets: {sheets}")
        if res.get("missing_fields"):
            print(f"    missing: {res['missing_fields']}")
    else:
        print(f"FAIL {os.path.basename(path)[:40]:40s} -> {res.get('error')}")

print("=" * 96)
c = conn.cursor()
for t in ("orders", "daily_metrics", "product_stats"):
    print(t, c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
print("-- daily_metrics by type --")
for r in c.execute("SELECT metric_type, platform, shop, category, COUNT(*), MIN(data_date), MAX(data_date) FROM daily_metrics GROUP BY metric_type, platform, shop, category"):
    print(tuple(r))
print("-- scene check (天猫 promo) --")
for r in c.execute("SELECT data_date, scene, promo_cost, promo_sales FROM daily_metrics WHERE metric_type='promo' AND platform='天猫' ORDER BY data_date LIMIT 8"):
    print(tuple(r))
print("-- orders by platform (抖音日期/金额抽查) --")
for r in c.execute("SELECT platform, COUNT(*), MIN(order_date), MAX(order_date), ROUND(SUM(pay_amount),2) FROM orders GROUP BY platform"):
    print(tuple(r))
print("-- 抖音样本 --")
for r in c.execute("SELECT order_id, order_date, pay_amount, status FROM orders WHERE platform='抖音' LIMIT 3"):
    print(tuple(r))
conn.close()
os.unlink(tmpdb)
