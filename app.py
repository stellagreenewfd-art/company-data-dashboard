# -*- coding: utf-8 -*-
"""
公司多平台经营数据管理系统
- 每天分平台上传数据（销售订单 / 推广分天 / 推广商品汇总）
- SQLite 历史累积存储（按 平台+品类+日期 去重 upsert）
- 看板 API：销售、推广、ROI、品类/平台对比、商品榜、长期趋势
"""
import os, io, re, json, sqlite3, datetime
from flask import Flask, request, jsonify, send_file, send_from_directory, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
STATIC = os.path.join(BASE, "static")
# DB 路径支持环境变量：云端部署时指向持久盘（如 /data/company.db）
DB = os.environ.get("DB_PATH", os.path.join(DATA_DIR, "company.db"))
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATIC, exist_ok=True)

app = Flask(__name__, static_folder=STATIC)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production-8f3k2d9s")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# 云端 HTTPS 下设为 1（通过环境变量 SECURE_COOKIES=1 开启 Secure Cookie）
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SECURE_COOKIES", "0") == "1"

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 5000))

# 全局 500 捕获：API 请求返回 JSON 错误，方便云端调试
import traceback
@app.errorhandler(500)
def handle_500(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "服务器内部错误", "detail": str(e), "traceback": traceback.format_exc()}), 500
    return str(e), 500

# ----------------------------------------------------------------------------
# DB
# ----------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def init_db():
    conn = get_db(); c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'user',
      status TEXT NOT NULL DEFAULT 'active',
      created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS imports (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      filename TEXT, platform TEXT, category TEXT, data_type TEXT,
      rows INTEGER, date_min TEXT, date_max TEXT, period TEXT,
      imported_at TEXT, note TEXT, user_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS orders (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      import_id INTEGER, platform TEXT, category TEXT,
      order_id TEXT, order_date TEXT, pay_amount REAL,
      item_count REAL, status TEXT, is_refund INTEGER DEFAULT 0,
      refund_amount REAL, product_name TEXT, shop TEXT, province TEXT,
      extras TEXT,
      UNIQUE(platform, category, order_id)
    );
    CREATE TABLE IF NOT EXISTS daily_metrics (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      import_id INTEGER, platform TEXT, category TEXT, data_date TEXT,
      promo_cost REAL, promo_sales REAL, roi REAL,
      order_count REAL, exposure REAL, clicks REAL, extras TEXT,
      UNIQUE(platform, category, data_date)
    );
    CREATE TABLE IF NOT EXISTS product_stats (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      import_id INTEGER, platform TEXT, category TEXT,
      product_id TEXT, product_name TEXT, period TEXT,
      promo_cost REAL, promo_sales REAL, roi REAL,
      order_count REAL, exposure REAL, clicks REAL, extras TEXT,
      UNIQUE(platform, category, product_id, period)
    );
    CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date);
    CREATE INDEX IF NOT EXISTS idx_orders_pc ON orders(platform,category);
    CREATE INDEX IF NOT EXISTS idx_dm_date ON daily_metrics(data_date);
    CREATE INDEX IF NOT EXISTS idx_dm_pc ON daily_metrics(platform,category);
    """)
    # 旧库兼容：若 imports 没有 user_id 列则补上
    cols = [r[1] for r in c.execute("PRAGMA table_info(imports)")]
    if "user_id" not in cols:
        try: c.execute("ALTER TABLE imports ADD COLUMN user_id INTEGER")
        except Exception: pass
    # 旧库兼容：若 users 没有 status 列则补上
    ucols = [r[1] for r in c.execute("PRAGMA table_info(users)")]
    if "status" not in ucols:
        try: c.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        except Exception: pass
    # 首次运行：播种管理员账号（仅当无任何用户时）
    cnt = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if cnt == 0:
        c.execute("INSERT INTO users (username,password_hash,role,created_at) VALUES (?,?,?,?)",
                  ("admin", generate_password_hash("admin123"), "admin",
                   datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        print("[init] 已创建默认管理员 admin / admin123，请尽快修改密码")
    conn.commit(); conn.close()

# ----------------------------------------------------------------------------
# 鉴权
# ----------------------------------------------------------------------------
def get_current_user():
    uid = session.get("user_id")
    if not uid: return None
    conn = get_db(); c = conn.cursor()
    r = c.execute("SELECT id,username,role FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return dict(r) if r else None

def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapped(*a, **k):
        u = get_current_user()
        if not u:
            # 页面请求跳登录；API 请求返回 401
            if request.path.startswith("/api/"):
                return jsonify({"error": "未登录"}), 401
            return redirect("/login")
        return f(*a, **k)
    return wrapped

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrapped(*a, **k):
        u = get_current_user()
        if not u:
            return jsonify({"error": "未登录"}), 401
        if u.get("role") != "admin":
            return jsonify({"error": "需要管理员权限"}), 403
        return f(*a, **k)
    return wrapped

# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def to_float(x):
    if x is None: return None
    if isinstance(x, (int, float)):
        return None if (isinstance(x, float) and pd.isna(x)) else float(x)
    s = str(x).strip().replace(",", "").replace("%", "")
    s = re.sub(r"[^\d.\-]", "", s)
    if s in ("", "-", ".", "."): return None
    try: return float(s)
    except: return None

def to_date(x):
    if x is None: return None
    if isinstance(x, datetime.datetime): return x.strftime("%Y-%m-%d")
    if isinstance(x, datetime.date): return x.strftime("%Y-%m-%d")
    s = str(x).strip()
    m = re.search(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})", s)
    if m: return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{1,2})月(\d{1,2})[日号]", s)
    if m: return f"2026-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return None

def find_col(cols, candidates):
    for cand in candidates:
        for c in cols:
            if c == cand or cand in str(c):
                return c
    return None

def read_any(path):
    """Read xlsx/csv/误命名TSV into a DataFrame."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        for enc in ["utf-8-sig", "utf-8", "gbk"]:
            try:
                return pd.read_csv(path, encoding=enc)
            except Exception:
                continue
        return pd.read_csv(path, encoding="utf-8", errors="ignore")
    # xlsx / 误命名
    try:
        return pd.read_excel(path)
    except Exception:
        # 可能是 GBK TSV 被改名成 .xlsx
        for enc in ["gbk", "utf-8-sig", "utf-8"]:
            try:
                return pd.read_csv(path, sep="\t", encoding=enc)
            except Exception:
                continue
    raise ValueError("无法解析文件，请确认格式为 Excel / CSV / TSV")

