#!/usr/bin/env python3
"""
独立估值子进程 — 被Web API调用，绕过matplotlib/uvicorn冲突。
通过子进程运行，父进程不会被matplotlib卡死。

用法：
    python3 run_valuation_subprocess.py '["000988","300308"]'

输出格式：
    含 ---RESULT_JSON--- 标记，标记之间的内容为JSON。
    空输出 = 无结果。
"""
import sys, os, json, sqlite3, warnings
warnings.filterwarnings("ignore", category=Warning)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd
import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import akshare as ak

DB_PATH = "stock_data.db"
CHART_DIR = "reports/valuation"
os.makedirs(CHART_DIR, exist_ok=True)

# 确保数据库表存在
_init_conn = sqlite3.connect(DB_PATH)
_init_conn.executescript("""CREATE TABLE IF NOT EXISTS valuation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT, stock_name TEXT, run_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    current_price REAL, pe_ttm REAL, roe REAL, growth_rate REAL,
    channel_position REAL, min_pe REAL, median_pe REAL,
    consensus_fair REAL, consensus_low REAL, consensus_high REAL,
    safety_margin REAL, rating TEXT, stars TEXT,
    report_text TEXT, chart_path TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);""")
_init_conn.close()

def evaluate(code):
    name = _name(code)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=400)

    # 从 SQLite 获取K线
    conn = sqlite3.connect(DB_PATH)
    df_sql = pd.read_sql("SELECT date,open,high,low,close,volume FROM daily_kline WHERE stock_code=? ORDER BY date", conn, params=(code,))
    conn.close()
    if df_sql.empty:
        raise ValueError(f"无数据: {code}")
    df_sql['date'] = pd.to_datetime(df_sql['date'], format='%Y%m%d')
    df = df_sql[(df_sql['date'] >= pd.Timestamp(start_date)) & (df_sql['date'] <= pd.Timestamp(end_date))].copy()
    if len(df) < 60:
        raise ValueError(f"数据不足({len(df)}行)")

    # EPS → TTM
    eps_df = _eps(code)
    qd = eps_df['report_date'].values; qv = eps_df['standalone_eps'].values
    ttm = []
    for d in df['date'].values:
        idx = np.where(qd <= np.datetime64(d))[0]
        ttm.append(float(qv[idx[-4:]].sum()) if len(idx) >= 1 else 0.0)
    df['ttm_eps'] = ttm
    df['pe_ttm'] = np.where(df['ttm_eps'] > 0, df['close'] / df['ttm_eps'], np.nan)

    pe_pos = df['pe_ttm'].dropna()
    pe_pos = pe_pos[pe_pos > 0]
    if len(pe_pos) < 20:
        raise ValueError(f"有效PE不足({len(pe_pos)})")

    min_pe, median_pe = float(pe_pos.min()), float(pe_pos.median())
    step = 0.5 * (median_pe - min_pe)
    bands = {'b1': min_pe, 'b2': min_pe+step, 'b3': median_pe, 'b4': min_pe+3*step, 'b5': min_pe+4*step}

    # 画图
    plt.rcParams.update({'font.family': ['Heiti TC','PingFang HK','STHeiti','sans-serif'], 'axes.unicode_minus': False})
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor('#f8f9fa'); ax.set_facecolor('#ffffff')
    dates, closes, ttm_v = df['date'].values, df['close'].values, df['ttm_eps'].values
    dm = ttm_v > 0
    colors = ['#e74c3c','#e67e22','#f1c40f','#2ecc71','#2980b9']
    labels = ['低估值','偏低','中位','偏高','高估值']
    bkeys = ['b1','b2','b3','b4','b5']
    for i, bk in enumerate(bkeys):
        pl = np.where(dm, bands[bk] * ttm_v, np.nan)
        ax.plot(dates, pl, color=colors[i], lw=1, alpha=0.85, ls='--', label=f'{labels[i]}({bands[bk]:.1f}x)')
    ax.plot(dates, closes, color='#1a1a2e', lw=2, alpha=1, label='收盘价', zorder=5)
    bot = bands['b1'] * ttm_v
    ax.fill_between(dates, closes, bot, where=(closes <= bot), color='#e74c3c', alpha=0.25, label='低于底部')
    ax.legend(loc='upper left', fontsize=9, ncol=2)
    ax.grid(True, alpha=0.3, ls=':'); ax.set_ylabel('股价(元)')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right', fontsize=8)
    fig.tight_layout()
    cp = os.path.join(CHART_DIR, f"{code}.png")
    fig.savefig(cp, dpi=150, bbox_inches='tight'); plt.close(fig)

    # 估值指标
    price = float(closes[-1])
    pe_val = float(df['pe_ttm'].iloc[-1]) if not pd.isna(df['pe_ttm'].iloc[-1]) else 0
    lp = bands['b1'] * ttm_v[-1] if dm[-1] else 0
    hp = bands['b5'] * ttm_v[-1] if dm[-1] else 0
    ch_pct = max(0, min(100, (price - lp) / (hp - lp) * 100)) if hp > lp else 50
    fair = bands['b3'] * ttm_v[-1] if dm[-1] else 0
    sm = (fair - price) / fair if fair > 0 else 0
    rating, stars = ("强烈推荐","⭐⭐⭐⭐⭐") if sm > 0.2 else ("推荐","⭐⭐⭐⭐") if sm > 0.05 else ("中性","⭐⭐⭐") if ch_pct < 70 else ("谨慎","⭐⭐")

    txt = f"📊 {name}({code}) PE通道\n当前价:{price:.2f} PE:{pe_val:.1f}x 通道:{ch_pct:.0f}%\n合理:{fair:.2f} 安全边际:{sm*100:.1f}% 评级:{stars}{rating}"
    print(txt, flush=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""INSERT INTO valuation_results(stock_code,stock_name,current_price,pe_ttm,channel_position,min_pe,median_pe,consensus_fair,consensus_low,consensus_high,safety_margin,rating,stars,report_text,chart_path)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (code, name, price, pe_val, ch_pct/100, min_pe, median_pe, fair, lp, hp, sm, rating, stars, txt, f"/reports/valuation/{code}.png"))
    conn.commit(); rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]; conn.close()
    return {"id": rid, "stock_code": code, "stock_name": name, "current_price": price, "pe_ttm": pe_val, "consensus_fair": fair, "rating": rating}

