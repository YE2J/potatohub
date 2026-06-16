#!/usr/bin/env python3
"""
同花顺 hd1.0 格式 分钟数据(.min) 批量转换器
- 自动检测 int24(÷10000+0xc0) 和 int32(÷1000000) 两种价格格式
- 指数/个股统一处理 (48B记录, 152B步长)
- 输出: CSV + 自动导入 minute_kline 表
- 可增量导入 (跳过重复seq)

用法:
    python ths_min_convert.py /path/to/min/dir
    python ths_min_convert.py /path/to/min/dir --db /path/to/stock_data.db
    python ths_min_convert.py /path/to/min/dir --csv-only
    python ths_min_convert.py /path/to/min/dir --db-only
"""
import sys, os, csv, sqlite3, struct, argparse, logging, time, glob
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("ths_min")

RECORD_SIZE = 152
DATA_SIZE   = 48

def read_int24_le(data, offset):
    return data[offset] + (data[offset+1] << 8) + (data[offset+2] << 16)

def detect_format(buf, data_off):
    """Auto-detect: 'int24' (3-byte+0xc0) or 'int32' (4-byte)"""
    rec = buf[data_off:data_off+DATA_SIZE]
    has_c0 = (rec[7] == 0xc0 and rec[11] == 0xc0 and rec[15] == 0xc0 and rec[19] == 0xc0)
    if has_c0:
        return "int24"
    no_c0 = all(rec[i] != 0xc0 for i in [7, 11, 15, 19])
    if not no_c0:
        return "unknown"
    vals = [int.from_bytes(rec[i:i+4], 'little') for i in [4, 8, 12, 16]]
    vmin, vmax = min(vals), max(vals)
    if 1000000 <= vmin and vmax <= 10000000000 and (vmax - vmin) / max(vmin, 1) < 0.5:
        return "int32"
    return "unknown"

def find_data_start(buf):
    for off in range(160, 800, 4):
        if off + DATA_SIZE > len(buf): break
        nxt = off + RECORD_SIZE
        if nxt + 20 > len(buf): continue
        fmt = detect_format(buf, off)
        if fmt == "unknown": continue
        if fmt == detect_format(buf, nxt):
            return off
    return None

def parse_min_file(filepath):
    try:
        with open(filepath, "rb") as f:
            buf = f.read()
    except Exception as e:
        return None, f"读取失败: {e}"
    if buf[:6] != b"hd1.0\0":
        return None, "不是 hd1.0 格式"
    data_off = find_data_start(buf)
    if data_off is None:
        return None, "无法定位数据区域"
    fmt = detect_format(buf, data_off)
    if fmt == "unknown":
        return None, "未知的价格格式"

    records = []
    off = data_off
    while off + DATA_SIZE <= len(buf):
        rec = buf[off:off+DATA_SIZE]
        if rec[0] == 0xff and rec[1] == 0xff:
            break
        seq = int.from_bytes(rec[0:4], 'little')
        if seq <= 0 or seq > 10**9:
            break
        if fmt == "int24":
            open_p  = read_int24_le(rec, 4) / 10000.0
            high_p  = read_int24_le(rec, 8) / 10000.0
            low_p   = read_int24_le(rec, 12) / 10000.0
            close_p = read_int24_le(rec, 16) / 10000.0
        else:
            DIV = 1000000.0
            open_p  = int.from_bytes(rec[4:8], 'little') / DIV
            high_p  = int.from_bytes(rec[8:12], 'little') / DIV
            low_p   = int.from_bytes(rec[12:16], 'little') / DIV
            close_p = int.from_bytes(rec[16:20], 'little') / DIV
        records.append({
            "seq": seq, "open": open_p, "high": high_p,
            "low": low_p, "close": close_p,
            "volume": int.from_bytes(rec[24:28], 'little'),
            "amount": int.from_bytes(rec[28:32], 'little'),
            "trades": int.from_bytes(rec[36:40], 'little'),
        })
        off += RECORD_SIZE
    if not records:
        return None, "没有解析到有效记录"
    return records, None

def collect_min_files(input_dir):
    files = []
    for root, _, _ in os.walk(input_dir):
        for f in os.listdir(root):
            if f.lower().endswith(".min"):
                files.append(os.path.join(root, f))
    return sorted(files)

