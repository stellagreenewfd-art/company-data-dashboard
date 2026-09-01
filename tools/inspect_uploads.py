import os, glob, sys
import pandas as pd

DATA = r"C:\Users\R17\WorkBuddy\2026-08-25-09-41-54\data"

def detect_data_type(df):
    cols = list(df.columns)
    colstr = " ".join(str(c) for c in cols)
    has_order = any(k in colstr for k in ["订单号", "订单编号", "主订单编号"])
    has_date = "日期" in cols
    has_promo = any(k in colstr for k in ["成交花费", "交易额", "投产比"])
    if has_order: return "sales"
    if has_date and has_promo: return "promo_daily"
    if has_promo: return "promo_product"
    return "sales"

def find_col(cols, cands):
    for c in cands:
        for col in cols:
            if c in str(col):
                return col
    return None

SALES_KEYCOLS = {
    "订单号": ["订单号", "订单编号", "主订单编号"],
    "日期": ["订单成交时间", "订单付款时间", "支付时间", "订单创建时间", "日期"],
    "金额": ["用户实付金额(元)", "买家实付金额", "商家实收金额(元)", "商家应收金额(元)(支付金额)", "商家应收金额", "买家应付货款", "商品总价(元)", "总金额"],
    "数量": ["商品数量(件)", "宝贝总数量", "SKU件数", "数量"],
}

files = sorted(glob.glob(os.path.join(DATA, "*")) )
for f in files:
    name = os.path.basename(f)
    if not (name.lower().endswith((".xlsx", ".xls", ".csv"))):
        continue
    if not any(k in name for k in ["京东", "天猫", "jd", "tmall", "淘宝"]):
        continue
    print("="*80)
    print("FILE:", name)
    try:
        if name.lower().endswith(".csv"):
            df = pd.read_csv(f, nrows=3, encoding="utf-8", errors="ignore")
            print(" [CSV] columns:", list(df.columns))
        else:
            xl = pd.ExcelFile(f)
            print(" [XLSX] sheets:", xl.sheet_names)
            for sn in xl.sheet_names:
                df = pd.read_excel(f, sheet_name=sn, nrows=5)
                print(f"  -- sheet '{sn}' shape={df.shape} dtype={detect_data_type(df)}")
                print("     cols:", list(df.columns))
                # 检查销售关键列命中
                for k, cands in SALES_KEYCOLS.items():
                    hit = find_col(list(df.columns), cands)
                    print(f"       {k}: 命中={hit}")
    except Exception as e:
        print("  ERROR:", repr(e))