def pick_sheet(xl, data_type):
    names = xl.sheet_names
    if data_type == "promo_daily":
        for n in names:
            if "汇总" in n and "商品" not in n: return n
        for n in names:
            if "分天" in n and "商品" not in n: return n
        return names[0]
    if data_type == "promo_product":
        for n in names:
            if "商品" in n: return n
        return names[0]
    return names[0]

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

def parse_period_from_filename(fn):
    m = re.search(r"(\d{4})(\d{2})(\d{2})[至~-](\d{4})(\d{2})(\d{2})", fn)
    if m:
        return (f"{m.group(1)}-{m.group(2)}-{m.group(3)}",
                f"{m.group(4)}-{m.group(5)}-{m.group(6)}")
    m = re.search(r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})", fn)
    if m:
        d = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return (d, d)
    return (None, None)

# ----------------------------------------------------------------------------
# 文件名智能识别：平台 / 品类 / 数据类型
# ----------------------------------------------------------------------------
DEFAULT_PLATFORMS = ["拼多多", "天猫", "淘宝", "抖音", "小红书", "京东", "视频号", "快手"]
DEFAULT_CATEGORIES = ["鸡蛋", "奶粉", "生鲜", "食品", "文创饰品", "智能锁", "叶黄素鸡蛋"]

def parse_meta_from_filename(fn):
    """从文件名推断 平台 / 品类 / 数据类型。返回 (platform, category, data_type)。
    模糊（如仅有“分天数据”无推广/销售字样）的 data_type 返回空，交由列检测决定。"""
    platform = ""
    for kw in ["拼多多", "天猫", "淘宝", "抖音", "小红书", "京东", "视频号", "快手"]:
        if kw in fn:
            platform = kw
            break
    category = ""
    if "叶黄素" in fn:
        category = "叶黄素鸡蛋"
    else:
        for kw in ["鸡蛋", "奶粉", "生鲜", "食品", "文创", "饰品", "锁"]:
            if kw in fn:
                category = kw
                break
    has_promo = ("推广" in fn) or ("汇总" in fn)
    has_product = "商品" in fn
    has_sales = ("销售" in fn) or ("订单" in fn)
    data_type = ""
    if has_product and has_promo:
        data_type = "promo_product"
    elif has_promo and ("分天" in fn or "每日" in fn):
        data_type = "promo_daily"
    elif has_sales:
        data_type = "sales"
    return platform, category, data_type

