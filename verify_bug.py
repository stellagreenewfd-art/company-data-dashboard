# -*- coding: utf-8 -*-
"""用真实原始表验证看板入库逻辑：改前/改后对比。
注意：checks 里的候选必须与 app.py store_sales() 内部的 find_col 候选保持一致，
否则测的是"理想候选"而非"代码真实行为"。
  DB_PATH=/tmp/verify_before.db python3 verify_bug.py   # 改前（当前代码）
  DB_PATH=/tmp/verify_after.db  python3 verify_bug.py   # 改后（patch 已应用）
"""
import os, importlib.util, datetime
import pandas as pd

DB = os.environ.get("DB_PATH", "/tmp/verify.db")
os.environ["DB_PATH"] = DB
if os.path.exists(DB):
    os.remove(DB)

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("app", os.path.join(HERE, "app.py"))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
app.init_db()

SRC = "/Users/qinaqiang/Downloads/8.1-8.25红书鸡蛋销售表格.xlsx"
df = pd.read_excel(SRC, sheet_name="订单信息", engine="openpyxl")
cols = list(df.columns)
print("=== 原始表真实列名 ===")
print(cols)

# —— 以下候选须与 app.store_sales() 内部保持一致（patch 后版本）——
REAL_CANDIDATES = {
    "oid(订单号)": ["订单号", "订单编号", "主订单编号", "订单ID", "订单", "交易编号", "TradeNo"],
    "pay(金额)": ["商家实收金额(元)", "商家实收金额", "商家应收金额(元)(支付金额)", "商家应收金额",
                  "用户实付金额(元)", "买家实付金额", "用户实付金额", "买家应付货款",
                  "商品总价(元)", "总金额", "支付金额", "实付金额"],
    "date(日期)": ["订单成交时间", "订单付款时间", "支付时间", "下单时间", "成交时间", "订单创建时间", "日期"],
    "status(状态)": ["订单状态", "售后状态", "状态"],
    "refund(退款)": ["退款金额"],
    "prod(商品)": ["商品标题", "商品名称", "SKU名称", "选购商品", "商品", "标题"],
    "infid(达人ID)": ["达人ID", "达人id", "达人编号", "主播ID"],
    "infl(达人名)": ["达人名称", "达人", "达人昵称", "主播", "博主"],
}
print("\n=== store_sales 真实候选下的 find_col 匹配（决定能不能取到值）===")
for k, cands in REAL_CANDIDATES.items():
    print(f"  {k} -> {app.find_col(cols, cands)}")

conn = app.get_db()
cur = conn.cursor()
cur.execute(
    "INSERT INTO imports (filename,platform,category,data_type,rows,imported_at,user_id) VALUES (?,?,?,?,?,?,?)",
    (os.path.basename(SRC), "小红书", "鸡蛋", "sales", len(df),
     datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 1))
iid = cur.lastrowid
res = app.store_sales(df, "小红书", "鸡蛋", iid, conn)
conn.commit()
n = res["rows"]
fields = res["fields"]

row = conn.execute(
    "SELECT COUNT(*), COALESCE(SUM(pay_amount),0), "
    "SUM(CASE WHEN pay_amount IS NULL THEN 1 ELSE 0 END) "
    "FROM orders WHERE import_id=?", (iid,)).fetchone()
print(f"\n=== store_sales 端到端结果（这就是用户上传原始表时系统的真实行为）===")
print(f"  函数返回入库行数 n = {n}")
print(f"  DB 实际行数 = {row[0]}  金额合计 = {round(row[1],2)}  NULL金额行数 = {row[2]}")
print("  关键字段识别情况:")
for k, v in fields.items():
    print(f"    {k}: {'✅' if v else '❌ 未识别'}")
# A 验证：渠道/合作类型/佣金字段是否入库
extra = conn.execute(
    "SELECT COUNT(*) FILTER (WHERE channel IS NOT NULL), "
    "COUNT(*) FILTER (WHERE coop_type IS NOT NULL), "
    "COALESCE(SUM(commission_base),0), COALESCE(SUM(commission_amount),0) "
    "FROM orders WHERE import_id=?", (iid,)).fetchone()
print(f"  [A] 推广渠道有值行数={extra[0]}  合作类型有值行数={extra[1]}  "
      f"计佣金额合计={round(extra[2],2)}  预估佣金合计={round(extra[3],2)}")
print("  状态分布:", dict(conn.execute(
    "SELECT status,COUNT(*) FROM orders WHERE import_id=? GROUP BY status", (iid,)).fetchall()))
try:
    samples = [r[0] for r in conn.execute(
        "SELECT influencer_name FROM orders WHERE import_id=? AND influencer_name IS NOT NULL LIMIT 3",
        (iid,)).fetchall()]
    print("  达人名称样本:", samples)
except Exception as e:
    print("  达人字段: orders 表尚无 influencer_name 列 ->", type(e).__name__)
conn.close()
print("\nDONE", DB)
