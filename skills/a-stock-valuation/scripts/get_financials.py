#!/usr/bin/env python3
"""
A股财务数据获取脚本

功能：
- 从Tushare获取A股财务报表数据（资产负债表、利润表、现金流量表）
- 自动清洗和格式化数据
- 支持输出为JSON供下游脚本调用

数据来源：
- 实时行情/行业：Hermes web_extract JSON（data/ 目录）
- 财务三大报表：Tushare（需 Tushare token 配置）

说明：
- Tushare 财务数据单位是元
- fina_indicator 中 ROE 是百分比值（如 15.2 表示 15.2%）

用法：
  python get_financials.py 600519
  python get_financials.py 000858 --format json
  python get_financials.py 600036 --period quarterly --output /tmp/data.json
"""

import sys
import json
import argparse
import os
import pandas as pd
import numpy as np
import tushare as ts

# 导入共享数据模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_fetcher import get_stock_name, get_stock_info, get_stock_price


# ============================================================
# Tushare 初始化
# ============================================================

_TS_PRO = None


def _get_ts_pro():
    global _TS_PRO
    if _TS_PRO is None:
        try:
            _TS_PRO = ts.pro_api()
        except Exception:
            _TS_PRO = None
    return _TS_PRO


def _ts_code(code: str) -> str:
    """将6位股票代码转为 Tushare 格式"""
    if code.endswith(('.SH', '.SZ', '.BJ')):
        return code
    # 北交所：8xxx 或 4xxx
    if code.startswith(('8', '4')):
        return f"{code}.BJ"
    suffix = 'SH' if code.startswith(('6', '9')) else 'SZ'
    return f"{code}.{suffix}"


def get_balance_sheet(stock_code: str, period: str = "annual"):
    """获取资产负债表

    Tushare 字段：
      end_date: 报告期
      total_assets: 资产总计
      total_liab: 负债合计
      total_hldr_eqy_inc_min_int: 股东权益合计(含少数)
      total_hldr_eqy_exc_min_int: 归属母公司股东权益
      money_cap: 货币资金
      accounts_receiv: 应收账款
      fix_assets: 固定资产
      intan_assets: 无形资产
    """
    try:
        pro = _get_ts_pro()
        if pro is None:
            return pd.DataFrame()
        ts_code = _ts_code(stock_code)
        fields = 'ts_code,end_date,total_assets,total_liab,total_hldr_eqy_inc_min_int,total_hldr_eqy_exc_min_int,money_cap,accounts_receiv,fix_assets,intan_assets'
        if period == "annual":
            df = pro.balancesheet(ts_code=ts_code, fields=fields,
                                  start_date='20000101', end_date='20261231')
            if df is not None and len(df) > 0:
                df = df[df['end_date'].astype(str).str.endswith('1231')]  # 仅保留年报
        else:
            # 季度数据：使用 report_type 参数获取所有报告期
            df = pro.balancesheet(ts_code=ts_code, fields=fields,
                                  start_date='20000101', end_date='20261231')
        if df is not None and len(df) > 0:
            df = df.sort_values('end_date')
        return df
    except Exception as e:
        print(f"获取资产负债表失败: {e}")
        return pd.DataFrame()


def get_income_statement(stock_code: str, period: str = "annual"):
    """获取利润表

    Tushare 字段：
      end_date: 报告期
      revenue: 营业收入
      total_revenue: 营业总收入
      operate_profit: 营业利润
      n_income_attr_p: 归属于母公司股东的净利润
      n_income: 净利润（含少数股东）
      basic_eps: 基本每股收益
      rd_exp: 研发费用
    """
    try:
        pro = _get_ts_pro()
        if pro is None:
            return pd.DataFrame()
        ts_code = _ts_code(stock_code)
        fields = 'ts_code,end_date,revenue,total_revenue,operate_profit,n_income_attr_p,n_income,basic_eps,rd_exp'
        df = pro.income(ts_code=ts_code, fields=fields,
                        start_date='20000101', end_date='20261231')
        if df is not None and len(df) > 0:
            df = df.sort_values('end_date')
            if period == "annual":
                df = df[df['end_date'].astype(str).str.endswith('1231')]  # 仅保留年报
        return df
    except Exception as e:
        print(f"获取利润表失败: {e}")
        return pd.DataFrame()