def _name(code):
    prefixed = ("sh" if code.startswith(("6","5","8","9")) else "sz") + code
    try: return requests.get(f"https://qt.gtimg.cn/q={prefixed}", timeout=5).text.split("~")[1].strip()
    except: return code

def _eps(code):
    df = ak.stock_financial_abstract_ths(symbol=code, indicator='按报告期')
    raw = df[['报告期','基本每股收益']].copy(); raw.columns=['report_date','cum_eps']
    raw['report_date'] = pd.to_datetime(raw['report_date'])
    raw['cum_eps'] = pd.to_numeric(raw['cum_eps'], errors='coerce')
    raw.sort_values('report_date', inplace=True); raw.dropna(subset=['cum_eps'], inplace=True)
    qv = raw['cum_eps'].values; sa = []; psy = 0.0
    for dt, cum in zip(raw['report_date'], qv):
        if pd.isna(cum) or cum == 0: sa.append(0.0); continue
        m = dt.month
        if m == 3: sa.append(float(cum)); psy = float(cum)
        elif m == 6: sa.append(float(cum)-psy); psy = float(cum)
        elif m == 9: sa.append(float(cum)-psy); psy = float(cum)
        else: sa.append(float(cum)-psy); psy = 0.0
    raw['standalone_eps'] = sa
    return raw[raw['standalone_eps'] > 0].copy()

if __name__ == '__main__':
    codes = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
    results = [evaluate(c) if (evaluate(c) or True) else {"code": c, "status": "error", "message": str(e)} for c in codes]
    print(f"\n---RESULT_JSON---\n{json.dumps(results, ensure_ascii=False)}\n---END---", flush=True)
