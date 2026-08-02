# CSRC 网站 URL 结构勘验记录

> 勘验日期：2026-06-21
> 方法：web_search + web_extract + browser_navigate（CSRC 网站对 browser 全部超时）

## 已验证可用的模式

### 详情页（纯 HTML，web_extract 可用）
```
http://www.csrc.gov.cn/csrc/c101928/c{ID}/content.shtml
```

**ID 类型**：
- 纯数字：`c7521308`、`c5913605`、`c7461383`、`c1782468`
- UUID 风格：`c490192772b7748f58f089887c76bb662`

**正文选择器**：`div.detail-news`（GitHub 爬虫确认 + web_extract 验证）

**页面结构**：
- 面包屑：首页 > 政务信息 > 政府信息公开 > 主动公开目录 > 按主题查看 > 行政执法 > 行政处罚
- 元数据表格：索引号、分类、发布机构、发文日期、名称、文号
- 正文：当事人信息 → 违法事实 → 法律定性 → 申辩复核 → 处罚决定

### 列表页（需要 JavaScript，Selenium 方案）
```
http://www.csrc.gov.cn/csrc/c101925/zfxxgk_zdgk.shtml?channelid=29ae08ca97d44d6ea365874aa02d44f6
```

**为什么必须 Selenium**：列表数据通过 JavaScript 动态加载，纯 HTTP 请求只返回通用信息公开页面。

**列表行选择器**：`#codeId_list > ul > table > tbody > tr`
**链接提取**：`row.find('a', href=True)['href']`
**翻页**：点击"下一页"链接

### 路径层级关系
```
/csrc/c100032/ — 政府信息公开入口
  └── /c100035/ — 主动公开目录
      └── /c101793/ — 按主题查看
          └── /c101925/ — 行政执法
              └── /c101928/ — 行政处罚（详情页在此目录下）
```

## ❌ 已验证为错误的 URL

| URL | 问题 |
|-----|------|
| `/csrc/c101928/zfxxgk_zdlist.shtml` | 豆包方案提供，不返回处罚列表 |
| `/csrc/c101928/zfxxgk_zdlist_{page}.shtml` | 同上，分页模式不存在 |

## 地区监管局

各地方证监局也有独立的处罚决定书页面：
- `www.csrc.gov.cn/shanghai/`
- `www.csrc.gov.cn/hebei/c103646/zfxxgk_zdgk.shtml`

## 参考爬虫

GitHub Gist: `goldluo126/718bb567c142b7194c7d10758a2a7221`
- 创建于 2023年12月
- 使用 Selenium + BeautifulSoup
- 验证过上述列表页 URL 和选择器
- 输出为 Excel

## 访问注意事项

1. CSRC 网站对 **browser_navigate 工具全部超时**，web_extract 正常
2. 列表页必须用 Selenium（需要 Chrome/Chromedriver）
3. web_extract 提取详情页效果很好，全文 markdown 格式
4. 页面编码为 UTF-8，中文正常
