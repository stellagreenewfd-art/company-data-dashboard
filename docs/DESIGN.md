# 公司多平台经营数据看板 · 系统设计文档

> 版本 v2.0（2026-09-02）· 基于 13 份真实平台导出文件（京东/天猫/拼多多/抖音/小红书）重构

---

## 一、系统目标

运营每天从各平台后台导出报表 → 上传到系统 → **自动识别、自动入库、自动更新看板**。
看板支持 **分平台 / 分类目 / 分店铺 / 分时间段** 查询销售、订单、广告投放、ROI 等核心指标，历史数据永久累积。

---

## 二、13 份源文件 → 四类数据形态

| 形态 | data_type | 典型文件 | 粒度 | 存储表 |
|---|---|---|---|---|
| 订单明细 | `sales` | 天猫订单、抖音订单、PDD 订单、小红书订单 | 每行一订单 | `orders` |
| 店铺交易概况分天 | `shop_daily` | 京东自营/POP 交易概况分天下载 | 每天一行（GMV/单量/访客） | `daily_metrics(metric_type='trade')` |
| 广告推广分天 | `promo_daily` | PDD 推广汇总 sheet、京东推广账户报表、天猫营销场景报表 | 每天×场景一行 | `daily_metrics(metric_type='promo', scene=...)` |
| 推广商品维度 | `promo_product` | PDD 推广商品分天 sheet | 每商品×每天一行 | `product_stats` |

**关键设计决策：店铺交易（trade）与广告推广（promo）分表存储。**
京东「交易概况」只有 GMV、没有广告花费——旧系统把它塞进推广槽位，导致 GMV 被当成"推广成交额"、ROI 口径错乱。v2 拆开后：销售额趋势 = 订单明细汇总，缺订单明细的 日×平台×品类 用 trade GMV 自动补位。

---

## 三、数据模型（SQLite）

### orders（订单明细）
`UNIQUE(platform, category, order_id)` —— 重复上传同一订单自动覆盖，不重复计数。
核心列：order_date / pay_amount / item_count / status / is_refund / refund_amount /
product_name / **shop（店铺）** / province / influencer_id / influencer_name（达人）/
channel / coop_type / commission_base / commission_rate / commission_amount / extras（原始行 JSON 全量留底）

### daily_metrics（分天指标，v2 重建）
`UNIQUE(platform, shop, category, data_date, metric_type, scene)`
- `metric_type='trade'`：gmv / order_count / visitors / exposure(浏览量)
- `metric_type='promo'`：promo_cost / promo_sales / roi / order_count / exposure / clicks / **scene（场景：关键词推广/货品全站推广…）**
- 旧库自动迁移：有花费→promo，无花费仅有金额→trade（自动修正历史京东数据口径）

### product_stats（推广商品维度）
`UNIQUE(platform, category, product_id, period)`，period 支持行内日期（PDD 商品分天 = 商品×天粒度）。

### imports（上传台账）
每次上传一行：文件名/平台/店铺/品类/类型/行数/数据区间/上传人/时间，支持整条删除并级联清数据。

---

## 四、识别管线（process_upload）

```
文件名推断(平台/品类/类型/店铺)
   ↓ Excel 逐 sheet 读取（PDD 双 sheet 全部入库，不再二选一）
列结构 detect_data_type（五类，列结构最可靠）
   ↓ 内容推断兜底（平台特征词/品类关键词/店铺名称列）
店铺推断（SHOP_HINTS + 文件名前缀 + 店铺名称列，过滤「店铺优惠折扣」误命中）
   ↓ 按形态分流入库（INSERT OR REPLACE 幂等）
上传回执：每 sheet 识别结果 + 行数 + 数据区间 + 未识别字段警示
```

**去重与幂等**：同一天同一平台同一店铺同一类型重复上传 = 覆盖更新，看板数字不膨胀。
**口径优先级**：promo 以账户级分天为权威；商品级仅在该平台×品类无账户级数据时补充（防 PDD 双 sheet 重复计数）。

---

## 五、看板功能清单（对照成熟 BI 看板）

| 功能 | 状态 | 说明 |
|---|---|---|
| KPI 总览 | ✅ 增强 | 销售额、净销售额(扣退款)、订单、AOV、整体 ROI、**费比**、**环比**、退款额/率 |
| 销售 vs 推广趋势图 | ✅ | 按日，可拆分平台/品类 |
| 平台对比 / 品类占比 | ✅ | 柱状 + 环形 |
| **平台×类目透视表** | ✅ 新增 | 销售额/订单/花费/费比/ROI 一表看清 |
| **推广场景效果表** | ✅ 新增 | 关键词推广 vs 货品全站推广 分场景 ROI |
| **店铺对比表** | ✅ 新增 | 京东自营 vs POP GMV/单量/访客 |
| **达人带货榜** | ✅ 新增 | 小红书/抖音达人销售额、订单、佣金 TOP20 |
| 渠道/合作类型分布 | ✅ | 直播/买手合作等 |
| 商品推广 TOP 榜 | ✅ | 商品级 ROI 排行 |
| 每日经营明细 + CSV 导出 | ✅ | UTF-8 BOM 防 Excel 乱码 |
| **数据覆盖检查** | ✅ 新增 | 近 14 天每个平台×品类「订/店/推/缺」一目了然 |
| 导入记录台账 | ✅ | 可追溯、可删除级联清理 |
| 多用户 + 审核 | ✅ | 管理员/成员，注册需审核 |
| 环比/同比 | 🟡 环比已有 | 同比需累积满一年数据后自然可用 |
| 毛利/成本 | ⬜ 待补 | 需补商品成本表（下一步可加"成本维护"页） |
| 库存周转 | ⬜ 待补 | 需库存数据源 |
| 自动定时抓取 | ⬜ 待补 | 当前为人工导出上传；平台 API/RPA 是 v3 方向 |

---

## 六、运营每日上传 SOP

1. 各平台后台导出昨天的报表（订单明细必传；推广报表、交易概况有就传）。
2. 打开看板 → 上传区：平台必选；品类可留空自动识别（文件名规范时）；店铺可留空自动识别。
3. 一次多选/拖入全部文件 → 「批量上传并入库」。
4. 看回执：每份文件的 平台/店铺/品类/类型/行数/数据区间；有红色"未识别字段"时检查是否选错类型。
5. 看「数据覆盖检查」卡片：哪个平台哪天标"缺"就补传哪份。

**重复上传安全**：同一天数据重复传只会覆盖更新，不会翻倍。

---

## 七、上线步骤（PythonAnywhere）

```bash
cd ~/company-data-dashboard
git fetch origin && git reset --hard origin/main   # 或上传 app.py / static/index.html
touch /var/www/yjdata2026_pythonanywhere_com_wsgi.py
```
Web 页点 **Reload**。首次启动自动完成 daily_metrics v2 迁移（旧数据口径自动修正）。
迁移后建议重新上传京东交易概况文件，让 shop 维度补全。

> 遗留：GitHub PAT 需 revoke；管理员密码建议修改。
