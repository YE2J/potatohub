# arXiv q-fin 监控 2026-09 故障复盘与修复（实测证据）

> 背景：cron 6921de23673c 自 2026-08-24 起连续 11 天"API 返回 200 条但 24h 窗口内 0 条"，09-04 当天 API `Connection reset by peer` 脚本 exit 1。

## 诊断链条（含被推翻的假说）

1. cron 输出 09-04 报告**猜测**"top-200 被修订版(updated)论文挤占"。
2. 实测证伪：同一查询 top-200 里修订版仅 20/200=10%；top-200 的 published 覆盖 2026-08-02~09-03 整月，每天 1~12 条——容量充足，修订版远不足以挤出。
3. 真实根因 = **24h 滚动窗口与公告时点错配**：脚本每日 03:10 CST = 前日 19:10 UTC，arXiv 约 20:00 UTC 公告当天新论文 → 运行时当天批次尚未进 API；窗口上沿(now)又把"昨天公告批"中提交较早的切掉。
4. 佐证：08-23 22:50 手动跑窗口=72h 抓到 2 篇；改 24h 后连续 11 次 0。
5. 09-04 的 Connection reset 是独立网络事件（非根因）：状态页正常、全边缘 IP 即时 RST、example.com 基线正常 → 出口路径/IP 级封锁；无重试逻辑 + 每日固定整点 = 机器人特征。

## 修复方案（2026-09-04 已落地）

| 项 | 旧版 | 修复版 |
|---|---|---|
| 查询 | sortBy=submittedDate top-200 + 本地 24h 过滤 | `submittedDate:[起 TO 止]` 服务端过滤（官方推荐） |
| 网络 | 单次失败 exit 1 | 退避重试 60s/300s/900s（仅网络类错误；HTTPError 不重试） |
| 窗口 | 固定 24h | 默认 7 天；`ARXIV_SINCE_DAYS`/`ARXIV_SINCE_DATE` 覆盖 |
| 调度 | 每日 03:10 | 每周六 02:00（公告后 22h，非整点密集） |
| 分级 prompt | 每篇深读 | 两级筛选：meta.json 摘要初筛 → 疑似 A/B 才读 paper.md 120+80 行 |

## 实测数字（供未来比对）

- 修复版冒烟（ARXIV_SINCE_DATE=202609031200）：2 条命中、下载+HTML 转 md 正常、NEW_PAPERS=2
- 补跑（ARXIV_SINCE_DATE=202608200000）：新增 76 篇、耗时约 2 分钟、exit 0；索引从 8 篇→86 篇
- 批量分级 78 篇（2 worker 并行，各读 meta.json 摘要初筛+17 篇深读）：A=3（23808 MinervaScore / 23393 KellyBoost / 00943 IlliQaR）、B=11、C=12、D=50、缺失 0
- 台账校验：`search_files pattern='^\| 2026-' TRIAGE.md` count = 86 = INDEX 论文行数

## 批量分级操作要点（78 篇实测）

- 拆分：read INDEX.md（published 排序）→ 按行均分给 N 个 worker，每个 worker 拿到**精确 ID 清单**（省得 worker 自己 diff INDEX）
- worker 指令：读 meta.json 摘要初筛；疑似 A/B 才 read paper.md（HTML 导出前 ~45 行是导航样板，正文从 ~50 行起）；诚实纪律=每篇必须真实 read 才判级、缺失标 ⚠️
- worker 输出：分级 markdown 表（日期/ID/标题≤35字/评级/一句话理由+处置）+ A/B 沉淀要点 + 缺失清单；写文件返回路径（大 JSON summary 会被截断，须 execute_code json.loads 解包）
- 主会话：统一 append TRIAGE.md（评级列 **A** 等，状态：A/B=⏳ 待拍板、C=⏳ pending、D=✅ archived）；完成后 count 校验
- 漏篇教训：8/31 有 10 篇（8 篇 2608.31xxx + 2 篇 2609.00xxx 前缀但 published=8/31），凭日期记忆切分漏了 2 篇 → 切分必须对着 INDEX.md 现读行

## A 级 skill 化（子代理草稿流程）

1. 子代理精读论文（正文 50 行起）+ skill_view 参考现有同族 skill（nonparametric-var / a-share-strategy-research-flow）学 frontmatter 惯例
2. 要求：公式/常数必须从 paper.md 实际提取，不确定标 ⚠️"论文未给"；SKILL.md 写入草稿文件返回路径+要点+3 条易错点
3. 主会话 read 草稿审查 → 落盘 `~/.hermes/skills/<category>/<name>/SKILL.md`（cp 即可，skill 系统文件系统+frontmatter 驱动）→ skill_view 验证 readiness_status=available
4. description 首 57 字符内自包含触发句；正文中文、步骤化、含 A股数据源映射/验证方法/陷阱

## 2026-09-04 产出 skill

- `minerva-backtest-robustness`（2608.23808）：五门 DSR/PBO/SPA/MinTRL/regime → Seal → 0-100；Python 骨架+SIG_EFF 冻结常数；陷阱含"统计支持≠盈利概率（论文自身真实市场预注册 null）"
- `a-share-liquidity-tail-risk`（2609.00943）：realized Amihud × MEM-J → IlliQaR 尾部分位；S0-S8 流程+Berkowitz 覆盖率回测；A股三压力期（2015/2016/2024）验收锚点
