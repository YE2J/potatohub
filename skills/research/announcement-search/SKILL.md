---
name: announcement-search
description: 支持A股、港股、基金、ETF等金融标的公告的查询，同时公告类型包括不限于定期财务报告、分红派息、回购增持、资产重组等等。
---
# 公告搜索技能

## 版本
当前技能版本：1.0.0

## 技能概述
本技能是一个金融公告搜索引擎，通过调用同花顺问财的公告搜索接口，帮助用户查询A股、港股、基金、ETF等金融标的的最新公告信息。

## 技术实现

### API接口
- **Base URL**: `https://openapi.iwencai.com`
- **接口路径**: `/v1/comprehensive/search`
- **请求方式**: POST
- **认证方式**: Bearer Token，从环境变量 `IWENCAI_API_KEY` 读取

### 必需请求头
| Header | 取值 |
|--------|------|
| `Authorization` | `Bearer $IWENCAI_API_KEY` |
| `X-Claw-Skill-Id` | `announcement-search` |
| `X-Claw-Skill-Version` | `1.0.0` |
| `X-Claw-Trace-Id` | 64字符 hex（`openssl rand -hex 32`） |

### 请求体
```json
{
  "channels": ["announcement"],
  "app_id": "AIME_SKILL",
  "query": "搜索关键词"
}
```

### 响应格式
`data` 数组，每项含 `title`, `summary`, `url`, `publish_date`。
