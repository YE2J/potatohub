#!/usr/bin/env python3
"""
同花顺 hd1.0 格式数据批量转换器
支持: .day 日线 (指数164B/条, 个股176B/条)
输出: UTF-8 BOM CSV (Excel直接打开不乱码)

用法:
    # 转换整个文件夹(递归)
    python ths_batch_convert.py /path/to/同花顺原数据

    # 输出到指定目录
    python ths_batch_convert.py /path/to/同花顺原数据 -o /path/to/csv输出

    # 仅处理 .day 文件
    python ths_batch_convert.py /path/to/同花顺原数据 --ext .day

    # 多进程加速(默认用满CPU核数)
    python ths_batch_convert.py /path/to/同花顺原数据 -j 8
"""
import sys, struct, csv, os, argparse, logging, time
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# ============================================================
# 核心解析函数
# ============================================================

def read_int24_le(data, offset):
    """读取3字节小端无符号整数"""
    return data[offset] + (data[offset+1] << 8) + (data[offset+2] << 16)


def find_data_area(buf):
    """自动探测 hd1.0 数据起始偏移和记录大小"""
    for rec_size in [164, 168, 172, 176, 180]:
        for off in range(10, min(500, len(buf)-4), 2):
            val = int.from_bytes(buf[off:off+4], 'little')
            if 19900101 <= val <= 20270630:
                if off + rec_size + 4 <= len(buf):
                    val2 = int.from_bytes(buf[off+rec_size:off+rec_size+4], 'little')
                    if 19900101 <= val2 <= 20270630 and val2 != val:
                        ok = True
                        for k in range(2, 5):
                            off3 = off + rec_size * k
                            if off3 + 4 <= len(buf):
                                v3 = int.from_bytes(buf[off3:off3+4], 'little')
                                if v3 < 19900101 or v3 > 20270630:
                                    ok = False
                                    break
                        if ok:
                            return off, rec_size
    return None, None


def parse_hd1_day(filepath):
    """解析单个 hd1.0 .day 文件，返回 (records, error_msg)"""
    try:
        with open(filepath, "rb") as f:
            buf = f.read()
    except Exception as e:
        return None, f"读取失败: {e}"

    if buf[:6] != b"hd1.0\0":
        return None, "不是 hd1.0 格式"

    data_start, rec_size = find_data_area(buf)
    if data_start is None:
        return None, "无法定位数据区域"

    records = []
    offset = data_start
    while offset + rec_size <= len(buf):
        di = int.from_bytes(buf[offset:offset+4], 'little')
        if di < 19900101 or di > 20270630:
            break
        try:
            ds = datetime.strptime(str(di), "%Y%m%d").strftime("%Y-%m-%d")
        except:
            break

        records.append({
            "date": ds,
            "open":  read_int24_le(buf, offset + 4) / 10000.0,
            "high":  read_int24_le(buf, offset + 8) / 10000.0,
            "low":   read_int24_le(buf, offset + 12) / 10000.0,
            "close": read_int24_le(buf, offset + 16) / 10000.0,
            "amount": int.from_bytes(buf[offset+20:offset+24], 'little'),
            "volume": int.from_bytes(buf[offset+24:offset+28], 'little'),
        })
        offset += rec_size

    if not records:
        return None, "没有解析到有效记录"

    records.sort(key=lambda r: r["date"])
    return records, None


# ============================================================
# 单文件转换任务 (用于多进程)
# ============================================================

