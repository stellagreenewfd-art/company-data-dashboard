import os, glob
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

PLAT_KW = ["拼多多","天猫","淘宝","抖音","小红书","京东","视频号","快手"]
SALES_KEYCOLS = {
    "订单号": ["订单号","订单编号","主订单编号"],
    "日期": ["订单成交时间","订单付款时间","支付时间","订单创建时间","日期"],
    "金额": ["用户实付金额(元)","买家实付金额","商家实收金额(元)","商家应收金额(元)(支付金额)","商家应收金额","买家应付货款","商品总价(元)","总金额"],
    "数量": ["商品数量(件)","宝贝总数量","SKU件数","数量"],
}
PROMO_KEYCOLS = {
    "日期": ["日期"],
    "花费": ["成交花费(元)","总花费(元)","成交花费"],
    "交易额": ["交易额(元)","净交易额(元)","交易额"],
    "投产比": ["实际投产比","净实际投产比","投产比"],
}

def platform_from_name(fn):
    for kw in PLAT_KW:
        if kw in fn: return kw
    return ""

files = sorted(glob.glob(os.path.join(DATA, "*")))
for f in files:
    name = os.path.basename(f)
    if not name.lower().endswith((".xlsx",".xls",".csv")):
        continue
    plat = platform_from_name(name)
    print("="*85)
    print(f"FILE: {name}")
    print(f"  文件名平台识别: {plat or '(无/可能失败)'}")
    try:
        if name.lower().endswith(".csv"):
            df = pd.read_csv(f, nrows=5, encoding="utf-8", errors="ignore")
            sheets = [("CSV", df)]
        else:
            xl = pd.ExcelFile(f)
            sheets = [(sn, pd.read_excel(f, sheet_name=sn, nrows=5)) for sn in xl.sheet_names]
        for sn, df in sheets:
            dt = detect_data_type(df)
            cols = list(df.columns)
            print(f"  sheet='{sn}' | 列数={len(cols)} | 疑似类型={dt}")
            kc = SALES_KEYCOLS if dt in ("sales",) else PROMO_KEYCOLS
            hits = {k: find_col(cols, c) for k,c in kc.items()}
            miss = [k for k,v in hits.items() if not v]
            print(f"     关键列命中: {hits}")
            if miss:
                print(f"     !! 缺失关键列: {miss}  -> 这类数据会存0行/识别失败")
    except Exception as e:
        print("  ERROR:", repr(e))
