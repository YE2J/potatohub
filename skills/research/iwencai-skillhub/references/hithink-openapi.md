# Hithink OpenAPI 调用规范

## 端点

```
POST https://openapi.iwencai.com/v1/query2data
```

## 认证

API Key 从环境变量 `IWENCAI_API_KEY` 读取（格式 `sk-proj-...`）。
必须在 `~/.zshrc` 和 `~/.hermes/.env` 两处配置。

## 请求头

```
Authorization: Bearer <IWENCAI_API_KEY>
Content-Type: application/json
X-Claw-Call-Type: normal
X-Claw-Skill-Id: <技能名>
X-Claw-Skill-Version: <版本号>
X-Claw-Plugin-Id: none
X-Claw-Plugin-Version: none
X-Claw-Trace-Id: <64字符hex>
```

`X-Claw-Trace-Id` 每次请求必须新生成：`secrets.token_hex(32)`。

## 请求体

```json
{
  "query": "改写后的自然语言查询",
  "page": "1",
  "limit": "10",
  "is_cache": "1",
  "expand_index": "true"
}
```

## 响应解析

```python
datas = result.get("datas", [])           # 当前页数据列表
code_count = result.get("code_count", 0)  # 符合条件的总记录数
# 每个 item 的键是中文列名（如 "股票代码"、"股票简称"、"股东名称"等）
for item in datas:
    code = item.get("股票代码")
    name = item.get("股票简称")
```

若 `code_count > len(datas)`，需翻页（`page=2,3,...`）。
若 `datas` 为空，放宽条件重试最多2次。

## 已安装技能

| 技能 | slug | 版本 | 领域 |
|------|------|------|------|
| 行情数据查询 | hithink-market-query | 1.0.0 | 实时价格/涨跌幅/技术指标/资金流向 |
| 财务数据查询 | hithink-finance-query | 1.0.0 | 营收/净利润/ROE/负债率/现金流/PE/PB |
| 股东股本查询 | hithink-management-query | 1.0.0 | 股本结构/前十大股东/实控人/高管/质押 |
| 机构研究评级 | hithink-insresearch-query | 1.0.0 | 研报评级/业绩预测/券商金股/ESG/信用评级 |
| 研报搜索 | report-search | 2.0.0 | 投研机构研报全文搜索+Python工具链 |
