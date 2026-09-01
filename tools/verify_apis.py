# -*- coding: utf-8 -*-
"""端到端验证看板 API：overview / coverage / influencers / dimensions。"""
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
    (r"C:\Users\R17\Downloads\太极武当金-自营-交易概况_不包括对比时间_离线_分天下载_2026-08-01_2026-08-31.xlsx", "京东", "奶粉"),
    (r"C:\Users\R17\Downloads\武当pop-交易概况__分天下载_2026-08-01_2026-08-31.xlsx", "京东", "奶粉"),
    (r"C:\Users\R17\Downloads\太极武当金顶自营--推广_报表中心_账户_30天_点击_不含赠品_成交订单_20260801_20260831.xlsx", "京东", "奶粉"),
    (r"C:\Users\R17\Downloads\营销场景报表_20260831_104334(1).csv", "天猫", "鸡蛋"),
    (r"C:\Users\R17\Downloads\8月红书鸡蛋销售数据表.xlsx", "小红书", "鸡蛋"),
    (r"C:\Users\R17\Downloads\抖音8月鸡蛋销售数据表.xlsx", "抖音", "鸡蛋"),
    (r"C:\Users\R17\Downloads\天猫鸡蛋订单.xlsx", "天猫", "鸡蛋"),
    (r"C:\Users\R17\Downloads\拼多多奶粉推广.xlsx", "拼多多", "奶粉"),
    (r"C:\Users\R17\Downloads\拼多多奶粉订单.csv", "拼多多", "奶粉"),
    (r"C:\Users\R17\Downloads\拼多多鸡蛋商品推广__20260801至20260831.xlsx", "拼多多", "鸡蛋"),
    (r"C:\Users\R17\Downloads\拼多多鸡蛋订单明细-2026.8.1-8.31.xlsx", "拼多多", "鸡蛋"),
]
conn = A.get_db()
for path, plat, cat in FILES:
    A.process_upload(FakeFile(path), plat, cat, "", conn, user_id=1)
conn.close()

client = A.app.test_client()
r = client.post("/api/login", json={"username": "yjdata2026", "password": "yj2026"})
assert r.get_json().get("ok"), r.get_json()

r = client.get("/api/overview?start=2026-08-01&end=2026-08-31")
d = r.get_json()
assert "kpis" in d, d
k = d["kpis"]
print("== KPI ==")
for kk in ("total_sales", "net_sales", "total_orders", "avg_aov", "total_promo_cost",
           "total_promo_sales", "overall_roi", "ad_cost_ratio", "refund_rate",
           "sales_pop", "prev_range", "trade_gmv_filled"):
    print(f"  {kk}: {k.get(kk)}")
print("== platform_breakdown ==")
for x in d["platform_breakdown"]: print(" ", x)
print("== scene_breakdown (top5) ==")
for x in d["scene_breakdown"][:5]: print(" ", x)
print("== shop_breakdown ==")
for x in d["shop_breakdown"]: print(" ", x)
print("== matrix (top6) ==")
for x in d["matrix"][:6]: print(" ", x)
print("== daily_trend 样例(3天) ==")
for x in d["daily_trend"][-3:]: print(" ", x)

r = client.get("/api/coverage?days=14")
cov = r.get_json()
print("== coverage ==", cov["start"], "~", cov["end"])
for row in cov["rows"][:6]:
    marks = " ".join(f"{x['date'][-2:]}:{x['mark']}" for x in row["days"][-7:])
    print(f"  {row['platform']}/{row['category']} 缺{row['missing_days']}天 | {marks}")

r = client.get("/api/influencers?limit=5")
print("== influencers ==")
for x in r.get_json(): print(" ", x)

r = client.get("/api/dimensions")
print("== dimensions ==", r.get_json())
os.unlink(tmpdb)
print("ALL_API_OK")