# 内容辅助识别品类：当文件名无法识别时，扫描表头+样本数据里的关键词
CONTENT_CATEGORY_HINTS = {
    "奶粉": ["奶粉", "皇家美素佳儿", "美素佳儿", "飞鹤", "爱他美", "a2", "惠氏", "牛栏"],
    "鸡蛋": ["鸡蛋", "蛋", "沙门氏菌", "叶黄素", "可生食"],
    "智能锁": ["智能锁", "指纹锁", "密码锁", "鹿客", "凯迪仕", "德施曼"],
    "文创饰品": ["文创", "饰品", "项链", "手链", "耳环"],
}

def infer_category_from_content(df):
    """扫描 DataFrame 的列名与前 N 行文本，推断品类。返回品类字符串或空。"""
    if df is None or df.empty:
        return ""
    text = " ".join(str(c) for c in df.columns)
    # 取前 200 行、前 10 列的样本，避免大文件太慢
    sample = df.head(200)
    for col in sample.columns[:10]:
        try:
            text += " " + " ".join(str(v) for v in sample[col].dropna().astype(str).tolist())
        except Exception:
            pass
    text = text.lower()
    scores = {}
    for cat, hints in CONTENT_CATEGORY_HINTS.items():
        scores[cat] = sum(1 for h in hints if h.lower() in text)
    if scores:
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best
    return ""

def is_total_row(row_dict):
    """判断一行是否为平台导出的合计/总计/注释行。"""
    pid = str(row_dict.get("product_id", "")).strip().lower()
    pname = str(row_dict.get("product_name", "")).strip()
    if pid in ("总计", "合计", "汇总", "total", "all", "sum"):
        return True
    if pname in ("-", "总计", "合计", "汇总") and not row_dict.get("product_id"):
        return True
    return False

