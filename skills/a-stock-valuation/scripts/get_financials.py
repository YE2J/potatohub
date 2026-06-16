#!/usr/bin/env python3
"""
A股财务数据获取脚本

功能：
- 从akshare获取A股财务报表数据（资产负债表、利润表、现金流量表）
- 自动清洗和格式化数据
- 支持输出为JSON供下游脚本调用

用法：
  python get_financials.py 600519
  python get_financials.py 000858 --format json
  python get_financials.py 600036 --period quarterly --output /tmp/data.json
"""

import sys
import json
import argparse
import pandas as pd
import numpy as np
import akshare as ak


def get_stock_name(stock_code: str) -> str:
    """获取股票名称"""
    try:
        info = ak.stock_individual_info_em(symbol=stock_code)
        if isinstance(info, pd.DataFrame):
            name_row = info[info[info['item'] == '股票简称']]
            if len(name_row) > 0:
                return name_row['value'].values[0]
    except Exception:
        pass
    return stock_code


def get_stock_info(stock_code: str) -> dict:
    """获取股票基本信息"""
    try:
        info_df = ak.stock_individual_info_em(symbol=stock_code)
        info = {}
        if isinstance(info_df, pd.DataFrame):
            for _, row in info_df.iterrows():
                info[row['item']] = row['value']
        return info
    except Exception as e:
        print(f"获取股票信息失败: {e}")
        return {}


def get_balance_sheet(stock_code: str, period: str = "annual"):
    """获取资产负债表"""
    try:
        if period == "annual":
            df = ak.stock_balance_sheet_by_yearly_em(symbol=stock_code)
        else:
            df = ak.stock_balance_sheet_by_quarterly_em(symbol=stock_code)
        return df
    except Exception as e:
        print(f"获取资产负债表失败: {e}")
        return pd.DataFrame()


def get_income_statement(stock_code: str, period: str = "annual"):
    """获取利润表"""
    try:
        if period == "annual":
            df = ak.stock_profit_sheet_by_yearly_em(symbol=stock_code)
        else:
            df = ak.stock_profit_sheet_by_quarterly_em(symbol=stock_code)
        return df
    except Exception as e:
        print(f"获取利润表失败: {e}")
        return pd.DataFrame()


def get_cash_flow(stock_code: str, period: str = "annual"):
    """获取现金流量表"""
    try:
        if period == "annual":
            df = ak.stock_cash_flow_sheet_by_yearly_em(symbol=stock_code)
        else:
            df = ak.stock_cash_flow_sheet_by_quarterly_em(symbol=stock_code)
        return df
    except Exception as e:
        print(f"获取现金流量表失败: {e}")
        return pd.DataFrame()


def get_historical_prices(stock_code: str, years: int = 5):
    """获取历史股价（用于计算估值参考）"""
    try:
        df = ak.stock_zh_a_hist(symbol=stock_code, period='daily', adjust='qfq')
        if len(df) > 0:
            df['日期'] = pd.to_datetime(df['日期'])
            cutoff = pd.Timestamp.now() - pd.DateOffset(years=years)
            return df[df['日期'] >= cutoff]
    except Exception as e:
        print(f"获取历史股价失败: {e}")
    return pd.DataFrame()


def clean_financial_data(df: pd.DataFrame) -> pd.DataFrame:
    """清洗财务数据"""
    if df is None or len(df) == 0:
        return df
    df = df.copy()
    # 删除全空列
    df = df.dropna(axis=1, how='all')
    # 按报告期排序
    if '报告期' in df.columns:
        df = df.sort_values('报告期', ascending=True)
    return df


def extract_key_financials(balance_df, income_df, cashflow_df) -> dict:
    """
    提取关键财务指标，供估值计算使用

    Returns:
        dict: 包含最近5年关键财务数据的字典
    """
    result = {
        "years": [],
        "revenue": [],
        "net_profit": [],
        "total_assets": [],
        "total_equity": [],
        "total_liabilities": [],
        "operating_cash_flow": [],
        "capital_expenditure": [],
        "free_cash_flow": [],
    }

    # 提取利润表关键数据
    if len(income_df) > 0 and '报告期' in income_df.columns:
        income_df = income_df.sort_values('报告期')
        recent = income_df.tail(5)

        for _, row in recent.iterrows():
            period = str(row.get('报告期', ''))
            result["years"].append(period[:4] if len(period) >= 4 else period)
            result["revenue"].append(float(row.get('营业收入', 0) or 0))
            result["net_profit"].append(float(row.get('净利润', 0) or 0))

    # 提取资产负债表关键数据
    if len(balance_df) > 0 and '报告期' in balance_df.columns:
        balance_df = balance_df.sort_values('报告期')
        recent_bs = balance_df.tail(5)

        for _, row in recent_bs.iterrows():
            result["total_assets"].append(float(row.get('资产总计', 0) or 0))
            result["total_equity"].append(float(row.get('股东权益合计', 0) or 0))
            result["total_liabilities"].append(float(row.get('负债合计', 0) or 0))

    # 提取现金流量表关键数据
    if len(cashflow_df) > 0 and '报告期' in cashflow_df.columns:
        cashflow_df = cashflow_df.sort_values('报告期')
        recent_cf = cashflow_df.tail(5)

        for _, row in recent_cf.iterrows():
            ocf = float(row.get('经营活动产生的现金流量净额', 0) or 0)
            capex = float(row.get('购建固定资产、无形资产和其他长期资产支付的现金', 0) or 0)
            result["operating_cash_flow"].append(ocf)
            result["capital_expenditure"].append(capex)
            result["free_cash_flow"].append(ocf + capex)  # capex为负值

    return result


