import os, glob, shutil, re, importlib.util

TMP_DB = r"C:\Users\R17\WorkBuddy\2026-08-25-09-41-54\company-data-dashboard\tools\_repro2.db"
if os.path.exists(TMP_DB): os.remove(TMP_DB)
os.environ["DB_PATH"] = TMP_DB
spec = importlib.util.spec_from_file_location("app", r"C:\Users\R17\WorkBuddy\2026-08-25-09-41-54\company-data-dashboard\app.py")
app = importlib.util.module_from_spec(spec); spec.loader.exec_module(app)
app.init_db(); conn = app.get_db()

SRC = r"C:\Users\R17\WorkBuddy\2026-08-25-09-41-54\data"

class FS:
    def __init__(self, src, name): self.src=src; self.filename=name
    def save(self, dst): shutil.copy(self.src, dst)

def orig(fn):
    m = re.match(r"tmp_\d+_(.*)", fn); return m.group(1) if m else fn

# 针对此前失败的推广文件，分别用 京东 / 天猫 作为"用户在下拉框选的平台"测试落库
targets = ["鸡蛋 分天数据", "商品推广_汇总数据", "奶粉8月份"]
for f in sorted(glob.glob(os.path.join(SRC,"*"))):
    name=os.path.basename(f)
    if not name.lower().endswith((".xlsx",".xls",".csv")): continue
    on=orig(name)
    if not any(t in on for t in targets): continue
    for plat in ["京东","天猫"]:
        fs=FS(f,on)
        res=app.process_upload(fs, plat, "", "", conn, user_id=1)
        print(f"{on[:40]:42s} | 平台={plat:4s} -> ok={res.get('ok')} rows={res.get('rows')} type={res.get('data_type')} err={res.get('error','')[:30]}")
    for t in ("imports","daily_metrics","product_stats"):
        conn.execute(f"DELETE FROM {t}")
    conn.commit()
