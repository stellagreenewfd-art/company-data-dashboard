import os, glob, shutil, sys

# 指向临时 DB，避免污染真实库
TMP_DB = r"C:\Users\R17\WorkBuddy\2026-08-25-09-41-54\company-data-dashboard\tools\_repro.db"
if os.path.exists(TMP_DB): os.remove(TMP_DB)
os.environ["DB_PATH"] = TMP_DB

import importlib.util
spec = importlib.util.spec_from_file_location("app", r"C:\Users\R17\WorkBuddy\2026-08-25-09-41-54\company-data-dashboard\app.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

app.init_db()
conn = app.get_db()

SRC = r"C:\Users\R17\WorkBuddy\2026-08-25-09-41-54\data"

class FS:
    def __init__(self, src, name):
        self.src = src; self.filename = name
    def save(self, dst):
        shutil.copy(self.src, dst)

def orig_name(fn):
    # 去掉 tmp_<ts>_ 前缀，还原真实上传文件名（含平台/品类信息）
    import re
    m = re.match(r"tmp_\d+_(.*)", fn)
    return m.group(1) if m else fn

results = []
for f in sorted(glob.glob(os.path.join(SRC, "*"))):
    name = os.path.basename(f)
    if not name.lower().endswith((".xlsx", ".xls", ".csv")):
        continue
    oname = orig_name(name)
    print("="*90)
    print("REAL FILE:", name)
    print("还原文件名:", oname)
    try:
        fs = FS(f, oname)
        res = app.process_upload(fs, "", "", "", conn, user_id=1)
        print("  结果:", res)
        results.append((oname, res))
    except Exception as e:
        import traceback
        print("  !! process_upload 抛异常:", repr(e))
        print(traceback.format_exc())
        results.append((oname, {"ok": False, "error": "EXC:"+repr(e)}))

print("\n\n################## 汇总 ##################")
ok_n = sum(1 for _, r in results if r.get("ok"))
fail = [(n, r) for n, r in results if not r.get("ok")]
zero = [(n, r) for n, r in results if r.get("ok") and r.get("rows") == 0]
print(f"总计 {len(results)} 个文件 | 成功 {ok_n} | 失败 {len(fail)} | 成功但0行 {len(zero)}")
print("\n--- 失败文件 ---")
for n, r in fail:
    print(f"  {n} -> {r.get('error')}")
print("\n--- 成功但存0行（疑似列不匹配）---")
for n, r in zero:
    print(f"  {n} -> data_type={r.get('data_type')} rows={r.get('rows')}")
