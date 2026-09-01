# -*- coding: utf-8 -*-
"""Profile the 13 platform data files: sheets, columns, sample rows, dtypes."""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pandas as pd

FILES = [
    r"C:\Users\R17\Downloads\太极武当金-自营-交易概况_不包括对比时间_离线_分天下载_2026-08-01_2026-08-31.xlsx",
    r"C:\Users\R17\Downloads\8月红书鸡蛋销售数据表.xlsx",
    r"C:\Users\R17\Downloads\抖音8月鸡蛋销售数据表.xlsx",
    r"C:\Users\R17\Downloads\太极武当金顶自营--推广_报表中心_账户_30天_点击_不含赠品_成交订单_20260801_20260831.xlsx",
    r"C:\Users\R17\Downloads\武当pop-交易概况__分天下载_2026-08-01_2026-08-31.xlsx",
    r"C:\Users\R17\Downloads\天猫鸡蛋订单.xlsx",
    r"C:\Users\R17\Downloads\营销场景报表_20260831_104334(1).csv",
    r"C:\Users\R17\Downloads\拼多多奶粉推广.xlsx",
    r"C:\Users\R17\Downloads\拼多多奶粉订单.csv",
    r"C:\Users\R17\Downloads\拼多多鸡蛋商品推广__20260801至20260831.xlsx",
    r"C:\Users\R17\Downloads\拼多多鸡蛋订单明细-2026.8.1-8.31.xlsx",
    r"C:\Users\R17\Downloads\天猫订单.xlsx",
    r"C:\Users\R17\Downloads\营销场景报表_20260831_104334.csv",
]

def read_csv_any(path):
    for enc in ("utf-8-sig", "gbk", "gb18030", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc, dtype=str, nrows=500)
        except Exception:
            continue
    return None

for fp in FILES:
    name = os.path.basename(fp)
    print("=" * 100)
    print("FILE:", name)
    if not os.path.exists(fp):
        print("  !! NOT FOUND"); continue
    try:
        if fp.lower().endswith(".csv"):
            df = read_csv_any(fp)
            if df is None:
                print("  !! csv unreadable"); continue
            print(f"  rows={len(df)} cols={len(df.columns)}")
            print("  COLUMNS:", list(df.columns))
            print(df.head(3).to_string(max_colwidth=18))
        else:
            xl = pd.ExcelFile(fp)
            print("  SHEETS:", xl.sheet_names)
            for sh in xl.sheet_names[:3]:
                df = xl.parse(sh, dtype=str, nrows=500)
                print(f"  -- sheet[{sh}] rows={len(df)} cols={len(df.columns)}")
                print("  COLUMNS:", list(df.columns))
                print(df.head(3).to_string(max_colwidth=18))
    except Exception as e:
        print("  !! ERROR:", repr(e))
