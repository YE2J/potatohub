#!/usr/bin/env python3
"""
同花顺 hd1.0 格式 .day 文件解析器
支持指数文件(164B/record)和个股文件(176B/record)
输出: CSV 格式 (UTF-8 with BOM, Excel兼容)

用法:
    python ths_day_parser.py <输入.day文件> [输出.csv文件]

示例:
    python ths_day_parser.py "同花顺原数据/shase/day/1A0003.day" 1A0003.csv
    python ths_day_parser.py "同花顺原数据/shase/day/600350.day"
    # 批量转换所有.day文件
    for f in "同花顺原数据/shase/day/"*.day; do python ths_day_parser.py "$f"; done
"""
import sys
import struct
import csv
import os
from datetime import datetime


def read_int24_le(data, offset):
    """读取3字节小端无符号整数

    同花顺 hd1.0 格式将价格存储为24位小端整数。
    实际价格 = int24 / 10000

    Args:
        data: 字节数组
        offset: 起始偏移

    Returns:
        int: 24位整数值
    """
    return data[offset] + (data[offset + 1] << 8) + (data[offset + 2] << 16)


def find_data_area(buf):
    """自动探测数据起始偏移和记录大小

    同花顺指数文件使用164B/record，个股文件使用176B/record。
    此函数通过搜索连续有效日期来确定正确的参数。

    Args:
        buf: 文件字节数据

    Returns:
        (data_start_offset, record_size) 或 (None, None)
    """
    for rec_size in [164, 168, 172, 176, 180]:
        for off in range(10, min(500, len(buf) - 4), 2):
            val = int.from_bytes(buf[off:off + 4], 'little')
            if 19900101 <= val <= 20270630:
                if off + rec_size + 4 <= len(buf):
                    val2 = int.from_bytes(buf[off + rec_size:off + rec_size + 4], 'little')
                    if 19900101 <= val2 <= 20270630 and val2 != val:
                        # 验证更多记录
                        ok = True
                        for k in range(2, 5):
                            off3 = off + rec_size * k
                            if off3 + 4 <= len(buf):
                                v3 = int.from_bytes(buf[off3:off3 + 4], 'little')
                                if v3 < 19900101 or v3 > 20270630:
                                    ok = False
                                    break
                        if ok:
                            return off, rec_size
    return None, None


def parse(filename):
    """解析同花顺 hd1.0 格式 .day 文件

    Args:
        filename: .day 文件路径

    Returns:
        list[dict]: 记录列表，每项包含 date/open/high/low/close/amount/volume
    """
    with open(filename, "rb") as f:
        buf = f.read()

    if buf[:6] != b"hd1.0\0":
        print("错误: 不是 hd1.0 格式文件")
        return None

    count = int.from_bytes(buf[6:10], 'little')
    data_start, rec_size = find_data_area(buf)

    if data_start is None:
        print("错误: 无法定位数据区域")
        return None

    print(f"  记录数={count}, 数据起始偏移={data_start}, 记录大小={rec_size}")

    records = []
    offset = data_start

    while offset + rec_size <= len(buf):
        di = int.from_bytes(buf[offset:offset + 4], 'little')
        if di < 19900101 or di > 20270630:
            break
        try:
            ds = datetime.strptime(str(di), "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            break

        records.append({
            "date": ds,
            "open": read_int24_le(buf, offset + 4) / 10000.0,
            "high": read_int24_le(buf, offset + 8) / 10000.0,
            "low": read_int24_le(buf, offset + 12) / 10000.0,
            "close": read_int24_le(buf, offset + 16) / 10000.0,
            "amount": int.from_bytes(buf[offset + 20:offset + 24], 'little'),
            "volume": int.from_bytes(buf[offset + 24:offset + 28], 'little'),
        })
        offset += rec_size

    # 原始文件是倒序存储，正序排列
    records.sort(key=lambda r: r["date"])
    return records


def write_csv(records, outpath):
    """写入 UTF-8 BOM CSV (Excel直接打开不乱码)

    Args:
        records: 记录列表
        outpath: 输出文件路径
    """
    cols = ["date", "open", "high", "low", "close", "amount", "volume"]
    with open(outpath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(records)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <输入.day文件> [输出.csv文件]")
        sys.exit(1)

    inp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(inp)[0] + ".csv"

    if not os.path.exists(inp):
        print(f"错误: 文件不存在: {inp}")
        sys.exit(1)

    print(f"解析: {inp}")
    records = parse(inp)
    if records:
        write_csv(records, out)
        print(f"完成! {len(records)} 条记录 -> {out}")
        print(f"数据区间: {records[0]['date']} ~ {records[-1]['date']}")
        print(f"价格范围: {min(r['close'] for r in records):.2f} ~ "
              f"{max(r['close'] for r in records):.2f}")
    else:
        print("解析失败!")
        sys.exit(1)
