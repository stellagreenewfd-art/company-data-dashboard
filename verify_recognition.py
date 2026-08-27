import os, importlib.util, json
os.environ["DB_PATH"] = "/tmp/recog_test.db"
spec = importlib.util.spec_from_file_location("app", "/Users/qinaqiang/WorkBuddy/2026-08-27-10-11-06/company-data-dashboard/app.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
find_col = app.find_col

import pandas as pd, warnings
warnings.filterwarnings("ignore")
df = pd.read_excel("/Users/qinaqiang/Downloads/8.1-8.25红书鸡蛋销售表格.xlsx", sheet_name="订单信息", engine="openpyxl")
orig_cols = list(df.columns)
print("原始表列数:", len(orig_cols))

# store_sales 的字段候选（与 app.py 当前一致）
fields = {
    "订单日期 date": ["订单成交时间","订单付款时间","支付时间","下单时间","成交时间","订单创建时间","日期"],
    "实收/支付金额 pay": ["商家实收金额(元)","商家实收金额","商家应收金额(元)(支付金额)","商家应收金额","用户实付金额(元)","买家实付金额","用户实付金额","买家应付货款","商品总价(元)","总金额","支付金额","实付金额"],
    "商品数量 qty": ["商品数量(件)","宝贝总数量","SKU件数","数量","件数"],
    "订单状态 status": ["订单状态","售后状态","状态"],
    "退款金额 refund": ["退款金额"],
    "商品名称 prod": ["商品标题","商品名称","SKU名称","选购商品","商品","标题","规格名称"],
    "店铺 shop": ["店铺名称","店铺"],
    "省份 prov": ["省","收货地址","收货省"],
    "订单ID oid": ["订单号","订单编号","主订单编号","订单ID","订单","交易编号","TradeNo"],
    "达人ID inf_id": ["达人ID","达人id","达人编号","主播ID"],
    "达人名称 inf_name": ["达人名称","达人","达人昵称","主播","博主"],
}

print("\n===== 原始表列 -> 系统识别字段映射 =====")
recognized = set()
for fname, cands in fields.items():
    hit = find_col(orig_cols, cands)
    if hit:
        recognized.add(hit)
        print(f"  [识别] {fname:28s} <- 「{hit}」")
    else:
        print(f"  [未匹配] {fname:28s} (候选均不在表中)")

print("\n===== 原始表中【未被任何字段识别】的列（仅进 extras JSON，不可聚合查询）=====")
for c in orig_cols:
    if c not in recognized:
        print(f"  - 「{c}」")

print("\n===== promo_daily 需要的列（曝光/点击/投产比）是否在原始表中 =====")
promo_fields = {
    "日期": ["日期"], "成交花费": ["成交花费(元)","总花费(元)","成交花费"],
    "交易额": ["交易额(元)","净交易额(元)","交易额"], "投产比": ["实际投产比","净实际投产比","投产比"],
    "成交笔数": ["成交笔数","净成交笔数"], "曝光量": ["曝光量"], "点击量": ["点击量"],
}
for fname, cands in promo_fields.items():
    hit = find_col(orig_cols, cands)
    print(f"  {'[有]' if hit else '[缺]'} {fname:8s} <- {hit or '无'}")