def convert_single(args):
    inpath, outdir, base_dir = args
    stock_code = os.path.splitext(os.path.basename(inpath))[0]
    if base_dir:
        rel = os.path.relpath(inpath, base_dir)
        outpath = os.path.join(outdir, os.path.splitext(rel)[0] + ".csv")
    else:
        outpath = os.path.join(outdir, stock_code + ".csv")
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    if os.path.exists(outpath):
        return (inpath, stock_code, True, "已存在(跳过)", 0)
    records, err = parse_min_file(inpath)
    if err:
        return (inpath, stock_code, False, err, 0)
    try:
        cols = ["seq", "open", "high", "low", "close", "volume", "amount", "trades"]
        with open(outpath, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(records)
    except Exception as e:
        return (inpath, stock_code, False, f"写CSV失败: {e}", 0)
    return (inpath, stock_code, True, "OK", len(records))

def create_min_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS minute_kline (
            stock_code TEXT, seq INTEGER,
            open REAL, high REAL, low REAL, close REAL,
            volume REAL, amount REAL, trades INTEGER,
            PRIMARY KEY (stock_code, seq)
        )
    """)
    conn.commit()

def import_csv_to_db(csv_files, db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    create_min_table(conn)
    cur = conn.execute("SELECT stock_code, seq FROM minute_kline")
    existing = {}
    for row in cur.fetchall():
        existing.setdefault(row[0], set()).add(row[1])
    total_imported = total_skipped = total_new = 0
    n = len(csv_files)
    start = time.time()
    for i, fpath in enumerate(csv_files):
        sc = os.path.splitext(os.path.basename(fpath))[0]
        rows = []
        with open(fpath, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                rows.append({"stock_code": sc, "seq": int(r["seq"]),
                    "open": float(r["open"]), "high": float(r["high"]),
                    "low": float(r["low"]), "close": float(r["close"]),
                    "volume": float(r.get("volume",0) or 0),
                    "amount": float(r.get("amount",0) or 0),
                    "trades": int(r.get("trades",0) or 0)})
        if not rows: continue
        known = existing.get(sc, set())
        new_rows = [r for r in rows if r["seq"] not in known]
        n_skip = len(rows) - len(new_rows)
        if not new_rows:
            logger.info("  [%d/%d] ⏭ %s: 全部已存在", i+1, n, sc)
            total_skipped += n_skip; continue
        for b in range(0, len(new_rows), 500):
            conn.executemany("INSERT OR IGNORE INTO minute_kline "
                "(stock_code,seq,open,high,low,close,volume,amount,trades) "
                "VALUES (:stock_code,:seq,:open,:high,:low,:close,:volume,:amount,:trades)",
                new_rows[b:b+500])
            conn.commit()
        if sc not in existing: existing[sc] = set(); total_new += 1
        for r in new_rows: existing[sc].add(r["seq"])
        total_imported += len(new_rows)
        total_skipped += n_skip
        logger.info("  [%d/%d] %s: +%d / ⏭%d  (共%d条)", i+1, n, sc, len(new_rows), n_skip, len(rows))
    elapsed = time.time() - start
    conn.close()
    logger.info("")
    logger.info("=" * 55)
    logger.info("  分钟数据导入完成! 耗时 %.1fs", elapsed)
    logger.info("  新增证券: %d", total_new)
    logger.info("  新增K线:  %d", total_imported)
    logger.info("  跳过重复: %d", total_skipped)
    return total_imported

def main():
    p = argparse.ArgumentParser(description="同花顺 hd1.0 分钟数据处理器")
    p.add_argument("input", nargs="?", help="输入目录")
    p.add_argument("--db", default=None, help="数据库路径")
    p.add_argument("--csv-only", action="store_true")
    p.add_argument("--db-only", action="store_true")
    p.add_argument("--jobs", type=int, default=os.cpu_count())
    args = p.parse_args()

    input_dir = os.path.abspath(args.input) if args.input else os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "Documents", "同花顺指标", "同花顺原数据", "shase", "min"))
    csv_dir = os.path.join(os.path.dirname(input_dir), "csv_export_min")
    db_path = args.db or os.path.expanduser("~/my_quant_system/stock_data.db")

    if not args.db_only:
        files = collect_min_files(input_dir)
        if not files:
            print(f"错误: 没有找到 .min 文件: {input_dir}"); sys.exit(1)
        print(f"📁 {len(files)} 个 .min 文件 -> 📂 {csv_dir} ⚡ {args.jobs}进程")
        tasks = [(f, csv_dir, input_dir) for f in files]
        ok = fail = total_rec = 0
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            fut = {ex.submit(convert_single, t): t[0] for t in tasks}
            done = 0
            for f in as_completed(fut):
                fp, sc, success, msg, nrec = f.result(); done += 1
                if success:
                    ok += 1; total_rec += nrec
                    if nrec > 0: logger.info("  ✓ [%d/%d] %s -> %d条", done, len(files), sc, nrec)
                else:
                    fail += 1; logger.warning("  ✗ [%d/%d] %s: %s", done, len(files), sc, msg)
        print(f"\n✅ 转换: {ok}/{len(files)} 成功, {total_rec} 条")
        if fail: print(f"❌ 失败: {fail}")

    if not args.csv_only:
        csv_files = sorted(glob.glob(os.path.join(csv_dir, "*.csv")))
        if csv_files: import_csv_to_db(csv_files, db_path)

if __name__ == "__main__":
    main()
