#!/usr/bin/env python3
"""
A股估值计算引擎

功能：
- 根据行业自动选择估值模型（行业映射由 industry_mapper.py 提供）
- 支持 PE / PB / DCF / PEG / EV-EBITDA / DDM / NAV 多种估值方法
- 输出估值区间和关键假设

用法：
  python calculate_valuation.py 600519 --model auto
  python calculate_valuation.py 600036 --model PB --wacc 0.085
  python calculate_valuation.py 000858 --model auto --output /tmp/valuation.json
"""

import sys
import json
import argparse
import subprocess
import os

# 导入共享数据模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_fetcher import (
    get_stock_name, get_stock_price, get_shares_outstanding,
    get_stock_industry_name, get_market_cap, get_pe_ratio, get_pb_ratio,
    get_financial_data_from_json
)


# ============================================================
# 估值计算核心函数
# ============================================================

# get_stock_name / get_stock_price / get_shares_outstanding 已从 data_fetcher 导入

def get_latest_price(stock_code: str) -> float:
    """获取最新股价（别名，兼容内部调用）"""
    return get_stock_price(stock_code)







    if len(income_df) >= 4:
        recent_rev = income_df.tail(4)['营业收入'].apply(safe_float).values
        if recent_rev[0] > 0 and recent_rev[-1] > 0:
            result["revenue_cagr_3y"] = (recent_rev[-1] / recent_rev[0]) ** (1 / 3) - 1

    return result




# ============================================================
# 估值模型实现
# ============================================================

def pe_valuation(financials: dict, price: float, params: dict) -> dict:
    """
    PE估值法
    估值 = EPS × 合理PE
    """
    shares = params.get("shares_outstanding", 0) or 1
    net_profit = financials.get("net_profit", 0)
    eps = net_profit / (shares * 1e8) if shares > 0 else 0

    pe_low = params.get("pe_threshold_undervalue", 15)
    pe_high = params.get("pe_threshold_overvalue", 30)
    pe_mid = (pe_low + pe_high) / 2

    growth_rate = financials.get("net_profit_cagr_3y") or params.get("default_growth_rate") or 0.10
    # PEG=1时的合理PE，但不低于行业低估阈值（避免低增长高ROE公司被过度惩罚）
    peg_fair_pe = growth_rate * 100 if growth_rate > 0 else pe_mid
    peg_fair_pe = max(peg_fair_pe, pe_low)  # 地板保护

    value_low = eps * min(pe_low, peg_fair_pe * 0.8)
    value_mid = eps * peg_fair_pe
    value_high = eps * pe_high

    return {
        "model": "PE",
        "eps": round(eps, 4),
        "pe_range": f"{pe_low:.0f}x - {pe_high:.0f}x",
        "peg_fair_pe": round(peg_fair_pe, 1),
        "value_low": round(value_low, 2),
        "value_mid": round(value_mid, 2),
        "value_high": round(value_high, 2),
        "current_price": round(price, 2),
        "upside_low": f"{(value_low/price - 1)*100:.1f}%" if price > 0 else "N/A",
        "upside_mid": f"{(value_mid/price - 1)*100:.1f}%" if price > 0 else "N/A",
        "upside_high": f"{(value_high/price - 1)*100:.1f}%" if price > 0 else "N/A",
    }


def pb_valuation(financials: dict, price: float, params: dict) -> dict:
    """
    PB估值法
    估值 = 每股净资产 × 合理PB
    """
    shares = params.get("shares_outstanding", 0) or 1
    equity = financials.get("total_equity", 0)
    bvps = equity / (shares * 1e8) if shares > 0 else 0
    roe = financials.get("roe", 0.10)

    # 合理PB ≈ ROE / 要求回报率
    required_return = params.get("default_wacc", 0.09)
    fair_pb = roe / required_return if required_return > 0 else 1.5

    pb_low = params.get("pb_threshold_undervalue", 1.0)
    pb_high = params.get("pb_threshold_overvalue", 2.0)

    value_low = bvps * pb_low
    value_mid = bvps * fair_pb
    value_high = bvps * pb_high

    return {
        "model": "PB",
        "bvps": round(bvps, 4),
        "pb_range": f"{pb_low:.1f}x - {pb_high:.1f}x",
        "fair_pb": round(fair_pb, 2),
        "roe": f"{roe*100:.1f}%",
        "value_low": round(value_low, 2),
        "value_mid": round(value_mid, 2),
        "value_high": round(value_high, 2),
        "current_price": round(price, 2),
        "upside_low": f"{(value_low/price - 1)*100:.1f}%" if price > 0 else "N/A",
        "upside_mid": f"{(value_mid/price - 1)*100:.1f}%" if price > 0 else "N/A",
        "upside_high": f"{(value_high/price - 1)*100:.1f}%" if price > 0 else "N/A",
    }


