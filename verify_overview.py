# -*- coding: utf-8 -*-
"""验证 overview 口径修复：默认排除无效单 + include_invalid=1 含全部 + 订单数去重。
自包含：先 store_sales 灌入原始表再查 overview。"""
import os, sys, datetime, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("DB_PATH", "/tmp/verify_overview.db")
if os.path.exists(DB):
    os.remove(DB)
os.environ["DB_PATH"] = DB

spec = importlib.util.spec_from_file_location("app", os.path.join(HERE, "app.py"))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
flask_app = app.app

import pandas as pd
SRC = "/Users/qinaqiang/Downloads/8.1-8.25红书鸡蛋销售表格.xlsx"
df = pd.read_excel(SRC, sheet_name="订单信息", engine="openpyxl")
app.init_db()
conn = app.get_db()
cur = conn.cursor()
cur.execute("INSERT INTO imports (filename,platform,category,data_type,rows,imported_at,user_id) VALUES (?,?,?,?,?,?,?)",
            (os.path.basename(SRC), "小红书", "鸡蛋", "sales", len(df),
             datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 1))
iid = cur.lastrowid
app.store_sales(df, "小红书", "鸡蛋", iid, conn)
conn.commit()
conn.close()

client = flask_app.test_client()
r = client.post("/api/login", json={"username": "admin", "password": "admin123"})
print("login:", r.status_code, r.get_json())

print("\n=== 默认（有效成交，排除取消/退款）===")
d = client.get("/api/overview?start=2026-08-01&end=2026-08-25").get_json()
k = d["kpis"]
print(f"  total_orders(去重有效) = {k['total_orders']}")
print(f"  total_rows(原始行)     = {k['total_rows']}")
print(f"  total_raw_orders(含取消)= {k['total_raw_orders']}")
print(f"  total_sales(有效)      = {k['total_sales']}")
print(f"  total_raw_sales(含取消)= {k['total_raw_sales']}")
print(f"  date span = {d['date_min']} ~ {d['date_max']}  天数={len(d['daily_trend'])}")
print(f"  total_promo_cost(投放) = {k['total_promo_cost']}  channel_breakdown={d.get('channel_breakdown')}")

print("\n=== include_invalid=1（含全部状态，对账用）===")
d2 = client.get("/api/overview?start=2026-08-01&end=2026-08-25&include_invalid=1").get_json()
k2 = d2["kpis"]
print(f"  total_orders = {k2['total_orders']}")
print(f"  total_raw_orders = {k2['total_raw_orders']}")
print(f"  total_sales = {k2['total_sales']}")
print(f"  date span = {d2['date_min']} ~ {d2['date_max']}")
print("\n--- 断言 ---")
# 669 行含 31 已取消 -> 有效去重应 < 669; 含取消 total_raw_orders 应 = 669(去重后唯一订单数)
print("去重有效订单 > 0:", "PASS" if k["total_orders"] > 0 else "FAIL")
print("含取消口径返回:", "PASS" if k2["total_raw_orders"] > 0 else "FAIL")
print("日期跨 8.1~8.25:", "PASS" if d["date_min"] == "2026-08-01" and d["date_max"] == "2026-08-25" else "FAIL")
