---
name: chinese-stock-tools
description: "Complete toolkit for A-share data work: binary format parsing (.day/.lc1/.lc5), THS/TDX formula→Python translation, batch CSV conversion, and database import."
version: 1.2.0
author: Hermes Agent
tags: [chinese-stock, a-share, tdx, ths, binary-format, formula-translation, quant, data-parsing, database-import]
platforms: [macos, linux]
---

# Chinese Stock Data Tools

Umbrella skill covering the full A-share data workflow: parsing local binary data files (同花顺/通达信 formats), batch converting to CSV, importing into SQLite databases, translating indicator formulas to Python, and retrieving data from APIs.

## When to Use

- User has `.day`, `.lc1`, `.lc5` files and asks how to read/parse/convert them
- User says "GitHub上有项目可以找到将该文件转换成可导入数据库的格式"
- User provides THS/TDX formula code (`.txt`, `.hxf`, `.nc`, `.tml`) and wants Python translation
- User asks about Chinese stock data file formats in general
- User needs OHLCV data from local software installations
- User wants bulk import of financial data into a backtesting database
- User has `.财经` financial data files that need parsing
- User wants incremental import that skips dates already in database

## Workflow: Single File Parsing → CSV

```bash
python scripts/ths_day_parser.py input.day [output.csv]
```

Auto-detects hd1.0 vs TDX format, index vs stock record size. Output is UTF-8 BOM CSV.

## Workflow: Batch Directory Conversion

For converting entire directories of `.day` files (recursive, multi-process):

```bash
# Convert all .day files in a directory tree
python scripts/ths_batch_convert.py /path/to/同花顺原数据

# Specify output directory
python scripts/ths_batch_convert.py /path/to/同花顺原数据 -o /path/to/csv_export

# Control parallelism
python scripts/ths_batch_convert.py /path/to/同花顺原数据 -j 8

# Flat output (no directory structure preserved)
python scripts/ths_batch_convert.py /path/to/同花顺原数据 --flat
```