def dcf_valuation(financials: dict, price: float, params: dict) -> dict:
    """
    DCF现金流折现估值法
    内在价值 = Σ(FCF_t / (1+WACC)^t) + 终值/(1+WACC)^n
    """
    wacc = params.get("default_wacc", 0.09)
    growth_rate = financials.get("net_profit_cagr_3y") or params.get("default_growth_rate") or 0.12
    terminal_growth = params.get("terminal_growth_rate", 0.03)
    shares = params.get("shares_outstanding", 0) or 1

    # 使用最近一期自由现金流
    base_fcf = financials.get("fcf", financials.get("operating_cf", 0))
    if base_fcf <= 0:
        # 降级：用净利润的80%估算FCF
        base_fcf = financials.get("net_profit", 0) * 0.8

    if base_fcf <= 0:
        return {"model": "DCF", "error": "自由现金流为负，无法进行DCF估值"}

    # 预测10年
    years = 10
    projections = []
    total_pv = 0
    fcf = base_fcf

    for t in range(1, years + 1):
        # 前5年用高增长，后5年线性衰减到永续增长率
        if t <= 5:
            fcf_growth = growth_rate
        else:
            fcf_growth = growth_rate - (growth_rate - terminal_growth) * (t - 5) / 5

        fcf = fcf * (1 + fcf_growth)
        pv = fcf / ((1 + wacc) ** t)
        total_pv += pv
        projections.append({
            "year": t,
            "fcf": round(fcf / 1e8, 2),
            "growth_rate": f"{fcf_growth*100:.1f}%",
            "pv": round(pv / 1e8, 2),
        })

    # 终值（永续增长模型）
    terminal_value = fcf * (1 + terminal_growth) / (wacc - terminal_growth)
    terminal_pv = terminal_value / ((1 + wacc) ** years)

    enterprise_value = total_pv + terminal_pv
    equity_value = enterprise_value  # 简化：假设无净负债

    per_share_value = equity_value / (shares * 1e8) if shares > 0 else 0

    # 敏感度分析（WACC ±1%，增长率 ±1%）
    sensitivity = {}
    for w in [wacc - 0.01, wacc, wacc + 0.01]:
        for g in [growth_rate - 0.02, growth_rate, growth_rate + 0.02]:
            if w <= terminal_growth:
                continue
            key = f"WACC={w*100:.0f}% G={g*100:.0f}%"
            # 简化重算
            f = base_fcf
            tv_pv = 0
            for t2 in range(1, years + 1):
                if t2 <= 5:
                    fg = g
                else:
                    fg = g - (g - terminal_growth) * (t2 - 5) / 5
                f = f * (1 + fg)
                tv_pv += f / ((1 + w) ** t2)
            tv = f * (1 + terminal_growth) / (w - terminal_growth)
            tv_pv += tv / ((1 + w) ** years)
            sensitivity[key] = round(tv_pv / (shares * 1e8), 2) if shares > 0 else 0

    value_low = min(sensitivity.values()) if sensitivity else per_share_value * 0.7
    value_high = max(sensitivity.values()) if sensitivity else per_share_value * 1.3

    return {
        "model": "DCF",
        "wacc": f"{wacc*100:.1f}%",
        "growth_rate": f"{growth_rate*100:.1f}%",
        "terminal_growth": f"{terminal_growth*100:.1f}%",
        "base_fcf": round(base_fcf / 1e8, 2),
        "projections": projections[:5],  # 只展示前5年
        "value_low": round(value_low, 2),
        "value_mid": round(per_share_value, 2),
        "value_high": round(value_high, 2),
        "current_price": round(price, 2),
        "upside_mid": f"{(per_share_value/price - 1)*100:.1f}%" if price > 0 else "N/A",
        "sensitivity": sensitivity,
    }


