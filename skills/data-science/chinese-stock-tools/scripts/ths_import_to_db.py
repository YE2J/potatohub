#!/usr/bin/env python3
"""
同花顺 hd1.0 CSV 数据 → 量化回测系统 SQLite 导入器

功能:
  - 将 ths_batch_convert.py 生成的 CSV 批量导入 stock_data.db
  - 增量导入: 已存在的记录自动跳过/覆盖
  - 支持未来新增数据的重复导入
  - 可选: 同时导出 Parquet 供 backtrader 使用

用法:
    python ths_import_to_db.py --csv-dir /path/to/csv --db /path/to/stock_data.db
    python ths_import_to_db.py --csv-dir /path/to/csv --db /path/to/stock_data.db --mode replace
    python ths_import_to_db.py --csv-dir /path/to/csv --db /path/to/stock_data.db --parquet
"""
import sys, os, csv, sqlite3, argparse, logging, time
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ths_import")


def count_csv_files(csv_dir):
    files = []
    for root, _, _ in os.walk(csv_dir):
        for f in os.listdir(root):
            if f.lower().endswith(".csv"):
                files.append(os.path.join(root, f))
    return sorted(files)


def parse_csv(filepath):
    """读取单个CSV, 返回(stock_code, records). 文件名不含扩展名即代码"""
    stock_code = os.path.splitext(os.path.basename(filepath))[0]
    records = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                records.append({
                    "stock_code": stock_code,
                    "date": row["date"],
                    "open": float(row["open"]), "high": float(row["high"]),
                    "low": float(row["low"]), "close": float(row["close"]),
                    "volume": float(row.get("volume", 0) or 0),
                    "amount": float(row.get("amount", 0) or 0),
                    "amplitude": None, "pct_change": None,
                    "change": None, "turnover": None,
                })
            except (KeyError, ValueError) as e:
                logger.warning("  Skip %s line %d: %s", filepath, reader.line_num, e)
    return stock_code, records


def import_csv_batch(csv_files, db_path, mode="ignore",
                     parquet=False, parquet_dir=None):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-80000")

    cur = conn.execute("SELECT DISTINCT stock_code FROM daily_kline")
    existing_codes = {row[0] for row in cur.fetchall()}
    cur = conn.execute(
        "SELECT stock_code, COUNT(*) FROM daily_kline GROUP BY stock_code"
    )
    existing_counts = dict(cur.fetchall())
    or_clause = "OR REPLACE" if mode == "replace" else "OR IGNORE"

    total_imported = total_skipped = total_new = 0
    start = time.time()
    n_files = len(csv_files)

    for i, fpath in enumerate(csv_files):
        stock_code, records = parse_csv(fpath)
        if not records:
            logger.info("  [%d/%d] ⏭  %s: empty", i+1, n_files, stock_code)
            continue

        BATCH = 500
        for b in range(0, len(records), BATCH):
            batch = records[b:b+BATCH]
            try:
                conn.executemany(
                    f"INSERT {or_clause} INTO daily_kline "
                    "(stock_code,date,open,high,low,close,volume,amount,"
                    "amplitude,pct_change,change,turnover) "
                    "VALUES(:stock_code,:date,:open,:high,:low,:close,:volume,"
                    ":amount,:amplitude,:pct_change,:change,:turnover)",
                    batch,
                )
                conn.commit()
            except sqlite3.Error as e:
                logger.error("  ERROR [%d/%d] %s: %s", i+1, n_files, stock_code, e)

        cur = conn.execute(
            "SELECT COUNT(*) FROM daily_kline WHERE stock_code=?", (stock_code,)
        )
        db_count = cur.fetchone()[0]
        old_count = existing_counts.get(stock_code, 0)
        imported = db_count - old_count
        skipped = len(records) - imported
        total_imported += imported
        total_skipped += skipped
        if stock_code not in existing_codes:
            total_new += 1

        logger.info(
            "  [%d/%d] %s: +%d / skp%d / tot%d  (%s~%s)",
            i+1, n_files, stock_code, imported, skipped, db_count,
            records[0]["date"], records[-1]["date"],
        )

    elapsed = time.time() - start
    cur = conn.execute("SELECT COUNT(*), COUNT(DISTINCT stock_code) FROM daily_kline")
    tot_k, tot_s = cur.fetchone()
    conn.close()

    logger.info("")
    logger.info("=" * 55)
    logger.info("  完成! %.1fs 文件:%d 新证券:%d 新K线:%d 跳过:%d",
                elapsed, n_files, total_new, total_imported, total_skipped)
    logger.info("  数据库总计: %d 条, %d 只证券", tot_k, tot_s)

    if parquet:
        _export_parquet(db_path, parquet_dir)


def _export_parquet(db_path, parquet_dir):
    import pandas as pd
    if not parquet_dir:
        parquet_dir = "data/parquet"
    os.makedirs(parquet_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT DISTINCT stock_code FROM daily_kline ORDER BY stock_code")
    codes = [r[0] for r in cur.fetchall()]
    for code in codes:
        df = pd.read_sql(
            "SELECT date,open,high,low,close,volume FROM daily_kline "
            "WHERE stock_code=? ORDER BY date",
            conn, params=(code,),
        )
        if not df.empty:
            df.to_parquet(os.path.join(parquet_dir, f"{code}.parquet"), index=False)
    conn.close()
    logger.info("Parquet done: %d securities", len(codes))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="THS CSV → Quant DB Importer")
    parser.add_argument("--csv-dir", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--mode", choices=["ignore", "replace"], default="ignore")
    parser.add_argument("--parquet", action="store_true")
    parser.add_argument("--parquet-dir")
    args = parser.parse_args()

    csv_dir = os.path.abspath(args.csv_dir)
    db_path = os.path.abspath(args.db)
    if not os.path.isdir(csv_dir):
        print(f"Error: CSV dir not found: {csv_dir}"); sys.exit(1)
    files = count_csv_files(csv_dir)
    if not files:
        print(f"Error: No CSV files in {csv_dir}"); sys.exit(1)

    logger.info("THS CSV → DB Importer: %d files → %s", len(files), db_path)
    import_csv_batch(files, db_path, mode=args.mode,
                     parquet=args.parquet, parquet_dir=args.parquet_dir)
