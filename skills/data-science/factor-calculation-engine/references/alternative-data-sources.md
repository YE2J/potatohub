# Alternative Data Sources for Factor Mining

Beyond the primary Tushare + moneyflow_daily pipeline, these data sources fill gaps and enable new factor signals.

---

## HiThink-Tech/Financial-API (同花顺官方)

**⭐ 136 | GitHub**: https://github.com/HiThink-Tech/Financial-API  
**定位**: 同花顺官方结构化金融数据服务，REST API + MCP + Python CLI + 本地DuckDB

### 差异化数据（Tushare 没有的）

| 接口 | 数据 | 因子用途 |
|------|------|----------|
| `limit-up-pool` | 涨停股票池（按日） | 涨停板因子、封板强度 |
| `limit-up-ladder` | 连板天梯矩阵（近30日×6板位） | 连板情绪因子、龙头识别 |
| `anomaly-analysis-list/stock` | 当日个股异动（急拉/急跌/放量等） | 异动因子、资金异动信号 |
| `dragon-tiger-list` | 龙虎榜（按板位类型） | 游资席位因子、龙虎榜溢价 |
| `hot-stock-list` | 市场热榜排名（日/小时） | 热度因子、动量因子 |
| `financials-indicators` | 聚合财务指标 | 基本面因子（ROE/PE/PB等） |

### 通用数据（与Tushare重叠但可作补充）

- `prices-snapshot` — 实时行情快照
- `prices-historical` — 日K线历史
- `financials-income/balance/cashflow` — 三大报表
- `index-catalog/constituents/snapshot/historical` — 指数相关
- `calendar-trading-days` — 交易日历
- `tickers-search/list` — 标的检索

### 安装要点

```bash
# 1. 克隆
cd ~/my_quant_system
git clone https://github.com/HiThink-Tech/Financial-API.git financial-api

# 2. 安装依赖（国内需清华源加速）
~/.pyenv/versions/3.11.11/bin/python -m pip install duckdb pyarrow \
  -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

# 3. 安装 marketdb 包（必须 --no-deps 避免 rich 版本冲突）
cd ~/my_quant_system/financial-api
~/.pyenv/versions/3.11.11/bin/python -m pip install --no-deps -e .

# 4. 配置 API Key
echo 'FUYAO_TOKEN=你的key' > ~/my_quant_system/financial-api/.env
# 注册地址: https://fuyao.aicubes.cn/admin/
```

### 关键坑

- **Rich版本冲突**: marketdb 锁定 `rich==13.9.4`，但 Hermes 需要 `rich==14.3.3`。必须用 `--no-deps` 安装 marketdb，然后手动修复 rich。
- **清华源**: 国内网络pip下载大包（duckdb 15MB, pyarrow 35MB）容易超时，必须走国内镜像。
- **`.env` 位置**: CLI 自动读 `toolkit/fuyao/` 下的 `.env`，如不生效可 `export FUYAO_TOKEN=xxx`。

### 基本用法

```bash
# 切换目录
cd ~/my_quant_system/financial-api

# 查日K线
~/.pyenv/versions/3.11.11/bin/python toolkit/fuyao/scripts/fuyao.py prices-historical --thscode 600519.SH

# 查涨停池
~/.pyenv/versions/3.11.11/bin/python toolkit/fuyao/scripts/fuyao.py limit-up-pool

# 查龙虎榜
~/.pyenv/versions/3.11.11/bin/python toolkit/fuyao/scripts/fuyao.py dragon-tiger-list --board-type all

# 构建本地 DuckDB 市场数据库
export FUYAO_TOKEN=xxx && ~/.pyenv/versions/3.11.11/bin/python bootstrap.py --api-only
```

---

## a-share-skill (by shouldnotappearcalm)

**⭐ 190 | GitHub**: https://github.com/shouldnotappearcalm/a-share-skill  
**定位**: A股数据分析与模拟交易的 AI Agent Skill 集合

### 可用子技能

| Skill | 功能 | 安装路径 |
|-------|------|----------|
| `a-share-data` | 实时行情、K线、技术指标、行业、指数、宏观 | `~/.hermes/skills/a-share/` |
| `a-share-paper-trading` | 模拟账户、下单、撤单、持仓、回测 | `~/.hermes/skills/a-share/` |
| `macd-second-golden-cross` | MACD二次金叉选股 | `~/.hermes/skills/a-share/` |
| `macd-trend-resonance-stock-picker` | 均线MACD趋势共振选股 | `~/.hermes/skills/a-share/` |
| `tuige-shortline-trading` | 短线交易触发/失效/风控/仓位 | `~/.hermes/skills/a-share/` |

### 安装方法

```bash
git clone https://github.com/shouldnotappearcalm/a-share-skill.git ~/my_quant_system/a-share-skill
mkdir -p ~/.hermes/skills/a-share
cp -R ~/my_quant_system/a-share-skill/a-share-data ~/.hermes/skills/a-share/
cp -R ~/my_quant_system/a-share-skill/a-share-paper-trading ~/.hermes/skills/a-share/
# ... 其他子技能同理
```

### 注意

- 数据源使用 akshare，与 Tushare 管线不同，不建议作为生产依赖
- 主要价值在 Skill 模块化设计理念和模拟交易系统参考
- `trend-pullback` 策略未开源

---

## GitHub Project Evaluation Criteria

当评估开源量化项目是否值得集成时，按以下维度筛选：

| 维度 | 最低标准 | 优选标准 |
|------|---------|---------|
| ⭐ Stars | ≥100 | ≥500（社区验证充分） |
| 最近更新 | 3个月内 | 1个月内（持续维护） |
| 语言 | Python | 纯pandas/numpy |
| 数据源 | 兼容Tushare/SQLite | 填补Tushare数据空白 |
| 依赖 | 轻量（<5个核心包） | 无版本锁定冲突 |
| 协议 | MIT/BSD/Apache | 非GPL（商业友好） |
| 用户偏好 | 自实现轻量路线 | 模块化可摘取，非重型框架 |

### 典型评估流程

1. 仓库信息（stars + 更新日期 + 语言）
2. README功能匹配度（解决了什么需求？）
3. 依赖分析（pyproject.toml / requirements.txt → 版本冲突检查）
4. 技术栈兼容（pandas版本、数据格式、数据库类型）
5. 值得借鉴的点（不一定要装，读源码提取有价值的部分即可）