def peg_valuation(financials: dict, price: float, params: dict) -> dict:
    """
    PEG估值法
    合理PE = 增长率 × 100（PEG=1时）
    """
    growth_rate = financials.get("net_profit_cagr_3y") or params.get("default_growth_rate") or 0.15
    shares = params.get("shares_outstanding", 0) or 1

    net_profit = financials.get("net_profit", 0)
    eps = net_profit / (shares * 1e8) if shares > 0 else 0

    if growth_rate <= 0:
        growth_rate = 0.10  # 默认10%

    fair_pe = growth_rate * 100
    fair_pe = max(10, min(fair_pe, 50))  # 限制PE范围

    value_low = eps * fair_pe * 0.7  # PEG=0.7
    value_mid = eps * fair_pe        # PEG=1.0
    value_high = eps * fair_pe * 1.3  # PEG=1.3

    return {
        "model": "PEG",
        "eps": round(eps, 4),
        "growth_rate": f"{growth_rate*100:.1f}%",
        "fair_pe": round(fair_pe, 1),
        "value_low": round(value_low, 2),
        "value_mid": round(value_mid, 2),
        "value_high": round(value_high, 2),
        "current_price": round(price, 2),
        "upside_low": f"{(value_low/price - 1)*100:.1f}%" if price > 0 else "N/A",
        "upside_mid": f"{(value_mid/price - 1)*100:.1f}%" if price > 0 else "N/A",
        "upside_high": f"{(value_high/price - 1)*100:.1f}%" if price > 0 else "N/A",
    }


def ev_ebitda_valuation(financials: dict, price: float, params: dict) -> dict:
    """
    EV/EBITDA估值法
    """
    shares = params.get("shares_outstanding", 0) or 1
    net_profit = financials.get("net_profit", 0)
    revenue = financials.get("revenue", 0)

    # 简化：EBITDA ≈ 净利润 + 折旧摊销（用营业收入的5%估算）
    ebitda = net_profit + revenue * 0.05

    # 企业价值 = EBITDA × 合理倍数
    ev_ebitda_low = 8
    ev_ebitda_high = 20
    ev_ebitda_mid = 12

    ev_low = ebitda * ev_ebitda_low
    ev_mid = ebitda * ev_ebitda_mid
    ev_high = ebitda * ev_ebitda_high

    # 股权价值 = EV - 净负债（简化：假设无净负债）
    per_share_low = ev_low / (shares * 1e8) if shares > 0 else 0
    per_share_mid = ev_mid / (shares * 1e8) if shares > 0 else 0
    per_share_high = ev_high / (shares * 1e8) if shares > 0 else 0

    return {
        "model": "EV/EBITDA",
        "ebitda": round(ebitda / 1e8, 2),
        "ev_ebitda_range": f"{ev_ebitda_low}x - {ev_ebitda_high}x",
        "value_low": round(per_share_low, 2),
        "value_mid": round(per_share_mid, 2),
        "value_high": round(per_share_high, 2),
        "current_price": round(price, 2),
        "upside_mid": f"{(per_share_mid/price - 1)*100:.1f}%" if price > 0 else "N/A",
    }


def ddm_valuation(financials: dict, price: float, params: dict) -> dict:
    """
    DDM股息折现模型（适用于公用事业/银行等高分红行业）
    """
    wacc = params.get("default_wacc", 0.07)
    terminal_growth = params.get("terminal_growth_rate", 0.02)
    shares = params.get("shares_outstanding", 0) or 1

    net_profit = financials.get("net_profit", 0)
    # 假设分红率30%
    dividend = net_profit * 0.30

    if wacc <= terminal_growth:
        return {"model": "DDM", "error": "WACC必须大于永续增长率"}

    dps = dividend / (shares * 1e8) if shares > 0 else 0

    # Gordon Growth Model: P = DPS / (r - g)
    fair_value = dps / (wacc - terminal_growth)
    value_low = fair_value * 0.8
    value_high = fair_value * 1.2

    return {
        "model": "DDM",
        "dps": round(dps, 4),
        "dividend_yield": f"{(dps/price)*100:.2f}%" if price > 0 else "N/A",
        "wacc": f"{wacc*100:.1f}%",
        "terminal_growth": f"{terminal_growth*100:.1f}%",
        "value_low": round(value_low, 2),
        "value_mid": round(fair_value, 2),
        "value_high": round(value_high, 2),
        "current_price": round(price, 2),
        "upside_mid": f"{(fair_value/price - 1)*100:.1f}%" if price > 0 else "N/A",
    }


# ============================================================
# 主逻辑
# ============================================================

MODEL_EXECUTORS = {
    "PE": pe_valuation,
    "PB": pb_valuation,
    "DCF": dcf_valuation,
    "PEG": peg_valuation,
    "EV/EBITDA": ev_ebitda_valuation,
    "DDM": ddm_valuation,
}


