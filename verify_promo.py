"""受控复现两个前端可见 bug 并验证修复：
  B1. KPI 汇总(总推广花费)看不到投放数据，但 商品推广效果 TOP 榜(明细)有
      -> 根因：product_stats 的 period 为空(46列文件名无日期)时, overview 直接 skip, 但 TOP 榜直接读表
  B2. TOP 榜第一个商品名称为空白
      -> 根因：/api/products 按 product_name GROUP BY 无空名过滤; 且 store_promo_product 不认「规格名称」列
模拟：46 列衍生表(含 规格名称 + 成交花费/交易额/曝光/点击), 文件名无日期 -> period=''
"""
import os, sys, json, datetime, importlib.util
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB = os.environ.get("DB_PATH", "/tmp/repro_promo.db")
if os.path.exists(DB):
    os.remove(DB)
os.environ["DB_PATH"] = DB

spec = importlib.util.spec_from_file_location("app", os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py"))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
app.get_current_user = lambda: {"id": 1, "username": "test", "role": "admin"}
app.app.secret_key = "test"

import pandas as pd
app.init_db()
conn = app.get_db()
cur = conn.cursor()
cur.execute("INSERT INTO imports (filename,platform,category,data_type,rows,imported_at,user_id) VALUES (?,?,?,?,?,?,?)",
            ("红书8月_46列_完全填充测试版.xlsx", "小红书", "鸡蛋", "promo_product", 4,
             datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 1))
iid = cur.lastrowid

# 模拟 46 列衍生表：用「规格名称」作商品名(系统旧候选不认); 含空名行(模拟 B2)
df = pd.DataFrame([
    {"规格名称": "可生食鸡蛋30枚装", "成交花费(元)": 100.0, "交易额(元)": 800.0, "实际投产比": 8.0, "曝光量": 5000, "点击量": 300},
    {"规格名称": "叶黄素鸡蛋20枚",   "成交花费(元)": 60.0,  "交易额(元)": 500.0, "实际投产比": 8.3, "曝光量": 3000, "点击量": 200},
    {"规格名称": "",                "成交花费(元)": 40.0,  "交易额(元)": 400.0, "实际投产比": 10.0,"曝光量": 2000, "点击量": 150},  # 空名行
    {"规格名称": "可生食鸡蛋30枚装", "成交花费(元)": 20.0,  "交易额(元)": 200.0, "实际投产比": 10.0,"曝光量": 1000, "点击量": 80},
])
res = app.store_promo_product(df, "小红书", "鸡蛋", iid, "", conn)  # period='' 模拟无日期文件名
conn.commit()
print("=== store_promo_product (period='') ===")
print("  入库行数:", res["rows"], " 字段识别:", {k: bool(v) for k, v in res["fields"].items()})
ps = conn.execute("SELECT product_id, product_name, promo_cost, promo_sales FROM product_stats").fetchall()
print("  product_stats 实际数据:")
for r in ps:
    print(f"    id={r['product_id']!r:14} name={r['product_name']!r:16} cost={r['promo_cost']} sales={r['promo_sales']}")

# B1: overview KPI 是否反映 product_stats(period 缺失场景)
with app.app.test_client() as client:
    ov = client.get("/api/overview?start=2026-08-01&end=2026-08-31").get_json()
    k = ov["kpis"]
    print("\n=== overview KPI (含 period 缺失的推广数据) ===")
    print(f"  总推广花费 total_promo_cost = {k['total_promo_cost']}")
    print(f"  推广成交额 total_promo_sales = {k['total_promo_sales']}")
    print(f"  整体ROI overall_roi = {k['overall_roi']}")
    # B2: TOP 榜第一个商品名
    pr = client.get("/api/products?limit=15").get_json()
    print("\n=== /api/products TOP 榜 ===")
    for i, r in enumerate(pr):
        print(f"  [{i}] {r['product_name']!r}  sales={r['promo_sales']}")
    print("\n--- 断言 ---")
    print("B1 修复:", "PASS" if k["total_promo_cost"] > 0 else "FAIL (仍为0)")
    print("B2 修复:", "PASS" if pr and pr[0]["product_name"] not in (None, "", "-") else "FAIL (首行空名)")
    # 验证空名行未进入 TOP 榜
    has_blank = any((r["product_name"] in (None, "", "-")) for r in pr)
    print("B2 无空名泄漏:", "PASS" if not has_blank else "FAIL")
conn.close()
print("\nDONE", DB)