Supports automatic output directory structure mirroring, progress reporting, and error resilience (bad files don't crash the batch).

## Workflow: CSV → Database Import

For importing the generated CSV files into a SQLite backtesting database:

```bash
# Import all CSVs into the database (incremental, skips duplicates)
python scripts/ths_import_to_db.py --csv-dir /path/to/csv_export --db /path/to/stock_data.db

# Overwrite existing records instead of skipping
python scripts/ths_import_to_db.py --csv-dir /path/to/csv_export --db /path/to/stock_data.db --mode replace

# Import + export Parquet files for backtrader
python scripts/ths_import_to_db.py --csv-dir /path/to/csv_export --db /path/to/stock_data.db --parquet
```

Uses `INSERT OR IGNORE` (default) or `INSERT OR REPLACE` (with `--mode replace`). Processes 500 records per batch in transactions for performance. Stock code is derived from CSV filename (filename minus extension).

## Workflow: Financial Data (.财经) Conversion & Import

For `.财经` files (同花顺财务数据——营收、ROE、股东户数、股本结构等):

```bash
# Parse all .财经 files in a directory (→ CSV + DB)
python scripts/ths_finance_parser.py /path/to/finance/

# Specify database
python scripts/ths_finance_parser.py /path/to/finance/ --db /path/to/stock_data.db

# CSV only (skip DB import)
python scripts/ths_finance_parser.py /path/to/finance/ --csv-only
```

Auto-detects the complex hd1.0 composite format: header → column definitions → padding → composite index → content area. Each `.财经` file creates its own SQLite table (e.g., `A股营业总收入`, `净资产收益率`, `股本结构`). Stock codes from the index entries automatically correlate with `daily_kline.stock_code`.

Files parsed in this session:
- `A股营业总收入.财经` (17MB, 315K records)
- `净资产收益率.财经` (2.7KB, 94 records)
- `股东户数.财经` (465KB, 18K records)
- `股本结构.财经` (22MB, 130K records)
- `可转债补充.财经` (21KB, 276 records)
- `REITs基金财务数据.财经` (31KB, 182 records)

## Key Format Changes Since v1.4

- **content_offset**: Some `.财经` files need +0x10000 adjustment; auto-detected by checking if adjusted offset contains a valid date
- **16-byte columns**: Auto-split into two double values
- **Per-file tables**: Each `.财经` file becomes its own DB table (not merged)

## Workflow: Minute Data Batch Conversion & Import

For `.min` files (minute-level K-line data):

```bash
# Convert all .min files in a directory + auto-import to minute_kline table
python scripts/ths_min_convert.py /path/to/min/dir

# Specify database
python scripts/ths_min_convert.py /path/to/min/dir --db /path/to/stock_data.db

# CSV-only (skip DB import) or DB-only (skip CSV conversion)
python scripts/ths_min_convert.py /path/to/min/dir --csv-only
python scripts/ths_min_convert.py /path/to/min/dir --db-only
```

Auto-detects int24 (÷10000 + 0xc0 sep) vs int32 (÷1000000) price encoding. Imports into `minute_kline` table (separate from daily data, as the user requires them managed independently).

See `references/ths-formula-translation.md` for the complete TDX formula → Python translation guide, including:
- Core function implementations (SMA, CROSS, HHV, LLV, etc.)
- AND/OR operator priority differences
- 6 major indicator translations (暗盘资金, 主力持仓, etc.)
- Tencent data API for fetching stock data

## Workflow: Data Retrieval

See `references/tencent_data_api.md` for the Tencent K-line API endpoint and parameters.
See `references/tdx_core_functions.md` for the TDX→Python function reference.
See `references/ths_indicators.md` for specific indicator translations.

## File Format Reference

See `references/hd1_day_format.md` for the complete hd1.0 **daily** binary format specification.
See `references/hd1_min_format.md` for the complete hd1.0 **minute** binary format specification.
See `references/stock-data-formats.md` for format comparison and detective work approach.

### Key Facts About hd1.0 Daily Format (.day)

- **Magic bytes**: `hd1.0\0` (6 bytes)
- **Record size**: 164 bytes (indices) / 176 bytes (stocks)
- **Price encoding**: 3-byte LE integer ÷ **10000**, followed by `0xc0` separator byte
- **Index area**: ~170 bytes between header and data area
- **Date field**: int32 LE at offset 0 of each record, format YYYYMMDD
- **OHLC offsets**: 4, 8, 12, 16 (3 bytes each + 1 byte 0xc0 separator)
- **Amount**: int32 LE at offset 20
- **Volume**: int32 LE at offset 24
- **Storage order**: reversed (newest first)
- **Data start**: offset 180 (0xB4) for indices, 192 (0xC0) for stocks
- **Stock code = filename without extension**: `600350.day` → code `600350`

### Key Facts About hd1.0 Minute Format (.min)

- **Magic bytes**: `hd1.0\0` (6 bytes) — same as daily
- **Record stride**: 152 bytes between records (48B data + 104B 0xFF padding)
- **Data start**: offset **320 (0x140)** (auto-detected)
- **seq field**: int32 LE at offset 0, auto-incrementing counter (≈1 per minute)
- **Automatic format detection**: two price encoding variants:
  - **int24**: 3-byte LE ÷ 10000 + 0xc0 separator (for B-shares, smaller indices)
  - **int32**: 4-byte LE ÷ 1000000 (for large indices like 上证指数 ~3262)
- **OHLC offsets**: 4, 8, 12, 16 (same positions, different encoding)
- **Additional fields**: volume(24), amount(28), trades(36)
- **DB table**: `minute_kline` (separate from daily data)

### `daily_kline` Table Schema (Quant System DB)

```sql
CREATE TABLE daily_kline (
    stock_code TEXT,
    date TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    amount REAL,
    amplitude REAL,     -- NULL from THS data
    pct_change REAL,    -- NULL from THS data
    change REAL,        -- NULL from THS data
    turnover REAL,      -- NULL from THS data
    PRIMARY KEY (stock_code, date)
);
```

### `minute_kline` Table Schema (Quant System DB)

Stored in the **same database** but separate table — minute data and daily data are managed independently.

```sql
CREATE TABLE minute_kline (
    stock_code TEXT,
    seq INTEGER,          -- minute sequence number (increments by 1 ≈ per minute)
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    amount REAL,
    trades INTEGER,
    PRIMARY KEY (stock_code, seq)
);
```

## Pitfalls

- **Don't use TDX 32-byte struct on hd1.0 files** — they have headers and different record sizes
- **Price divisor is 10000 for hd1.0, not 100** — int24 / 10000
- **Skip the 0xc0 separators** between each price field
- **Skip the index area** between header and data
- **Sort by date** — files store records newest-first
- **Stock files vs index files** have different record sizes (164 vs 176), detected automatically
- **Batch import is idempotent** — safe to re-run; uses INSERT OR IGNORE
- **Minute data has TWO price formats**: int24 (÷10000 + 0xc0) for small values, int32 (÷1000000) for large. Auto-detect via `detect_format()` — never hardcode
- **Minute record stride is 152 bytes**, not 48 (48B data + 104B padding). Data at offset 320, not 180/192 like daily
- **Do NOT mix daily and minute data** in the same table — user requires separate tables (`daily_kline` vs `minute_kline`)
- **Incremental import filters in Python** before hitting SQLite: read all existing (stock_code, date/seq) pairs into memory, then skip them. This avoids sending duplicate data to the DB at all

## Scripts

- `scripts/ths_day_parser.py` — Standalone single-file hd1.0 daily parser (stdlib only)
- `scripts/ths_batch_convert.py` — Multi-process batch .day → CSV converter
- `scripts/ths_min_convert.py` — Multi-process batch .min/.mn5 → CSV + DB import, auto-detects int24/int32 price format, supports --ext and --table for different minute granularities
- `scripts/ths_finance_parser.py` — hd1.0 `.财经` financial data parser (revenue, ROE, shareholders, capital structure, etc.)
- `scripts/ths_import_to_db.py` — CSV → SQLite database importer with incremental mode

All scripts work with Python 3 stdlib only (no pandas/akshare required for basic conversion). The import script uses optional `pandas` when `--parquet` is specified.