def run_industry_mapper(stock_code: str) -> dict:
    """调用 industry_mapper.py 获取行业模型配置"""
    try:
        script_dir = "/".join(__file__.split("/")[:-1])
        mapper_path = f"{script_dir}/industry_mapper.py" if script_dir else "industry_mapper.py"
        result = subprocess.run(
            ["python3", mapper_path, "--stock-code", stock_code, "--json"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            # 提取JSON部分
            output = result.stdout
            json_start = output.find("{")
            if json_start >= 0:
                return json.loads(output[json_start:])
    except Exception as e:
        print(f"调用行业映射失败: {e}")
    return {}


def main():
    parser = argparse.ArgumentParser(description="A股估值计算引擎")
    parser.add_argument("stock_code", type=str, help="股票代码，如600519")
    parser.add_argument("--model", type=str, default="auto",
                        help="估值模型：auto/PE/PB/DCF/PEG/EV-EBITDA/DDM")
    parser.add_argument("--wacc", type=float, help="手动指定WACC")
    parser.add_argument("--growth-rate", type=float, help="手动指定增长率")
    parser.add_argument("--terminal-growth", type=float, help="手动指定永续增长率")
    parser.add_argument("--output", type=str, help="输出JSON文件路径")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    args = parser.parse_args()

    stock_code = args.stock_code
    stock_name = get_stock_name(stock_code)
    price = get_latest_price(stock_code)

    print(f"\n{'='*60}")
    print(f"  {stock_name} ({stock_code}) · 估值分析")
    print(f"{'='*60}")
    print(f"  当前价格: {price:.2f}" if price > 0 else "  当前价格: 获取失败")

    # 获取行业模型配置
    industry_config = run_industry_mapper(stock_code)

    # 获取财务数据（从 Hermes JSON）
    financials = get_financial_data_from_json(stock_code)
    shares = get_shares_outstanding(stock_code)

    # 构建参数
    model_params = industry_config.get("model_params", {})
    if args.wacc:
        model_params["default_wacc"] = args.wacc
    if args.growth_rate:
        model_params["default_growth_rate"] = args.growth_rate
    if args.terminal_growth:
        model_params["terminal_growth_rate"] = args.terminal_growth
    model_params["shares_outstanding"] = shares

    # 确定使用的模型
    if args.model == "auto":
        primary = industry_config.get("primary_model", "PE")
        secondary = industry_config.get("secondary_models", [])
    else:
        primary = args.model
        secondary = []

    print(f"  行业分类:  {industry_config.get('matched_category', '未知')}")
    print(f"  首选模型:  {primary}")
    if secondary:
        print(f"  辅助模型:  {', '.join(secondary[:2])}")

    # 估值摘要
    print(f"\n  关键财务数据:")
    print(f"    营业收入:  {financials.get('revenue', 0)/1e8:.2f} 亿")
    print(f"    净利润:    {financials.get('net_profit', 0)/1e8:.2f} 亿")
    if financials.get("roe"):
        print(f"    ROE:       {financials['roe']*100:.1f}%")
    if financials.get("net_profit_cagr_3y"):
        print(f"    3年CAGR:   {financials['net_profit_cagr_3y']*100:.1f}%")
    print(f"    总股本:    {shares:.2f} 亿股" if shares > 0 else "    总股本:    获取失败")

    # 执行估值
    all_results = {}
    models_to_run = [primary] + secondary[:1]  # 首选+最多1个辅助

    print(f"\n{'='*60}")
    print(f"  估值结果")
    print(f"{'='*60}")

    for model_name in models_to_run:
        if model_name in MODEL_EXECUTORS:
            try:
                result = MODEL_EXECUTORS[model_name](financials, price, model_params)
                all_results[model_name] = result

                if "error" in result:
                    print(f"\n  [{model_name}] {result['error']}")
                else:
                    print(f"\n  【{model_name}估值】")
                    print(f"    估值区间: {result['value_low']:.2f} ~ {result['value_high']:.2f} 元")
                    print(f"    估值中值: {result['value_mid']:.2f} 元")
                    print(f"    隐含空间: {result.get('upside_mid', 'N/A')}")
                    if model_name == "PE":
                        print(f"    EPS: {result['eps']:.2f}, PE范围: {result['pe_range']}")
                    elif model_name == "PB":
                        print(f"    BVPS: {result['bvps']:.2f}, PB范围: {result['pb_range']}, ROE: {result.get('roe', 'N/A')}")
                    elif model_name == "DCF":
                        print(f"    WACC: {result['wacc']}, 增长率: {result['growth_rate']}, 终值增长率: {result['terminal_growth']}")
                    elif model_name == "PEG":
                        print(f"    EPS: {result['eps']:.2f}, 增长率: {result['growth_rate']}, 合理PE: {result['fair_pe']}x")
            except Exception as e:
                print(f"\n  [{model_name}] 估值失败: {e}")

    # 综合结论
    print(f"\n{'='*60}")
    print(f"  综合估值结论")
    print(f"{'='*60}")

    primary_result = all_results.get(primary, {})
    if primary_result and "error" not in primary_result:
        mid = primary_result["value_mid"]
        if price > 0:
            deviation = (mid / price - 1) * 100
            if deviation > 20:
                verdict = "🟢 显著低估"
            elif deviation > 5:
                verdict = "🟡 略低估"
            elif deviation > -5:
                verdict = "⚪ 合理估值"
            elif deviation > -20:
                verdict = "🟠 略高估"
            else:
                verdict = "🔴 显著高估"
            print(f"  判断: {verdict}")
            print(f"  自有估值中值: {mid:.2f} 元")
            print(f"  当前价格:     {price:.2f} 元")
            print(f"  偏差:         {deviation:+.1f}%")
        print(f"  核心模型:     {primary}")
        print(f"  行业分类:     {industry_config.get('matched_category', '未知')}")
        notes = industry_config.get("notes", "")
        if notes:
            print(f"  行业说明:     {notes}")
    else:
        print(f"  无法生成估值结论，请检查数据获取是否正常")

    # 机构验证层
    inst = financials.get("institutional", {})
    if inst:
        print(f"\n{'─'*60}")
        print(f"  机构验证（恒生聚源 180天窗口）")
        print(f"{'─'*60}")
        rt = inst.get("rating", {})
        if rt:
            print(f"  评级: {rt.get('buy',0)}买 {rt.get('add',0)}增 {rt.get('neutral',0)}中性 | "
                  f"共{rt.get('total',0)}次 标准分{rt.get('std_score','?')} | {rt.get('org_count',0)}家机构")
        tp = inst.get("target_price", {})
        if tp and tp.get("median"):
            tp_dev = (tp["median"] / price - 1) * 100 if price > 0 else 0
            print(f"  目标价: 均价{tp['avg']:.2f} | 中位数{tp['median']:.2f} | 偏差{tp_dev:+.1f}% | {tp.get('org_count',0)}家机构")
        eps = inst.get("eps_forecast", [])
        if eps:
            parts = []
            for ep in eps[:3]:
                yoy_str = f" 增速{ep['np_yoy']:.1f}%" if ep.get('np_yoy') is not None else ""
                parts.append(f"{ep['level']} EPS={ep['eps_avg']:.2f}{yoy_str} ({ep['inst_count']}家)")
            print(f"  盈利预测: {' | '.join(parts)}")
        # 机构 vs 自有估值交叉验证
        tp_median = tp.get("median")
        if tp_median and primary_result and "error" not in primary_result:
            own_mid = primary_result["value_mid"]
            tp_vs_own = (tp_median / own_mid - 1) * 100 if own_mid > 0 else 0
            print(f"  交叉验证: 机构目标{tp_median:.2f} vs 自有估值{own_mid:.2f} → 机构比自有高{tp_vs_own:+.1f}%")

    print(f"{'='*60}\n")

    # 输出JSON
    output_data = {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "current_price": price,
        "industry": industry_config.get("matched_category", "未知"),
        "primary_model": primary,
        "financials_summary": {
            "revenue": round(financials.get("revenue", 0) / 1e8, 2),
            "net_profit": round(financials.get("net_profit", 0) / 1e8, 2),
            "roe": round(financials.get("roe", 0) * 100, 1) if financials.get("roe") else None,
            "cagr_3y": round(financials.get("net_profit_cagr_3y", 0) * 100, 1) if financials.get("net_profit_cagr_3y") else None,
        },
        "valuation_results": all_results,
        "institutional_validation": {
            "rating": inst.get("rating") if inst else None,
            "target_price": inst.get("target_price") if inst else None,
            "eps_forecast": inst.get("eps_forecast") if inst else None,
        } if inst else None,
    }

    if args.json or args.output:
        json_str = json.dumps(output_data, ensure_ascii=False, indent=2, default=str)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(json_str)
            print(f"结果已保存: {args.output}")
        elif args.json:
            print(json_str)


if __name__ == "__main__":
    main()
