# A股数据源测试结果 (2026-06-11)

测试环境: macOS, 中国大陆网络, Hermes Agent

## 测试结果汇总

### ✅ 可用

#### 1. 腾讯实时行情
```
GET https://qt.gtimg.cn/q=sz000001
```
- 状态: 200 OK
- 响应速度: 快 (~0.1s)
- 数据格式: `~` 分隔的文本, 位置 [39] = PE-TTM
- 批量查询: 用逗号分隔多代码, 如 `q=sz000001,sh600519,sz300750`

#### 2. 腾讯历史K线 (前复权)
```
GET http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz000001,day,2020-01-01,2026-06-11,1000,qfq
```
- 状态: 200 OK
- 响应速度: 快 (~0.3s)
- 返回格式: `[日期, 开盘, 收盘, 最高, 最低, 成交量]`
- **注意**: 除权除息日可能出现第7个字段(分红信息字典), 如 `{'nd': '2024', 'fh_sh': '3.62', 'djr': '2025-06-11', 'cqr': '2025-06-12', 'FHcontent': '10派3.62元'}`。解析时需截取前6列: `row[:6]`。
- 每段上限: ~640条
- 周线: `week` 替换 `day`, 2016-2026 (533条) 单次拉满
- 月线: `month` 替换 `day`, 2000-2026 (316条) 单次拉满

测试代码:
```python
import requests
headers = {'User-Agent': 'Mozilla/5.0'}
url = 'http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz000001,week,2020-01-01,2026-06-11,500,qfq'
r = requests.get(url, headers=headers, timeout=10)
data = r.json()
kline = data['data']['sz000001']['qfqweek']
```

#### 3. 同花顺 EPS (通过 akshare)
```python
import akshare as ak
df = ak.stock_financial_abstract_ths(symbol='000001', indicator='按报告期')
```
- 状态: 可用
- 响应速度: 快, 平均 0.14s/股
- 覆盖范围: 全部测试股(9/9)成功
- 数据深度: 约 36-121 条记录/股 (取决于上市时间)
- 限流: 无可见限制, 10股连续请求1.35s完成

### ❌ 不可用

#### 1. 东方财富 push2 API
```
https://push2.eastmoney.com/api/qt/stock/kline/get?secid=0.000001&...
```
- 错误: `RemoteDisconnected('Remote end closed connection without response')`
- 原因: 网络层连接被重置 (可能 GFW 或 ISP 限制)

#### 2. 雪球 API
```
https://stock.xueqiu.com/v5/stock/chart/kline.json?symbol=SZ000001&...
```
- 错误: 400 Bad Request
- 原因: 需要 Cookie/登录认证, 匿名请求被拒绝

#### 3. 新浪财经 (163.com)
```
https://quotes.money.163.com/service/chddata.html?code=1000001&start=...
```
- 错误: 502 Bad Gateway

#### 4. 东方财富 (akshare)
```python
ak.stock_zh_a_hist(...)        # ConnectionError
ak.stock_individual_info_em()  # ConnectionError
```
- 全部东方财富源头的 akshare 函数均不可用

### ⏭️ 未深入测试

#### 新浪实时
```
https://hq.sinajs.cn/list=sz000001
```
- 200 OK (实时行情), 但未测试历史数据

#### yfinance
- A股数据不完整, 未测试

## PE-TTM 通道计算验证

以 **平安银行 (000001)** 为例:

### 数据
- EPS(累积值): 2025Q1=0.62, 2025H1=1.18, 2025Q3=1.87, 2025FY=2.07, 2026Q1=0.67
- 单季度: Q1_25=0.62, Q2=0.56, Q3=0.69, Q4=0.20, Q1_26=0.67
- TTM(2026-03-31) = 0.56+0.69+0.20+0.67 = **2.12**
- 当日收盘价 = 11.30
- PE_TTM = 11.30/2.12 = **5.33**
- 腾讯实时PE(TTM) = **5.09** (微小差异来自EPS统计口径)
