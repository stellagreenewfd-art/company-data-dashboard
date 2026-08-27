# -*- coding: utf-8 -*-
"""验证 overview 口径修复：默认排除无效单 + include_invalid=1 含全部 + 订单数去重。"""
import os, importlib.util
DB = os.environ.get("DB_PATH", "/tmp/verify_after.db")
os.environ["DB_PATH"] = DB
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("app", os.path.join(HERE, "app.py"))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
flask_app = app.app  # app.py 内的 Flask 实例
client = flask_app.test_client()

r = client.post("/api/login", json={"username": "admin", "password": "admin123"})
print("login:", r.status_code, r.get_json())

print("\n=== 默认（有效成交，排除取消/退款）===")
d = client.get("/api/overview").get_json()
k = d["kpis"]
print(f"  total_orders(去重有效) = {k['total_orders']}")
print(f"  total_rows(原始行)     = {k['total_rows']}")
print(f"  total_raw_orders(含取消)= {k['total_raw_orders']}")
print(f"  total_sales(有效)      = {k['total_sales']}")
print(f"  total_raw_sales(含取消)= {k['total_raw_sales']}")
print(f"  date span = {d['date_min']} ~ {d['date_max']}  天数={len(d['daily_trend'])}")

print("\n=== include_invalid=1（含全部状态，对账用）===")
d2 = client.get("/api/overview?include_invalid=1").get_json()
k2 = d2["kpis"]
print(f"  total_orders = {k2['total_orders']}")
print(f"  total_raw_orders = {k2['total_raw_orders']}")
print(f"  total_sales = {k2['total_sales']}")
print(f"  date span = {d2['date_min']} ~ {d2['date_max']}  天数={len(d2['daily_trend'])}")
