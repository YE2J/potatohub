#!/usr/bin/env python3
"""Parse East Money moneyflow raw data files and write to SQLite.

Reads all /tmp/mf_raw_*.json files (web_extract output) and
/tmp/mf_batch_data.json (accumulated format), parses klines,
and writes to ~/my_quant_system/stock_data.db moneyflow_daily table.
"""
import json, sqlite3, os, glob, re

DB = os.path.expanduser('~/my_quant_system/stock_data.db')

def write_row(conn, code, date, f52, f53, f54, f55, f56):
    main_net = float(f52) if f52 != '-' else 0.0
    elg_net  = float(f53) if f53 != '-' else 0.0
    lg_net   = float(f54) if f54 != '-' else 0.0
    md_net   = float(f55) if f55 != '-' else 0.0
    sm_net   = float(f56) if f56 != '-' else 0.0

    conn.execute('''INSERT OR REPLACE INTO moneyflow_daily
        (stock_code,date,main_net_amt,lg_buy_amt,lg_sell_amt,md_buy_amt,md_sell_amt,
         sm_buy_amt,sm_sell_amt,elg_buy_amt,elg_sell_amt,net_mf_amt,data_source)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (code, date, main_net,
         max(lg_net,0), abs(min(lg_net,0)),
         max(md_net,0), abs(min(md_net,0)),
         max(sm_net,0), abs(min(sm_net,0)),
         max(elg_net,0), abs(min(elg_net,0)),
         main_net+elg_net+lg_net, 'eastmoney'))

def parse_klines(items, conn):
    """items: list of {code, klines: [str, ...]}"""
    count = 0
    for item in items:
        code = item['code']
        for line in item['klines']:
            parts = line.split(',')
            if len(parts) >= 6:
                write_row(conn, code, parts[0], parts[1], parts[2], parts[3], parts[4], parts[5])
                count += 1
    return count

def parse_raw_result(content, conn):
    """Parse a single web_extract result content string, extract klines."""
    m = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
    if not m:
        return 0
    j = json.loads(m.group(1))
    d = j.get('data', {})
    code = d.get('code', '')
    klines = d.get('klines', [])
    count = 0
    for line in klines:
        parts = line.split(',')
        if len(parts) >= 6:
            write_row(conn, code, parts[0], parts[1], parts[2], parts[3], parts[4], parts[5])
            count += 1
    return count

def main():
    conn = sqlite3.connect(DB)
    conn.execute('''CREATE TABLE IF NOT EXISTS moneyflow_daily (
        stock_code TEXT, date TEXT,
        main_net_amt REAL, lg_buy_amt REAL, lg_sell_amt REAL,
        md_buy_amt REAL, md_sell_amt REAL, sm_buy_amt REAL, sm_sell_amt REAL,
        elg_buy_amt REAL, elg_sell_amt REAL, net_mf_amt REAL, data_source TEXT,
        PRIMARY KEY (stock_code, date))''')

    total = 0

    # Load accumulated JSON
    batch_path = '/tmp/mf_batch_data.json'
    if os.path.exists(batch_path):
        with open(batch_path) as f:
            data = json.load(f)
        n = parse_klines(data, conn)
        print(f"batch_data.json: {len(data)} stocks, {n} rows")
        total += n

    # Load raw web_extract output files
    for rf in sorted(glob.glob('/tmp/mf_raw_*.json')):
        with open(rf) as f:
            content = f.read()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            print(f"  SKIP {rf}: invalid JSON")
            continue

        # Format 1: {"results": [{"content": "```json..."}, ...]}  (web_extract raw)
        if 'results' in data:
            n = 0
            for r in data['results']:
                n += parse_raw_result(r.get('content', ''), conn)
            print(f"  {rf}: {len(data['results'])} stocks, {n} rows (raw)")
            total += n
        # Format 2: [{"code": "...", "klines": [...]}, ...]  (direct)
        elif isinstance(data, list) and len(data) > 0 and 'klines' in data[0]:
            n = parse_klines(data, conn)
            print(f"  {rf}: {len(data)} stocks, {n} rows (direct)")
            total += n
        else:
            print(f"  SKIP {rf}: unknown format")

    conn.commit()

    cur = conn.execute("SELECT COUNT(*) as cnt, MIN(date), MAX(date) FROM moneyflow_daily WHERE date >= date('now','-5 days')")
    cnt, mn, mx = cur.fetchone()
    all_rows = conn.execute("SELECT COUNT(*), COUNT(DISTINCT stock_code) FROM moneyflow_daily").fetchone()
    print(f"\nRecent 5d: {cnt} rows ({mn} ~ {mx})")
    print(f"Total: {all_rows[0]} rows, {all_rows[1]} stocks")
    print(f"New/updated this run: {total} rows")
    conn.close()

if __name__ == '__main__':
    main()
