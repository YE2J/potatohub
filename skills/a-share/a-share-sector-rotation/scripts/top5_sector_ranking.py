#!/usr/bin/env python3
"""每日概念/行业板块 TOP5 净流入排名统计

用法:
  python3 top5_sector_ranking.py

输出:
  2026年至今，概念板块和行业板块每日净流入TOP5的上榜次数排行
  含: 上榜次数、日均净流入(亿)、登顶次数、累计净流入(亿)

数据源:
  sector_moneyflow_ths  — 同花顺概念板块资金流向
  industry_moneyflow_ths — 同花顺行业板块资金流向

注意:
  net_amount 单位是 万元，除以 1e4 得到 亿
"""
import sqlite3

DB = '/Users/yellow/my_quant_system/stock_data.db'


def run():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    for table, label, code_col, name_col in [
        ('sector_moneyflow_ths', '概念板块', 'sector_code', 'sector_name'),
        ('industry_moneyflow_ths', '行业板块', 'industry_code', 'industry_name'),
    ]:
        _print_ranking(cur, table, label, code_col, name_col)

    cur.execute(
        "SELECT COUNT(DISTINCT trade_date) FROM sector_moneyflow_ths "
        "WHERE trade_date LIKE '2026%'"
    )
    total = cur.fetchone()[0]
    print(f"\n共 {total} 个交易日")
    conn.close()


def _print_ranking(cur, table, label, code_col, name_col):
    print(f"\n{'=' * 60}")
    print(f"【{label}】每日净流入TOP5 上榜次数排行 (2026全年)")
    print(f"{'=' * 60}")
    cur.execute(f"""
        WITH ranked AS (
            SELECT trade_date, {code_col}, {name_col},
                   ROUND(net_amount / 1e4, 2) AS net_yi,
                   ROW_NUMBER() OVER (
                       PARTITION BY trade_date ORDER BY net_amount DESC
                   ) AS rn
            FROM {table}
            WHERE trade_date LIKE '2026%'
        )
        SELECT {name_col}, COUNT(*) AS top5_times,
               ROUND(AVG(net_yi), 2) AS avg_inflow_yi,
               SUM(CASE WHEN rn = 1 THEN 1 ELSE 0 END) AS rank1_times,
               ROUND(SUM(net_yi), 2) AS total_inflow_yi
        FROM ranked
        WHERE rn <= 5
        GROUP BY {code_col}
        ORDER BY top5_times DESC
        LIMIT 25
    """)
    print(f"{'排名':<4} {label:<16} {'上榜次数':<8} "
          f"{'日均净流入(亿)':<12} {'登顶次数':<8} {'累计净流入(亿)':<10}")
    print('-' * 60)
    for i, (name, cnt, avg, r1, total) in enumerate(cur.fetchall(), 1):
        print(f"{i:<4} {name:<16} {cnt:<8} {avg:<12} {r1:<8} {total:<10}")


if __name__ == '__main__':
    run()
