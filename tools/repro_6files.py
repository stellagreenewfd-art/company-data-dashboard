# -*- coding: utf-8 -*-
"""针对用户提供的6份京东/天猫文件，用真实 process_upload 逻辑逐份复现识别结果。
用法: python tools/repro_6files.py
"""
import os, sys, sqlite3, io, tempfile, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app  # noqa

# 用独立临时 DB，避免污染正式数据
app.DB = os.path.join(tempfile.gettempdir(), "_repro6.db")
if os.path.exists(app.DB):
    os.remove(app.DB)

# 初始化表结构
app.init_db()

FILES = [
    r"C:\Users\R17\Downloads\太极武当金顶自营--推广_报表中心_账户_30天_点击_不含赠品_成交订单_20260801_20260831.xlsx",
    r"C:\Users\R17\Downloads\武当pop-交易概况__分天下载_2026-08-01_2026-08-31.xlsx",
    r"C:\Users\R17\Downloads\太极武当金-自营-交易概况_不包括对比时间_离线_分天下载_2026-08-01_2026-08-31.xlsx",
    r"C:\Users\R17\Downloads\天猫鸡蛋订单.xlsx",
    r"C:\Users\R17\Downloads\天猫订单.xlsx",
    r"C:\Users\R17\Downloads\营销场景报表_20260831_104334.csv",
]

print("=" * 100)
for path in FILES:
    fn = os.path.basename(path)
    print(f"\n### 文件: {fn}")
    print(f"  文件名解析(平台/品类/类型): {app.parse_meta_from_filename(fn)}")
    # 读取文件做内容推断
    try:
        if fn.lower().endswith(('.xlsx', '.xls')):
            xl = pd_read = None
            import pandas as pd
            xl = pd.ExcelFile(path)
            df = pd.read_excel(path, sheet_name=xl.sheet_names[0], nrows=300)
        else:
            import pandas as pd
            # GBK/UTF-8 尝试
            df = None
            for enc in ('utf-8', 'gbk', 'utf-8-sig'):
                try:
                    df = pd.read_csv(path, encoding=enc, nrows=300)
                    break
                except Exception:
                    continue
        print(f"  列数: {len(df.columns)}  行数(前300): {len(df)}")
        print(f"  内容推断平台: {app.infer_platform_from_content(df) or '(空)'}")
        print(f"  内容推断品类: {app.infer_category_from_content(df) or '(空)'}")
        print(f"  内容推断数据类型: {app.detect_data_type(df)}")
    except Exception as e:
        print(f"  读取/推断失败: {e}")

    # 用真实 process_upload 跑（不传 override，完全自动）
    print(f"  ---- 自动识别(不手动选) process_upload ----")
    conn = sqlite3.connect(app.DB)
    conn.row_factory = sqlite3.Row
    try:
        with open(path, 'rb') as f:
            data = f.read()
        fs = type('FS', (), {
            'filename': fn,
            'save': lambda self, p: open(p, 'wb').write(data)
        })()
        res = app.process_upload(fs, '', '', '', conn)
        print(f"  结果: ok={res.get('ok')} platform={res.get('platform')} category={res.get('category')} type={res.get('data_type')} rows={res.get('rows')} err={res.get('error')}")
    except Exception as e:
        print(f"  process_upload 异常: {e!r}")
    finally:
        conn.close()

print("\n" + "=" * 100)
print("DONE")
