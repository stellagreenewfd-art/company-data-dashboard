import os, datetime, importlib.util
import pandas as pd
spec = importlib.util.spec_from_file_location("app", r"C:\Users\R17\WorkBuddy\2026-08-25-09-41-54\app.py")
app = importlib.util.module_from_spec(spec); spec.loader.exec_module(app)
app.init_db()

def pd_excel(path):
    return pd.ExcelFile(path)
def pd_read(path, sheet, n=0):
    if n: return pd.read_excel(path, sheet_name=sheet, nrows=n)
    return pd.read_excel(path, sheet_name=sheet)

files = [
    # (path, platform, category, data_type override or '')
    (r"C:\Users\R17\Downloads\奶粉8月份.csv", "拼多多", "奶粉", ""),
    (r"C:\Users\R17\Downloads\鸡蛋7月8月销售数据.csv", "拼多多", "鸡蛋", ""),
    (r"C:\Users\R17\Downloads\鸡蛋天猫27021132492.xlsx", "天猫", "鸡蛋", ""),
    (r"C:\Users\R17\Downloads\小红书7月-8.23销售表.xlsx", "小红书", "鸡蛋", ""),
    (r"C:\Users\R17\Downloads\鸡蛋抖音7月-8.23.xlsx", "抖音", "鸡蛋", ""),
    (r"C:\Users\R17\Downloads\鸡蛋 分天数据_20260801至20260823.xlsx", "拼多多", "鸡蛋", ""),
    (r"C:\Users\R17\Downloads\奶粉推广_分天数据_20260801至20260823.xlsx", "拼多多", "奶粉", ""),
    (r"C:\Users\R17\Downloads\鸡蛋_20260701至20260823.xlsx", "拼多多", "鸡蛋", ""),
    (r"C:\Users\R17\Downloads\奶粉8月份.xlsx", "拼多多", "奶粉", ""),
    (r"C:\Users\R17\Downloads\商品推广_汇总数据_20260801至20260823.xlsx", "拼多多", "奶粉", ""),
]

for path, platform, category, dt in files:
    fn = os.path.basename(path)
    print("="*70)
    print("FILE:", fn, "|", platform, category)
    try:
        if fn.lower().endswith((".xlsx", ".xls")):
            try:
                xl = pd_excel(path)
                sample = pd_read(path, xl.sheet_names[0], 50)
                data_type = dt or app.detect_data_type(sample)
                sheet = app.pick_sheet(xl, data_type)
                df = pd_read(path, sheet)
            except Exception:
                df = app.read_any(path)
                data_type = dt or app.detect_data_type(df)
        else:
            df = app.read_any(path)
            data_type = dt or app.detect_data_type(df)
        df = df.dropna(how="all")
        conn = app.get_db(); cur = conn.cursor()
        cur.execute("INSERT INTO imports (filename,platform,category,data_type,rows,imported_at) VALUES (?,?,?,?,?,?)",
                    (fn, platform, category, data_type, len(df), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        iid = cur.lastrowid
        if data_type == "sales": n = app.store_sales(df, platform, category, iid, conn)
        elif data_type == "promo_daily": n = app.store_promo_daily(df, platform, category, iid, conn)
        elif data_type == "promo_product":
            p0,p1 = app.parse_period_from_filename(fn); period=(p0 or "")+("~"+p1 if p1 and p1!=p0 else "")
            n = app.store_promo_product(df, platform, category, iid, period, conn)
        conn.commit(); conn.close()
        print(f"  => data_type={data_type}  stored_rows={n}  file_rows={len(df)}")
    except Exception as e:
        import traceback; traceback.print_exc()
        print("  ERROR:", repr(e))

# summary
conn = app.get_db(); c = conn.cursor()
print("\n=== DB SUMMARY ===")
for t in ["orders","daily_metrics","product_stats","imports"]:
    print(t, c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
print("orders date range:", c.execute("SELECT MIN(order_date),MAX(order_date) FROM orders").fetchone())
print("promo date range:", c.execute("SELECT MIN(data_date),MAX(data_date) FROM daily_metrics").fetchone())
print("platforms:", [r[0] for r in c.execute("SELECT DISTINCT platform FROM orders").fetchall()])
print("categories:", [r[0] for r in c.execute("SELECT DISTINCT category FROM orders").fetchall()])
# sample KPI-like
print("total sales:", round(c.execute("SELECT COALESCE(SUM(pay_amount),0) FROM orders").fetchone()[0],2))
print("total promo cost:", round(c.execute("SELECT COALESCE(SUM(promo_cost),0) FROM daily_metrics").fetchone()[0],2))
print("total promo sales:", round(c.execute("SELECT COALESCE(SUM(promo_sales),0) FROM daily_metrics").fetchone()[0],2))
conn.close()
