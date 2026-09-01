# -*- coding: utf-8 -*-
"""验证4份京东文件在手动指定平台/品类后能否落库。"""
import os, sys, sqlite3, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app
import pandas as pd

app.DB = os.path.join(tempfile.gettempdir(), "_repro6b.db")
if os.path.exists(app.DB):
    os.remove(app.DB)
app.init_db()

FILES = [
    (r"C:\Users\R17\Downloads\太极武当金顶自营--推广_报表中心_账户_30天_点击_不含赠品_成交订单_20260801_20260831.xlsx", "京东", "鸡蛋"),
    (r"C:\Users\R17\Downloads\武当pop-交易概况__分天下载_2026-08-01_2026-08-31.xlsx", "京东", "鸡蛋"),
    (r"C:\Users\R17\Downloads\太极武当金-自营-交易概况_不包括对比时间_离线_分天下载_2026-08-01_2026-08-31.xlsx", "京东", "鸡蛋"),
    (r"C:\Users\R17\Downloads\营销场景报表_20260831_104334.csv", "京东", "鸡蛋"),
]

print("=" * 100)
for path, plat, cat in FILES:
    fn = os.path.basename(path)
    # 读真实文件拿 detect_data_type
    try:
        if fn.lower().endswith(('.xlsx', '.xls')):
            xl = pd.ExcelFile(path)
            sample = pd.read_excel(path, sheet_name=xl.sheet_names[0], nrows=50)
            dtype = app.detect_data_type(sample)
        else:
            df = None
            for enc in ('utf-8', 'gbk', 'utf-8-sig'):
                try:
                    df = pd.read_csv(path, encoding=enc, nrows=50)
                    break
                except Exception:
                    continue
            sample = df
            dtype = app.detect_data_type(sample)
        print(f"\n### {fn}")
        print(f"  detect_data_type = {dtype}")
    except Exception as e:
        print(f"\n### {fn}\n  读取失败: {e}")
        continue

    conn = sqlite3.connect(app.DB)
    conn.row_factory = sqlite3.Row
    try:
        with open(path, 'rb') as f:
            data = f.read()
        fs = type('FS', (), {'filename': fn, 'save': lambda self, p: open(p, 'wb').write(data)})()
        res = app.process_upload(fs, plat, cat, '', conn)
        print(f"  override(平台={plat},品类={cat}) -> ok={res.get('ok')} type={res.get('data_type')} rows={res.get('rows')} err={res.get('error')}")
        # 打印回执字段识别
        fields = res.get('fields') or {}
        if fields:
            missing = [k for k, v in fields.items() if not v]
            print(f"  已识别字段: {[k for k,v in fields.items() if v]}")
            print(f"  缺失字段: {missing if missing else '无'}")
    except Exception as e:
        print(f"  process_upload 异常: {e!r}")
    finally:
        conn.close()

print("\n" + "=" * 100)
# 汇总各表行数
conn = sqlite3.connect(app.DB)
for t in ('orders', 'daily_metrics', 'product_stats'):
    try:
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"表 {t}: {n} 行")
    except Exception as e:
        print(f"表 {t}: 不存在/err {e}")
conn.close()