# ----------------------------------------------------------------------------
# parsing -> store
# ----------------------------------------------------------------------------
def store_sales(df, platform, category, import_id, conn):
    cols = list(df.columns)
    date_col = find_col(cols, ["订单成交时间", "订单付款时间", "支付时间", "订单创建时间", "日期"])
    pay_col = find_col(cols, ["用户实付金额(元)", "买家实付金额", "商家实收金额(元)",
                              "商家应收金额(元)(支付金额)", "商家应收金额", "买家应付货款",
                              "商品总价(元)", "总金额"])
    qty_col = find_col(cols, ["商品数量(件)", "宝贝总数量", "SKU件数", "数量"])
    status_col = find_col(cols, ["订单状态", "售后状态"])
    refund_col = find_col(cols, ["退款金额"])
    prod_col = find_col(cols, ["商品标题", "商品名称", "SKU名称", "选购商品", "商品"])
    shop_col = find_col(cols, ["店铺名称"])
    prov_col = find_col(cols, ["省", "收货地址"])
    oid_col = find_col(cols, ["订单号", "订单编号", "主订单编号"])

    rows = []
    for _, r in df.iterrows():
        oid = str(r[oid_col]) if oid_col else None
        if not oid or oid in ("nan", ""): continue
        d = to_date(r[date_col]) if date_col else None
        pay = to_float(r[pay_col]) if pay_col else None
        qty = to_float(r[qty_col]) if qty_col else None
        status = str(r[status_col]) if status_col else ""
        refund_amt = to_float(r[refund_col]) if refund_col else None
        is_refund = 0
        if refund_col and refund_amt and refund_amt > 0:
            is_refund = 1
        elif status and any(k in status for k in ["退款", "售后"]):
            is_refund = 1
        prod = str(r[prod_col])[:200] if prod_col and r[prod_col] is not None else None
        shop = str(r[shop_col]) if shop_col and r[shop_col] is not None else None
        prov = None
        if prov_col:
            v = str(r[prov_col])
            if " " in v: prov = v.split(" ")[0]
            else: prov = v[:10]
        extras = json.dumps({str(k): (None if (isinstance(r[k], float) and pd.isna(r[k])) else r[k]) for k in cols}, ensure_ascii=False, default=str)
        rows.append((import_id, platform, category, oid, d, pay, qty, status,
                     is_refund, refund_amt, prod, shop, prov, extras))
    c = conn.cursor()
    c.executemany(
        """INSERT OR REPLACE INTO orders
           (import_id,platform,category,order_id,order_date,pay_amount,item_count,
            status,is_refund,refund_amount,product_name,shop,province,extras)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    return len(rows)

def store_promo_daily(df, platform, category, import_id, conn):
    cols = list(df.columns)
    date_col = find_col(cols, ["日期"])
    cost_col = find_col(cols, ["成交花费(元)", "总花费(元)", "成交花费"])
    sales_col = find_col(cols, ["交易额(元)", "净交易额(元)", "交易额"])
    roi_col = find_col(cols, ["实际投产比", "净实际投产比", "投产比"])
    ord_col = find_col(cols, ["成交笔数", "净成交笔数"])
    exp_col = find_col(cols, ["曝光量"])
    clk_col = find_col(cols, ["点击量"])
    rows = []
    for _, r in df.iterrows():
        d = to_date(r[date_col]) if date_col else None
        if not d: continue
        extras = json.dumps({str(k): (None if (isinstance(r[k], float) and pd.isna(r[k])) else r[k]) for k in cols}, ensure_ascii=False, default=str)
        rows.append((import_id, platform, category, d,
                     to_float(r[cost_col]) if cost_col else None,
                     to_float(r[sales_col]) if sales_col else None,
                     to_float(r[roi_col]) if roi_col else None,
                     to_float(r[ord_col]) if ord_col else None,
                     to_float(r[exp_col]) if exp_col else None,
                     to_float(r[clk_col]) if clk_col else None, extras))
    c = conn.cursor()
    c.executemany(
        """INSERT OR REPLACE INTO daily_metrics
           (import_id,platform,category,data_date,promo_cost,promo_sales,roi,
            order_count,exposure,clicks,extras)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""", rows)
    return len(rows)

def store_promo_product(df, platform, category, import_id, period, conn):
    cols = list(df.columns)
    pid_col = find_col(cols, ["商品ID", "商品id"])
    pname_col = find_col(cols, ["商品名称", "推广名称", "商品标题"])
    cost_col = find_col(cols, ["成交花费(元)", "成交花费"])
    sales_col = find_col(cols, ["交易额(元)", "净交易额(元)", "交易额"])
    roi_col = find_col(cols, ["实际投产比", "投产比"])
    ord_col = find_col(cols, ["成交笔数", "净成交笔数"])
    exp_col = find_col(cols, ["曝光量"])
    clk_col = find_col(cols, ["点击量"])
    rows = []
    for _, r in df.iterrows():
        pid = str(r[pid_col]) if pid_col else None
        if not pid or pid in ("nan", ""): pid = "UNK_" + str(len(rows))
        # 过滤平台导出表里的“总计/合计/汇总/注释”行
        pids = pid.strip().lower()
        if pids in ("总计", "合计", "汇总", "total", "sum", "all"):
            continue
        pname = str(r[pname_col])[:200] if pname_col and r[pname_col] is not None else None
        if pname and pname.strip() in ("-", "总计", "合计", "汇总") and (not pid or pid.startswith("UNK_")):
            continue
        cost = to_float(r[cost_col]) if cost_col else None
        sales = to_float(r[sales_col]) if sales_col else None
        orders = to_float(r[ord_col]) if ord_col else None
        # 过滤注释/空行：没有商品ID、没有商品名、关键指标全空
        if pid.startswith("UNK_") and not pname and not any([cost, sales, orders]):
            continue
        extras = json.dumps({str(k): (None if (isinstance(r[k], float) and pd.isna(r[k])) else r[k]) for k in cols}, ensure_ascii=False, default=str)
        rows.append((import_id, platform, category, pid, pname, period,
                     cost, sales,
                     to_float(r[roi_col]) if roi_col else None,
                     orders,
                     to_float(r[exp_col]) if exp_col else None,
                     to_float(r[clk_col]) if clk_col else None, extras))
    c = conn.cursor()
    c.executemany(
        """INSERT OR REPLACE INTO product_stats
           (import_id,platform,category,product_id,product_name,period,promo_cost,
            promo_sales,roi,order_count,exposure,clicks,extras)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    return len(rows)

# ----------------------------------------------------------------------------
# API
# ----------------------------------------------------------------------------
@app.route("/")
def index():
    return send_file(os.path.join(STATIC, "index.html"))

@app.route("/api/health")
def health():
    """公开健康检查端点（Render 健康检查用，无需登录）。"""
    return jsonify({"status": "ok"})

@app.route("/api/dimensions")
@login_required
def dimensions():
    conn = get_db(); c = conn.cursor()
    db_plats = [r[0] for r in c.execute("SELECT DISTINCT platform FROM orders UNION SELECT DISTINCT platform FROM daily_metrics UNION SELECT DISTINCT platform FROM product_stats")]
    db_cats = [r[0] for r in c.execute("SELECT DISTINCT category FROM orders UNION SELECT DISTINCT category FROM daily_metrics UNION SELECT DISTINCT category FROM product_stats")]
    conn.close()
    def merge(defaults, dbvals):
        s = list(defaults)
        for v in dbvals:
            if v and v not in s:
                s.append(v)
        return s
    return jsonify({"platforms": merge(DEFAULT_PLATFORMS, db_plats),
                    "categories": merge(DEFAULT_CATEGORIES, db_cats)})

@app.route("/api/guess")
def guess():
    """根据文件名预填 平台/品类/数据类型，供前端上传前自动识别。"""
    fn = request.args.get("filename", "")
    p, c, t = parse_meta_from_filename(fn)
    return jsonify({"platform": p, "category": c, "data_type": t})

# ----------------------------------------------------------------------------
# 鉴权路由
# ----------------------------------------------------------------------------
@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    conn = get_db(); c = conn.cursor()
    r = c.execute("SELECT id,username,password_hash,role,status FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if not r or not check_password_hash(r["password_hash"], password):
        return jsonify({"error": "用户名或密码错误"}), 401
    if r.get("status") == "pending":
        return jsonify({"error": "账号待管理员审核，请等待审核通过后再登录"}), 403
    if r.get("status") == "rejected":
        return jsonify({"error": "账号审核未通过，请联系管理员"}), 403
    session["user_id"] = r["id"]
    return jsonify({"ok": True, "user": {"username": r["username"], "role": r["role"]}})

@app.route("/api/register", methods=["POST"])
def api_register():
    """自助注册：开放给任何人，提交申请后默认角色为成员、状态为待审核，需管理员审核通过后生效。"""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "用户名和密码必填"}), 400
    if not (2 <= len(username) <= 20):
        return jsonify({"error": "用户名长度需 2-20 个字符"}), 400
    if len(password) < 6:
        return jsonify({"error": "密码至少 6 位"}), 400
    conn = get_db(); c = conn.cursor()
    exists = c.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone()
    if exists:
        conn.close(); return jsonify({"error": "用户名已存在"}), 400
    c.execute("INSERT INTO users (username,password_hash,role,status,created_at) VALUES (?,?,?,?,?)",
              (username, generate_password_hash(password), "user", "pending",
               datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()
    return jsonify({"ok": True, "message": "申请已提交，等待管理员审核通过后即可登录"})

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/me")
def api_me():
    u = get_current_user()
    if not u: return jsonify({"user": None}), 401
    return jsonify({"user": u})

@app.route("/api/users", methods=["GET"])
@admin_required
def list_users():
    conn = get_db(); c = conn.cursor()
    rows = c.execute("SELECT id,username,role,status,created_at FROM users ORDER BY id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/users", methods=["POST"])
@admin_required
def create_user():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = data.get("role") if data.get("role") in ("admin", "user") else "user"
    if not username or not password:
        return jsonify({"error": "用户名和密码必填"}), 400
    conn = get_db(); c = conn.cursor()
    exists = c.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone()
    if exists:
        conn.close(); return jsonify({"error": "用户名已存在"}), 400
    c.execute("INSERT INTO users (username,password_hash,role,created_at) VALUES (?,?,?,?)",
              (username, generate_password_hash(password), role,
               datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/users/<int:uid>", methods=["DELETE"])
@admin_required
def delete_user(uid):
    u = get_current_user()
    if u["id"] == uid:
        return jsonify({"error": "不能删除自己"}), 400
    conn = get_db(); c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/users/<int:uid>/approve", methods=["POST"])
@admin_required
def approve_user(uid):
    conn = get_db(); c = conn.cursor()
    c.execute("UPDATE users SET status='active' WHERE id=?", (uid,))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/users/<int:uid>/reject", methods=["POST"])
@admin_required
def reject_user(uid):
    conn = get_db(); c = conn.cursor()
    r = c.execute("SELECT 1 FROM users WHERE id=? AND role='admin'", (uid,)).fetchone()
    if r:
        conn.close(); return jsonify({"error": "不能拒绝管理员账号"}), 400
    c.execute("UPDATE users SET status='rejected' WHERE id=?", (uid,))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

def process_upload(file_storage, platform_override, category_override, data_type_override, conn, user_id=None):
    """处理单个上传文件：自动识别 → 解析 → 入库。返回结果 dict。"""
    fn = file_storage.filename or "upload"
    platform = (platform_override or "").strip()
    category = (category_override or "").strip()
    data_type = (data_type_override or "").strip()
    gp, gc, gtype = parse_meta_from_filename(fn)
    if not platform: platform = gp
    if not category: category = gc
    # 注意：category 的内容推断在读取 df 后二次校验，见下方
    if not platform:
        return {"filename": fn, "ok": False,
                "error": "无法识别平台，请在文件名中包含平台名（如 拼多多/抖音/天猫）或手动选择"}
    tmp = os.path.join(DATA_DIR, "tmp_" + str(datetime.datetime.now().timestamp()).replace(".", "") + "_" + fn)
    file_storage.save(tmp)
    try:
        is_excel = fn.lower().endswith((".xlsx", ".xls"))
        try:
            if is_excel:
                xl = pd.ExcelFile(tmp)
                if not data_type:
                    sample = pd.read_excel(tmp, sheet_name=xl.sheet_names[0], nrows=50)
                    data_type = gtype or detect_data_type(sample)
                sheet = pick_sheet(xl, data_type)
                df = pd.read_excel(tmp, sheet_name=sheet)
            else:
                df = read_any(tmp)
                if not data_type:
                    data_type = gtype or detect_data_type(df)
        except Exception:
            # 误命名 / 非标准 Excel（如 GBK TSV 改名 .xlsx）
            df = read_any(tmp)
            if not data_type:
                data_type = gtype or detect_data_type(df)
        df = df.dropna(how="all")
        # 文件名没识别出品类的，再用内容推断一次；仍识别不出则报错
        if not category:
            category = infer_category_from_content(df)
        if not category:
            return {"filename": fn, "ok": False,
                    "error": "无法识别品类，请在文件名中包含品类名（如 鸡蛋/奶粉）或手动选择"}
        cur = conn.cursor()
        cur.execute("INSERT INTO imports (filename,platform,category,data_type,rows,imported_at,user_id) VALUES (?,?,?,?,?,?,?)",
                    (fn, platform, category, data_type, len(df), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        import_id = cur.lastrowid
        if data_type == "sales":
            n = store_sales(df, platform, category, import_id, conn)
        elif data_type == "promo_daily":
            n = store_promo_daily(df, platform, category, import_id, conn)
        elif data_type == "promo_product":
            p0, p1 = parse_period_from_filename(fn)
            period = (p0 or "") + ("~" + p1 if p1 and p1 != p0 else "")
            n = store_promo_product(df, platform, category, import_id, period, conn)
        else:
            n = 0
        dmin = dmax = None
        if data_type == "sales":
            rr = cur.execute("SELECT MIN(order_date),MAX(order_date) FROM orders WHERE import_id=?", (import_id,)).fetchone()
            dmin, dmax = rr[0], rr[1]
        elif data_type == "promo_daily":
            rr = cur.execute("SELECT MIN(data_date),MAX(data_date) FROM daily_metrics WHERE import_id=?", (import_id,)).fetchone()
            dmin, dmax = rr[0], rr[1]
        cur.execute("UPDATE imports SET date_min=?,date_max=? WHERE id=?", (dmin, dmax, import_id))
        conn.commit()
        return {"filename": fn, "ok": True, "data_type": data_type, "rows": n,
                "platform": platform, "category": category, "date_min": dmin, "date_max": dmax}
    except Exception as e:
        return {"filename": fn, "ok": False, "error": str(e)}
    finally:
        try: os.remove(tmp)
        except: pass

@app.route("/api/upload", methods=["POST"])
@login_required
def upload():
    u = get_current_user()
    f = request.files.get("file")
    if not f: return jsonify({"error": "未收到文件"}), 400
    platform = request.form.get("platform", "")
    category = request.form.get("category", "")
    data_type = request.form.get("data_type", "")
    conn = get_db()
    res = process_upload(f, platform, category, data_type, conn, user_id=u["id"])
    conn.close()
    if not res.get("ok"): return jsonify({"error": res.get("error")}), 400
    return jsonify(res)

@app.route("/api/upload_batch", methods=["POST"])
@login_required
def upload_batch():
    u = get_current_user()
    files = request.files.getlist("files")
    if not files: return jsonify({"error": "未收到文件"}), 400
    # 批量时允许前端在文件名里标注覆盖（?platform= / ?category= / ?data_type= 不支持多值，故只用自动识别）
    platform = request.form.get("platform", "")
    category = request.form.get("category", "")
    data_type = request.form.get("data_type", "")
    conn = get_db()
    results = [process_upload(f, platform, category, data_type, conn, user_id=u["id"]) for f in files]
    conn.close()
    ok = [r for r in results if r.get("ok")]
    fail = [r for r in results if not r.get("ok")]
    return jsonify({
        "ok": True,
        "total": len(results),
        "success": len(ok),
        "failed": len(fail),
        "results": results,
    })

@app.route("/api/overview")
@login_required
def overview():
    start = request.args.get("start", "")
    end = request.args.get("end", "")
    platforms = [p for p in request.args.get("platforms", "").split(",") if p]
    categories = [c for c in request.args.get("categories", "").split(",") if c]

    conn = get_db(); c = conn.cursor()
    def wc(table, datecol):
        clauses = []
        params = []
        if start: clauses.append(f"{datecol}>=?"); params.append(start)
        if end: clauses.append(f"{datecol}<=?"); params.append(end)
        if platforms: clauses.append(f"platform IN ({','.join('?'*len(platforms))})"); params += platforms
        if categories: clauses.append(f"category IN ({','.join('?'*len(categories))})"); params += categories
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    # sales — 只统计有效成交（排除取消/退款/未成交/待付款/待成交/已关闭）
    NEG = ("(order_date IS NOT NULL) AND (status IS NULL OR ("
           "status NOT LIKE '%取消%' AND status NOT LIKE '%退款成功%' AND "
           "status NOT LIKE '%未成交%' AND status NOT LIKE '%待付款%' AND "
           "status NOT LIKE '%待成交%' AND status NOT LIKE '%已关闭%'))")
    wc_s, p_s = wc("orders", "order_date")
    wc_s_valid = wc_s + ((" AND " + NEG) if wc_s else (" WHERE " + NEG))
    sales_rows = c.execute(
        f"""SELECT order_date, platform, category,
                   COALESCE(SUM(pay_amount),0) sales,
                   COUNT(*) orders,
                   COALESCE(SUM(item_count),0) units
            FROM orders {wc_s_valid} GROUP BY order_date, platform, category""", p_s).fetchall()
    # promo
    wc_p, p_p = wc("daily_metrics", "data_date")
    promo_rows = c.execute(
        f"""SELECT data_date, platform, category,
                   COALESCE(promo_cost,0) promo_cost,
                   COALESCE(promo_sales,0) promo_sales,
                   roi, COALESCE(order_count,0) orders,
                   COALESCE(exposure,0) exposure, COALESCE(clicks,0) clicks
            FROM daily_metrics {wc_p}""", p_p).fetchall()
    # 退款（跨全部订单：有效成交后的退款 + 显式退款金额）
    wc_r, p_r = wc("orders", "order_date")
    wc_r_ref = wc_r + ((" AND " ) if wc_r else " WHERE ") + "(COALESCE(refund_amount,0)>0 OR is_refund=1)"
    refund_row = c.execute(f"SELECT COALESCE(SUM(refund_amount),0), COALESCE(SUM(is_refund),0) FROM orders {wc_r_ref}", p_r).fetchone()
    conn.close()

    # KPIs
    total_sales = sum(r["sales"] for r in sales_rows)
    total_orders = sum(r["orders"] for r in sales_rows)
    total_units = sum(r["units"] for r in sales_rows)
    total_refund = refund_row[0]
    total_promo_cost = sum(r["promo_cost"] for r in promo_rows)
    total_promo_sales = sum(r["promo_sales"] for r in promo_rows)
    avg_aov = (total_sales / total_orders) if total_orders else 0
    overall_roi = (total_promo_sales / total_promo_cost) if total_promo_cost else 0
    refund_rate = (total_refund / total_sales) if total_sales else 0

    # combined daily series
    dates = set()
    for r in sales_rows: dates.add(r["order_date"])
    for r in promo_rows: dates.add(r["data_date"])
    dates = sorted(d for d in dates if d)
    series = {}
    for d in dates:
        series[d] = {}
    def key(p, cat): return p + " / " + cat
    for r in sales_rows:
        k = key(r["platform"], r["category"])
        series[r["order_date"]].setdefault(k, {"sales": 0, "promo_cost": 0, "promo_sales": 0, "roi": None})
        series[r["order_date"]][k]["sales"] += r["sales"]
    for r in promo_rows:
        k = key(r["platform"], r["category"])
        series[r["data_date"]].setdefault(k, {"sales": 0, "promo_cost": 0, "promo_sales": 0, "roi": None})
        series[r["data_date"]][k]["promo_cost"] += r["promo_cost"]
        series[r["data_date"]][k]["promo_sales"] += r["promo_sales"]
        if r["roi"]:
            series[r["data_date"]][k]["roi"] = r["roi"]

    platforms_set = sorted(set([r["platform"] for r in sales_rows] + [r["platform"] for r in promo_rows]))
    categories_set = sorted(set([r["category"] for r in sales_rows] + [r["category"] for r in promo_rows]))
    combos = sorted(set(list(series[d].keys()) for d in dates), key=lambda x: x[0] if x else "") if False else None
    combo_keys = sorted(set(k for d in dates for k in series[d].keys()))

    # daily totals (for trend chart)
    daily_trend = []
    for d in dates:
        row = {"date": d, "sales": 0, "promo_cost": 0, "promo_sales": 0}
        for k, v in series[d].items():
            row["sales"] += v["sales"]
            row["promo_cost"] += v["promo_cost"]
            row["promo_sales"] += v["promo_sales"]
        daily_trend.append(row)

    # platform breakdown (sales)
    plat_sales = {}
    for r in sales_rows:
        plat_sales[r["platform"]] = plat_sales.get(r["platform"], 0) + r["sales"]
    plat_promo = {}
    for r in promo_rows:
        plat_promo[r["platform"]] = plat_promo.get(r["platform"], 0) + r["promo_cost"]
    platform_breakdown = [{"platform": p,
                           "sales": round(plat_sales.get(p, 0), 2),
                           "promo_cost": round(plat_promo.get(p, 0), 2)} for p in platforms_set]

    # category breakdown
    cat_sales = {}
    for r in sales_rows:
        cat_sales[r["category"]] = cat_sales.get(r["category"], 0) + r["sales"]
    category_breakdown = [{"category": c, "sales": round(cat_sales.get(c, 0), 2)} for c in categories_set]

    return jsonify({
        "kpis": {
            "total_sales": round(total_sales, 2),
            "total_orders": total_orders,
            "avg_aov": round(avg_aov, 2),
            "total_units": round(total_units, 2),
            "total_refund": round(total_refund, 2),
            "refund_rate": round(refund_rate, 4),
            "total_promo_cost": round(total_promo_cost, 2),
            "total_promo_sales": round(total_promo_sales, 2),
            "overall_roi": round(overall_roi, 2),
        },
        "daily_trend": daily_trend,
        "combo_keys": combo_keys,
        "series": {d: series[d] for d in dates},
        "platform_breakdown": platform_breakdown,
        "category_breakdown": category_breakdown,
        "platforms": platforms_set,
        "categories": categories_set,
        "date_min": dates[0] if dates else None,
        "date_max": dates[-1] if dates else None,
    })

@app.route("/api/products")
@login_required
def products():
    platform = request.args.get("platform", "")
    category = request.args.get("category", "")
    limit = int(request.args.get("limit", 15))
    conn = get_db(); c = conn.cursor()
    clauses = []; params = []
    if platform: clauses.append("platform=?"); params.append(platform)
    if category: clauses.append("category=?"); params.append(category)
    wc = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = c.execute(
        f"""SELECT product_name, platform, category, period,
                   COALESCE(SUM(promo_cost),0) promo_cost,
                   COALESCE(SUM(promo_sales),0) promo_sales,
                   COALESCE(AVG(roi),0) roi,
                   COALESCE(SUM(order_count),0) orders
            FROM product_stats {wc} GROUP BY product_name, platform, category, period
            ORDER BY promo_sales DESC LIMIT ?""", params + [limit]).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/imports")
@login_required
def imports():
    conn = get_db(); c = conn.cursor()
    rows = c.execute("""SELECT i.*, u.username AS uploader
                        FROM imports i LEFT JOIN users u ON i.user_id=u.id
                        ORDER BY i.id DESC""").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/imports/<int:import_id>", methods=["DELETE"])
@login_required
def delete_import(import_id):
    u = get_current_user()
    if not u:
        return jsonify({"error": "未登录"}), 401
    conn = get_db(); c = conn.cursor()
    row = c.execute("SELECT user_id FROM imports WHERE id=?", (import_id,)).fetchone()
    if not row:
        conn.close(); return jsonify({"error": "记录不存在"}), 404
    # 仅本人或管理员可删除（管理员可删所有人的）
    if u["role"] != "admin" and row["user_id"] != u["id"]:
        conn.close(); return jsonify({"error": "只能删除自己上传的数据"}), 403
    c.execute("DELETE FROM orders WHERE import_id=?", (import_id,))
    c.execute("DELETE FROM daily_metrics WHERE import_id=?", (import_id,))
    c.execute("DELETE FROM product_stats WHERE import_id=?", (import_id,))
    c.execute("DELETE FROM imports WHERE id=?", (import_id,))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

# 模块加载即初始化（gunicorn 多 worker 也能确保表存在）
init_db()

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