def main():
    parser = argparse.ArgumentParser(description="A股财务数据获取脚本")
    parser.add_argument("stock_code", type=str, help="股票代码，如600519")
    parser.add_argument("--period", type=str, default="annual",
                        choices=["annual", "quarterly"], help="报告期（默认annual）")
    parser.add_argument("--format", type=str, default="text",
                        choices=["text", "json"], help="输出格式（默认text）")
    parser.add_argument("--output", type=str, help="输出文件路径（JSON格式）")
    parser.add_argument("--save-excel", type=str, help="保存为Excel文件路径")
    args = parser.parse_args()

    stock_code = args.stock_code
    stock_name = get_stock_name(stock_code)

    print(f"\n{'='*60}")
    print(f"  {stock_name} ({stock_code}) · 财务数据获取")
    print(f"{'='*60}\n")

    # 获取财务数据
    balance_df = clean_financial_data(get_balance_sheet(stock_code, args.period))
    income_df = clean_financial_data(get_income_statement(stock_code, args.period))
    cashflow_df = clean_financial_data(get_cash_flow(stock_code, args.period))
    stock_info = get_stock_info(stock_code)

    print(f"  资产负债表: {len(balance_df)} 条")
    print(f"  利润表:     {len(income_df)} 条")
    print(f"  现金流量表: {len(cashflow_df)} 条")

    # 提取关键指标
    key_data = extract_key_financials(balance_df, income_df, cashflow_df)

    # 获取最新股价
    price_df = get_historical_prices(stock_code, years=1)
    latest_price = float(price_df.iloc[-1]['收盘']) if len(price_df) > 0 else 0.0

    # 保存Excel
    if args.save_excel:
        try:
            with pd.ExcelWriter(args.save_excel, engine='openpyxl') as writer:
                if len(balance_df) > 0:
                    balance_df.to_excel(writer, sheet_name='资产负债表', index=False)
                if len(income_df) > 0:
                    income_df.to_excel(writer, sheet_name='利润表', index=False)
                if len(cashflow_df) > 0:
                    cashflow_df.to_excel(writer, sheet_name='现金流量表', index=False)
            print(f"\n  Excel已保存: {args.save_excel}")
        except Exception as e:
            print(f"\n  保存Excel失败: {e}")

    # 构建输出
    output = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "latest_price": latest_price,
        "stock_info": stock_info,
        "financial_data": key_data,
        "data_quality": {
            "balance_sheet_records": len(balance_df),
            "income_statement_records": len(income_df),
            "cash_flow_records": len(cashflow_df),
        }
    }

    if args.format == "json":
        output_str = json.dumps(output, ensure_ascii=False, indent=2, default=str)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_str)
            print(f"\n  JSON已保存: {args.output}")
        else:
            print("\n" + output_str)
    else:
        print(f"\n{'='*60}")
        print(f"  关键财务数据摘要（最近5年）")
        print(f"{'='*60}")
        print(f"  最新股价: {latest_price:.2f}" if latest_price > 0 else "  最新股价: 获取失败")
        if key_data["years"]:
            print(f"  数据年份: {', '.join(key_data['years'])}")
            print(f"\n  营业收入（亿）:")
            for i, year in enumerate(key_data["years"]):
                if i < len(key_data["revenue"]):
                    rev = key_data["revenue"][i] / 1e8
                    print(f"    {year}: {rev:.2f}")
            print(f"\n  净利润（亿）:")
            for i, year in enumerate(key_data["years"]):
                if i < len(key_data["net_profit"]):
                    np_val = key_data["net_profit"][i] / 1e8
                    print(f"    {year}: {np_val:.2f}")
            if key_data["free_cash_flow"]:
                print(f"\n  自由现金流（亿）:")
                for i, year in enumerate(key_data["years"]):
                    if i < len(key_data["free_cash_flow"]):
                        fcf = key_data["free_cash_flow"][i] / 1e8
                        print(f"    {year}: {fcf:.2f}")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
