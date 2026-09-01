# -*- coding: utf-8 -*-
"""
一键应用「京东/天猫识别修复」到服务器 app.py（不依赖 git/GitHub 推送）。
用法：在 PythonAnywhere Bash 中执行
    cd ~/company-data-dashboard && python apply_fix.py
执行后：cat -n app.py | sed -n '194,300p' 人工核对 + python -m py_compile app.py
"""
import re, io, sys

PATH = "app.py"
src = io.open(PATH, encoding="utf-8").read()
orig = src
applied = []

def sub(old, new, tag):
    global src
    if old not in src:
        print(f"[SKIP] {tag}：未找到匹配文本，可能已应用过。")
        return
    if new in src:
        print(f"[SKIP] {tag}：已存在，跳过。")
        return
    src = src.replace(old, new, 1)
    applied.append(tag)
    print(f"[OK] {tag}")

# 1) to_date：兼容范围日期 + 紧凑格式
sub(
    """    s = str(x).strip()
    m = re.search(r"(\\d{4})[-/年.](\\d{1,2})[-/月.](\\d{1,2})", s)
    if m: return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\\d{1,2})月(\\d{1,2})[日号]", s)""",
    """    s = str(x).strip()
    # 兼容「20260801~20260831」「2026-08-01~2026-08-31」等范围值：取起始日期
    s0 = re.split(r"[~至\\-\\u2013_]", s, maxsplit=1)[0] if ("~" in s or "\u81f3" in s or "\u2013" in s or "_" in s) else s
    # 兼容「20260801」这类紧凑格式
    m = re.fullmatch(r"(\\d{4})(\\d{2})(\\d{2})", s0)
    if m: return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(\\d{4})[-/年.](\\d{1,2})[-/月.](\\d{1,2})", s0)
    if m: return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\\d{1,2})月(\\d{1,2})[日号]", s)""",
    "1. to_date 范围日期"
)

# 2) detect_data_type 增强
sub(
    """    has_date = "日期" in cols
    has_promo = any(k in colstr for k in ["成交花费", "交易额", "投产比"])
    if has_order and has_promo:
        return "sales"   # 含订单号的混合表默认按销售处理；推广指标需手动选 promo_* 上传
    if has_order: return "sales"
    if has_date and has_promo: return "promo_daily"
    if has_promo: return "promo_product"
    return "sales\"""",
    """    has_date = bool(find_col(cols, ["日期", "时间", "点击时间", "成交时间", "支付时间"]))
    has_promo = any(k in colstr for k in ["成交花费", "交易额", "投产比", "花费", "点击"])
    has_gmv = any(k in colstr for k in ["成交金额", "交易额", "成交额"])
    has_orderqty = any(k in colstr for k in ["成交单量", "成交笔数", "订单数", "下单单量", "直接订单行"])
    if has_order and has_promo:
        return "sales"   # 含订单号的混合表默认按销售处理；推广指标需手动选 promo_* 上传
    if has_order: return "sales"
    # 分天汇总表：有日期/时间列 + 交易额或单量（京东/淘宝「交易概况」「分天下载」「推广账户日报」）
    if has_date and (has_promo or has_gmv or has_orderqty): return "promo_daily"
    if has_promo: return "promo_product"
    return "sales\"

def _decide_data_type(gtype, df):
    \"\"\"综合文件名推断(gtype)与列结构检测(detect)决定 data_type。
    列结构最可靠，优先采用；仅当列检测判为泛化 sales 而文件名明确推广时才用文件名。\"\"\"
    dt = detect_data_type(df)
    if dt != "sales":
        return dt
    if gtype in ("promo_daily", "promo_product"):
        return gtype
    return "sales\"""",
    "2. detect_data_type 增强 + _decide_data_type"
)

# 3) store_promo_daily 拓宽列名
sub(
    """    date_col = find_col(cols, ["日期"])
    cost_col = find_col(cols, ["成交花费(元)", "总花费(元)", "成交花费"])
    sales_col = find_col(cols, ["交易额(元)", "净交易额(元)", "交易额"])
    roi_col = find_col(cols, ["实际投产比", "净实际投产比", "投产比"])
    ord_col = find_col(cols, ["成交笔数", "净成交笔数"])
    exp_col = find_col(cols, ["曝光量"])
    clk_col = find_col(cols, ["点击量"])""",
    """    date_col = find_col(cols, ["日期", "时间"])
    cost_col = find_col(cols, ["成交花费(元)", "总花费(元)", "成交花费", "花费", "推广花费"])
    sales_col = find_col(cols, ["交易额(元)", "净交易额(元)", "交易额", "成交金额", "总订单金额",
                                "直接订单金额", "成交额", "支付金额"])
    roi_col = find_col(cols, ["实际投产比", "净实际投产比", "投产比", "ROI"])
    ord_col = find_col(cols, ["成交笔数", "净成交笔数", "成交单量", "下单单量", "总订单行",
                              "直接订单行", "订单数", "支付子订单数"])
    exp_col = find_col(cols, ["曝光量", "展现数", "曝光数"])
    clk_col = find_col(cols, ["点击量", "点击数"])""",
    "3. store_promo_daily 列名拓宽"
)

# 4) process_upload：detect 优先于文件名
sub(
    """                    data_type = gtype or detect_data_type(sample)""",
    """                    data_type = _decide_data_type(gtype, sample)""",
    "4a. process_upload xlsx detect优先"
)
sub(
    """                df = read_any(tmp)
                if not data_type:
                    data_type = gtype or detect_data_type(df)""",
    """                df = read_any(tmp)
                if not data_type:
                    data_type = _decide_data_type(gtype, df)""",
    "4b. process_upload csv detect优先"
)
sub(
    """            df = read_any(tmp)
            if not data_type:
                data_type = gtype or detect_data_type(df)""",
    """            df = read_any(tmp)
            if not data_type:
                data_type = _decide_data_type(gtype, df)""",
    "4c. process_upload 异常分支 detect优先"
)

if src == orig:
    print("\n没有做任何修改。若此前已应用过本补丁属正常。")
else:
    io.open(PATH, "w", encoding="utf-8").write(src)
    print("\n已写入 app.py。应用了 %d 处：" % len(applied))
    for a in applied:
        print("  -", a)

# 语法校验
import py_compile
try:
    py_compile.compile(PATH, doraise=True)
    print("\n语法检查通过 ✔  app.py 无错误")
except Exception as e:
    print("\n语法检查失败:", e)
