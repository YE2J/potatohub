#!/usr/bin/env python3
"""DC vs THS 板块资金流交叉对比分析

用法:
  python scripts/dc_ths_cross_compare.py

输出:
  3个抽样日的DC vs THS TOP5净流入对比
  全量排名相关性统计（两数据源TOP5上榜次数排名对比）
"""
import sqlite3

DB = '/Users/yellow/my_quant_system/stock_data.db'

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # 选3个抽样日
    cur.execute("""
        SELECT DISTINCT s.trade_date FROM sector_moneyflow_dc s
        JOIN sector_moneyflow_ths t ON s.trade_date = t.trade_date
        ORDER BY s.trade_date
    """)
    common = [r[0] for r in cur.fetchall()]
    samples = [common[0], common[len(common)//2], common[-1]]

    for label, dc_tbl, ths_tbl, dc_col, ths_col in [
        ('概念板块', 'sector_moneyflow_dc', 'sector_moneyflow_ths',
         'sector_code', 'sector_code'),
        ('行业板块', 'industry_moneyflow_dc', 'industry_moneyflow_ths',
         'industry_code', 'industry_code'),
    ]:
        print(f"\n【{label}】")
        for d in samples:
            cur.execute(f"SELECT sector_name, ROUND(net_amount/1e8,2) FROM {dc_tbl} WHERE trade_date=? ORDER BY net_amount DESC LIMIT 5", (d,))
            dc5 = cur.fetchall()
            cur.execute(f"SELECT sector_name, ROUND(net_amount/1e4,2) FROM {ths_tbl} WHERE trade_date=? ORDER BY net_amount DESC LIMIT 5", (d,))
            ths5 = cur.fetchall()
            overlap = {r[0] for r in dc5} & {r[0] for r in ths5}
            print(f"  {d}: 重合{len(overlap)}/5")

    conn.close()

if __name__ == '__main__':
    main()
