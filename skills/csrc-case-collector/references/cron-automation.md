# CSRC 采集 Cron 自动化配置 (2026-06-22)

## Cron Job

| 属性 | 值 |
|------|------|
| job_id | `2e89791a416c` |
| 名称 | CSRC 案例自动采集 |
| 定时 | `0 8 * * *` (每天8:00) |
| 模式 | `no_agent=false` (Agent驱动) |
| 工具集 | `web`, `terminal`, `file`, `skills` |

## 运行流程

```
Cron Agent
  1. web_search → site:csrc.gov.cn 行政处罚决定书 操纵
  2. 去重 (对比 discovered_urls.csv)
  3. 新URL写入 /tmp/csrc_new_urls_YYYYMMDD.txt
  4. bash ~/.hermes/scripts/csrc_pipeline.sh <urls_file>
     ├─ collect_csrc.py --urls → requests下载 (≥5s间隔)
     ├─ pipeline.py --screen-only → screener粗筛
     ├─ pipeline.py → 入库
     └─ 统计报告
  5. 追加新URL到 discovered_urls.csv
  6. 报告结果
```

## 关键约束

- **永远不要直接跑 `collect_csrc.py` 不带 `--urls`** → 会调 Selenium (无Chrome) 返回空
- `discover_urls_from_search()` 是 stub (空函数)，不要依赖
- URL发现只能通过 Agent 工具的 web_search
- 详情页固定模式: `http://www.csrc.gov.cn/csrc/c101928/c{ID}/content.shtml`
- 格式: 纯HTML，web_extract 或 requests + BeautifulSoup 均可解析

## 阈值

- 粗筛: 21分 (已校准)
- 江勇标杆 ~27分，刘洪涛 ~21分，夏德全 ~7分
- 低于21分的长线操纵案 (如余韩17分) → 需LLM精筛捞回

## 真实运行数据 (2026-06-23 批次)

| 指标 | 数值 |
|------|------|
| 搜索发现 URL | 9 条 |
| 下载成功率 | 9/9 (100%) |
| 下载间隔 | 7-8秒（符合≥5s要求） |
| 粗筛通过 | 3/16 文件（含预存文本） |
| 新增入库 | 1 篇（李鹏案, 〔2023〕49号, 评分23） |
| URL→案例 yield | ~11%（受 `<br>` 格式问题压制） |

**关键发现**: CSRC 大部分页面用 `<br>` 而非 `<p>` 分段，导致 screener 的"句均字数"硬性检查大量误杀。仅少数使用标准 `<p>` 排版的页面（如李鹏案）能通过。cron 运行时需要考虑这个格式差异，见 SKILL.md 的应对策略。

## wrapper脚本位置

`~/.hermes/scripts/csrc_pipeline.sh` (已 chmod +x)

### 已知脚本问题

`csrc_pipeline.sh` 第 52 行的 `score` 字段应改为 `quality_score`（与 DB schema 匹配），否则最终统计阶段会报 `no such column: score` 错误。