def get_cash_flow(stock_code: str, period: str = "annual"):
    """获取现金流量表

    Tushare 字段：
      end_date: 报告期
      n_cashflow_act: 经营活动产生的现金流量净额
      c_fr_sale_sg: 销售商品、提供劳务收到的现金
      c_pay_acq_const_fiolta: 购建固定资产、无形资产和其他长期资产支付的现金
      free_cashflow: 自由现金流
    """
    try:
        pro = _get_ts_pro()
        if pro is None:
            return pd.DataFrame()
        ts_code = _ts_code(stock_code)
        fields = 'ts_code,end_date,n_cashflow_act,c_fr_sale_sg,c_pay_acq_const_fiolta,free_cashflow'
        df = pro.cashflow(ts_code=ts_code, fields=fields,
                          start_date='20000101', end_date='20261231')
        if df is not None and len(df) > 0:
            df = df.sort_values('end_date')
            if period == "annual":
                df = df[df['end_date'].astype(str).str.endswith('1231')]  # 仅保留年报
        return df
    except Exception as e:
        print(f"获取现金流量表失败: {e}")
        return pd.DataFrame()


def get_historical_prices(stock_code: str, years: int = 5):
    """获取历史股价（用于计算估值参考）"""
    try:
        pro = _get_ts_pro()
        if pro is None:
            return pd.DataFrame()
        ts_code = _ts_code(stock_code)
        import datetime
        end = datetime.datetime.now().strftime('%Y%m%d')
        start = (datetime.datetime.now() - datetime.timedelta(days=years*365)).strftime('%Y%m%d')
        df = pro.daily(ts_code=ts_code, start_date=start, end_date=end)
        if df is not None and len(df) > 0:
            df = df.sort_values('trade_date')
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            return df
    except Exception as e:
        print(f"获取历史股价失败: {e}")
    return pd.DataFrame()


def get_financial_indicators(stock_code: str):
    """获取财务指标

    Tushare 字段：
      end_date: 报告期
      roe: 净资产收益率（百分比，如 15.2 表示 15.2%）
      roa: 总资产净利率
      gross_margin: 销售毛利率
      netprofit_margin: 销售净利率
      eps: 基本每股收益
      bps: 每股净资产
      ocfps: 每股经营活动现金流

    注意：fina_indicator 单次最多返回100条记录，如需更多可通过设置日期范围多次请求。
    """
    try:
        pro = _get_ts_pro()
        if pro is None:
            return pd.DataFrame()
        ts_code = _ts_code(stock_code)
        fields = 'ts_code,end_date,roe,roa,gross_margin,netprofit_margin,eps,bps,ocfps'
        df = pro.fina_indicator(ts_code=ts_code, fields=fields,
                                start_date='20000101', end_date='20261231')
        if df is not None and len(df) > 0:
            df = df.sort_values('end_date')
        return df
    except Exception as e:
        print(f"获取财务指标失败: {e}")
    return pd.DataFrame()


def clean_financial_data(df: pd.DataFrame) -> pd.DataFrame:
    """清洗财务数据"""
    if df is None or len(df) == 0:
        return df
    df = df.copy()
    # 删除全空列
    df = df.dropna(axis=1, how='all')
    return df


