# CSRC 网站 URL 结构（2026-06-21 勘验结果）

## 勘验过程

经过 browser 实测 + web_extract 验证 + web_search + GitHub Gist 交叉验证。

## 列表页

- **类型**：JS 渲染（需要 Selenium，纯 HTTP 不可用）
- **正确 URL**：
  ```
  http://www.csrc.gov.cn/csrc/c101925/zfxxgk_zdgk.shtml
  ?channelid=29ae08ca97d44d6ea365874aa02d44f6
  ```
- **翻页**：点击 `下一页` 链接
- **列表项 CSS**：`#codeId_list > ul > table > tbody > tr`（来源：2023年 GitHub Gist，可能需要更新）
- **发现时间**：2023年爬虫仍有用户反馈"太实用了"（2025-06），应仍有效

## 详情页

- **类型**：纯 HTML，`requests` 直接获取，**不需要 browser/Selenium**
- **URL 模式**：
  ```
  http://www.csrc.gov.cn/csrc/c101928/c{ID}/content.shtml
  ```
- **ID 类型**：
  - 纯数字：`c7521308`, `c5913605`, `c1042654`
  - UUID 风格：`c490192772b7748f58f089887c76bb662`
- **正文 CSS**：`div.detail-news`
- **面包屑**：首页 > 政务信息 > 政府信息公开 > 主动公开目录 > 按主题查看 > 行政执法 > 行政处罚

## ❌ 错误 URL（豆包方案提供）

```
http://www.csrc.gov.cn/csrc/c101928/zfxxgk_zdlist_{page}.shtml
```
→ **经验证返回首页内容，非处罚列表。不存在此路径。**

## 地方监管局

各地证监局也有独立处罚页面：
- `www.csrc.gov.cn/shanghai/`
- `www.csrc.gov.cn/hebei/c103646/zfxxgk_zdgk.shtml`
- 等 36 个地方局

## 引号格式注意

文号使用**中文直角引号** `〔〕`，非英文 `[]` 或中文全角 `【】`。

## 参考来源

- GitHub Gist: `goldluo126/718bb567c142b7194c7d10758a2a7221`（2023年爬虫）
- 该 Gist 最后验证有效：2025年6月用户评论"太实用了"
