# -*- coding: utf-8 -*-
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pandas as pd

FILES = [
    r"C:\Users\R17\Downloads\太极武当金顶自营--推广_报表中心_账户_30天_点击_不含赠品_成交订单_20260801_20260831.xlsx",
    r"C:\Users\R17\Downloads\武当pop-交易概况__分天下载_2026-08-01_2026-08-31.xlsx",
    r"C:\Users\R17\Downloads\天猫鸡蛋订单.xlsx",
]
for fp in FILES:
    print("=" * 90)
    print("FILE:", os.path.basename(fp))
    xl = pd.ExcelFile(fp)
    print("  SHEETS:", xl.sheet_names)
    for sh in xl.sheet_names[:2]:
        df = xl.parse(sh, dtype=str, nrows=300)
        print(f"  -- sheet[{sh}] rows={len(df)} cols={len(df.columns)}")
        print("  COLUMNS:", list(df.columns))
        if len(df):
            r = df.iloc[0]
            print("  ROW0:", {c: (str(r[c])[:20] if pd.notna(r[c]) else None) for c in list(df.columns)[:25]})