def convert_single_file(args):
    """
    转换单个文件。独立函数以便 ProcessPoolExecutor 调度。
    args: (input_path, output_dir, base_dir)
    返回: (input_path, success, message, record_count)
    """
    inpath, outdir, base_dir = args

    # 计算输出路径: 保持相对于 base_dir 的目录结构
    if base_dir:
        rel = os.path.relpath(inpath, base_dir)
        rel_no_ext = os.path.splitext(rel)[0]
        outpath = os.path.join(outdir, rel_no_ext + ".csv")
    else:
        outpath = os.path.join(outdir, os.path.splitext(os.path.basename(inpath))[0] + ".csv")

    # 创建输出目录
    os.makedirs(os.path.dirname(outpath), exist_ok=True)

    # 跳过已存在的文件(续传)
    if os.path.exists(outpath):
        return (inpath, True, "已存在(跳过)", 0)

    records, err = parse_hd1_day(inpath)
    if err:
        return (inpath, False, err, 0)

    try:
        cols = ["date", "open", "high", "low", "close", "amount", "volume"]
        with open(outpath, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(records)
    except Exception as e:
        return (inpath, False, f"写入CSV失败: {e}", 0)

    return (inpath, True, "OK", len(records))


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="同花顺 hd1.0 格式数据批量转换器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s /path/to/同花顺原数据
  %(prog)s /path/to/同花顺原数据 -o /path/to/csv
  %(prog)s /path/to/同花顺原数据 --ext .day -j 8
        """
    )
    parser.add_argument("input", help="输入文件或文件夹路径")
    parser.add_argument("-o", "--output", default=None,
                        help="输出目录 (默认: 在输入目录旁创建 csv_export)")
    parser.add_argument("--ext", default=".day",
                        help="文件扩展名过滤 (默认: .day)")
    parser.add_argument("-j", "--jobs", type=int, default=None,
                        help="并行进程数 (默认: CPU核数)")
    parser.add_argument("--flat", action="store_true",
                        help="平铺输出, 不保留目录结构")
    parser.add_argument("--quiet", action="store_true",
                        help="静默模式, 只显示摘要")

    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    if not os.path.exists(input_path):
        print(f"错误: 路径不存在: {input_path}")
        sys.exit(1)

    # 收集文件
    if os.path.isfile(input_path):
        files = [input_path]
        base_dir = os.path.dirname(input_path) if not args.flat else None
    else:
        files = []
        base_dir = input_path if not args.flat else None
        for root, _, _ in os.walk(input_path):
            for f in os.listdir(root):
                if f.lower().endswith(args.ext.lower()):
                    files.append(os.path.join(root, f))

    if not files:
        print(f"没有找到 *{args.ext} 文件")
        sys.exit(1)

    # 输出目录
    if args.output:
        out_dir = os.path.abspath(args.output)
    else:
        if os.path.isfile(input_path):
            out_dir = os.path.join(os.path.dirname(input_path), "csv_export")
        else:
            out_dir = os.path.join(input_path, "..", "csv_export")
        out_dir = os.path.abspath(out_dir)

    os.makedirs(out_dir, exist_ok=True)

    # 准备任务参数
    tasks = [(f, out_dir, base_dir) for f in files]

    # 执行
    start = time.time()
    n_jobs = args.jobs or os.cpu_count() or 4

    if not args.quiet:
        print(f"输入: {input_path}")
        print(f"文件数: {len(files)} (*{args.ext})")
        print(f"输出: {out_dir}")
        print(f"进程数: {n_jobs}")
        print(f"{'='*50}")

    success_count = 0
    fail_count = 0
    total_records = 0
    fails = []

    if n_jobs > 1 and len(files) > 1:
        with ProcessPoolExecutor(max_workers=n_jobs) as executor:
            futures = {executor.submit(convert_single_file, t): t[0] for t in tasks}
            done = 0
            for future in as_completed(futures):
                fpath, ok, msg, nrec = future.result()
                done += 1
                if ok:
                    success_count += 1
                    total_records += nrec
                    if not args.quiet:
                        print(f"  OK [{done}/{len(files)}] {os.path.basename(fpath)} -> {nrec}条")
                else:
                    fail_count += 1
                    fails.append((fpath, msg))
                    if not args.quiet:
                        print(f"  FAIL [{done}/{len(files)}] {os.path.basename(fpath)}: {msg}")
    else:
        for i, task in enumerate(tasks):
            fpath, ok, msg, nrec = convert_single_file(task)
            if ok:
                success_count += 1
                total_records += nrec
                if not args.quiet:
                    print(f"  OK [{i+1}/{len(files)}] {os.path.basename(fpath)} -> {nrec}条")
            else:
                fail_count += 1
                fails.append((fpath, msg))
                if not args.quiet:
                    print(f"  FAIL [{i+1}/{len(files)}] {os.path.basename(fpath)}: {msg}")

    elapsed = time.time() - start

    print(f"\n{'='*50}")
    print(f"完成! 耗时 {elapsed:.1f}s")
    print(f"成功: {success_count}/{len(files)} 文件, 共 {total_records} 条K线记录")
    print(f"失败: {fail_count}")
    print(f"输出: {out_dir}")

    if fails:
        print(f"\n失败详情:")
        for fpath, msg in fails:
            print(f"   {fpath}: {msg}")


if __name__ == "__main__":
    main()