def extract_key_financials(balance_df, income_df, cashflow_df, indicator_df=None) -> dict:
    """
    提取关键财务指标，供估值计算使用

    Tushare 版 — 使用英文字段名

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
        "roe_series": [],
        "gross_margin_series": [],
    }

    # 提取利润表关键数据
    if len(income_df) > 0 and 'end_date' in income_df.columns:
        recent = income_df.tail(5)
        for _, row in recent.iterrows():
            period = str(row.get('end_date', ''))
            result["years"].append(period[:4] if len(period) >= 4 else period)
            result["revenue"].append(float(row.get('revenue', 0) or 0))
            # n_income_attr_p 是归母净利润
            np_val = float(row.get('n_income_attr_p', 0) or 0)
            if np_val == 0:
                np_val = float(row.get('n_income', 0) or 0)
            result["net_profit"].append(np_val)

    # 提取资产负债表关键数据
    if len(balance_df) > 0 and 'end_date' in balance_df.columns:
        recent_bs = balance_df.tail(5)
        for _, row in recent_bs.iterrows():
            result["total_assets"].append(float(row.get('total_assets', 0) or 0))
            # total_hldr_eqy_exc_min_int 是归母股东权益
            eq_val = float(row.get('total_hldr_eqy_exc_min_int', 0) or 0)
            if eq_val == 0:
                eq_val = float(row.get('total_hldr_eqy_inc_min_int', 0) or 0)
            result["total_equity"].append(eq_val)
            result["total_liabilities"].append(float(row.get('total_liab', 0) or 0))

    # 提取现金流量表关键数据
    if len(cashflow_df) > 0 and 'end_date' in cashflow_df.columns:
        recent_cf = cashflow_df.tail(5)
        for _, row in recent_cf.iterrows():
            ocf = float(row.get('n_cashflow_act', 0) or 0)
            capex = float(row.get('c_pay_acq_const_fiolta', 0) or 0)
            result["operating_cash_flow"].append(ocf)
            result["capital_expenditure"].append(-abs(capex))  # 转为负值（与akshare一致）
            result["free_cash_flow"].append(ocf - abs(capex))

    # 提取财务指标
    if indicator_df is not None and len(indicator_df) > 0 and 'end_date' in indicator_df.columns:
        recent_ind = indicator_df.tail(5)
        for _, row in recent_ind.iterrows():
            roe_val = float(row.get('roe', 0) or 0) / 100.0  # Tushare 百分比 → 小数
            gm_val = float(row.get('gross_margin', 0) or 0) / 100.0
            result["roe_series"].append(roe_val)
            result["gross_margin_series"].append(gm_val)

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
    print(f"  {stock_name} ({stock_code}) · 财务数据获取（Tushare）")
    print(f"{'='*60}\n")

    # 获取财务数据（Tushare）
    balance_df = clean_financial_data(get_balance_sheet(stock_code, args.period))
    income_df = clean_financial_data(get_income_statement(stock_code, args.period))
    cashflow_df = clean_financial_data(get_cash_flow(stock_code, args.period))
    indicator_df = clean_financial_data(get_financial_indicators(stock_code))

    # 获取基本信息（Hermes JSON）
    stock_info = get_stock_info(stock_code)
    latest_price = get_stock_price(stock_code)

    print(f"  资产负债表: {len(balance_df)} 条")
    print(f"  利润表:     {len(income_df)} 条")
    print(f"  现金流量表: {len(cashflow_df)} 条")
    print(f"  财务指标:   {len(indicator_df)} 条")
    if latest_price > 0:
        print(f"  最新股价:   {latest_price:.2f}")

    # 提取关键指标
    key_data = extract_key_financials(balance_df, income_df, cashflow_df, indicator_df)

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
                if len(indicator_df) > 0:
                    indicator_df.to_excel(writer, sheet_name='财务指标', index=False)
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
            "indicator_records": len(indicator_df),
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
            if key_data["roe_series"]:
                print(f"\n  ROE:")
                for i, year in enumerate(key_data["years"]):
                    if i < len(key_data["roe_series"]):
                        roe_pct = key_data["roe_series"][i] * 100
                        print(f"    {year}: {roe_pct:.1f}%")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
