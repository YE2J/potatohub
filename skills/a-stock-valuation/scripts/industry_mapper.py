#!/usr/bin/env python3
"""
行业→估值模型映射引擎

功能：
- 通过akshare获取股票所属申万行业分类
- 根据行业自动推荐估值模型
- 返回模型参数配置

用法：
  python industry_mapper.py --stock-code 600519
  python industry_mapper.py --stock-code 600036 --json
"""

import sys
import json
import argparse
import pandas as pd
import akshare as ak


# ============================================================
# 行业→估值模型映射配置
# ============================================================
INDUSTRY_MODEL_MAP = {
    "银行": {
        "primary_model": "PB",
        "secondary_models": ["股息率", "RORE"],
        "key_metrics": ["不良贷款率", "拨备覆盖率", "净息差", "核心一级资本充足率"],
        "default_wacc": 0.085,
        "pb_threshold_undervalue": 0.8,
        "pb_threshold_overvalue": 1.5,
        "notes": "银行股以PB为核心，辅以股息率和RORE（净资产收益率回报率）"
    },
    "保险": {
        "primary_model": "PB",
        "secondary_models": ["内含价值倍数", "PEV"],
        "key_metrics": ["新业务价值", "内含价值", "综合成本率"],
        "default_wacc": 0.09,
        "pb_threshold_undervalue": 0.8,
        "pb_threshold_overvalue": 1.5,
        "notes": "保险股关注内含价值(EV)和新业务价值(NBV)"
    },
    "证券": {
        "primary_model": "PB",
        "secondary_models": ["PE", "ROE"],
        "key_metrics": ["ROE", "经纪业务占比", "自营业务收益率"],
        "default_wacc": 0.09,
        "pb_threshold_undervalue": 1.0,
        "pb_threshold_overvalue": 2.5,
        "notes": "券商周期性强，PB+ROE结合判断"
    },
    "计算机": {
        "primary_model": "DCF",
        "secondary_models": ["PEG", "PS"],
        "key_metrics": ["研发费用率", "用户增速", "市占率", "ARR/MRR"],
        "default_wacc": 0.10,
        "default_growth_rate": 0.15,
        "terminal_growth_rate": 0.03,
        "notes": "科技股关注研发投入和用户增长，DCF为主"
    },
    "电子": {
        "primary_model": "PEG",
        "secondary_models": ["DCF", "PE"],
        "key_metrics": ["研发占比", "毛利率趋势", "产能利用率"],
        "default_wacc": 0.10,
        "default_growth_rate": 0.12,
        "terminal_growth_rate": 0.03,
        "notes": "电子行业关注技术迭代和产能周期"
    },
    "传媒": {
        "primary_model": "PEG",
        "secondary_models": ["PS", "DCF"],
        "key_metrics": ["用户增速", "ARPU", "内容成本率"],
        "default_wacc": 0.10,
        "default_growth_rate": 0.12,
        "terminal_growth_rate": 0.03,
        "notes": "互联网/传媒看用户和变现能力"
    },
    "通信": {
        "primary_model": "PE",
        "secondary_models": ["EV/EBITDA", "DCF"],
        "key_metrics": ["CAPEX/营收", "ARPU", "用户数"],
        "default_wacc": 0.09,
        "terminal_growth_rate": 0.025,
        "notes": "通信运营商看稳定现金流和CAPEX"
    },
    "食品饮料": {
        "primary_model": "PE",
        "secondary_models": ["PEG", "EV/EBITDA"],
        "key_metrics": ["毛利率", "净利率", "ROE", "品牌力"],
        "default_wacc": 0.09,
        "pe_threshold_undervalue": 20,
        "pe_threshold_overvalue": 40,
        "notes": "消费龙头看品牌溢价和稳定增长"
    },
    "家用电器": {
        "primary_model": "PE",
        "secondary_models": ["EV/EBITDA", "PEG"],
        "key_metrics": ["毛利率", "海外收入占比", "市占率"],
        "default_wacc": 0.09,
        "pe_threshold_undervalue": 12,
        "pe_threshold_overvalue": 25,
        "notes": "家电看品牌+渠道+海外扩张"
    },
    "汽车": {
        "primary_model": "PE",
        "secondary_models": ["PEG", "EV/EBITDA"],
        "key_metrics": ["新能源车占比", "毛利率", "研发费用率"],
        "default_wacc": 0.10,
        "pe_threshold_undervalue": 15,
        "pe_threshold_overvalue": 35,
        "notes": "汽车关注新能源转型和智能化"
    },
    "纺织服饰": {
        "primary_model": "PE",
        "secondary_models": ["PEG", "EV/EBITDA"],
        "key_metrics": ["毛利率", "同店增速", "存货周转率"],
        "default_wacc": 0.09,
        "pe_threshold_undervalue": 15,
        "pe_threshold_overvalue": 30,
        "notes": "消费品看品牌力和渠道效率"
    },
    "医药生物": {
        "primary_model": "DCF",
        "secondary_models": ["峰值销售额折现", "PEG"],
        "key_metrics": ["研发费用率", "管线进度", "在研产品数", "获批概率"],
        "default_wacc": 0.10,
        "default_growth_rate": 0.12,
        "terminal_growth_rate": 0.03,
        "notes": "医药看管线价值，创新药用DCF+峰值销售额折现"
    },
    "房地产": {
        "primary_model": "NAV",
        "secondary_models": ["PB"],
        "key_metrics": ["土储货值", "去化率", "净负债率", "融资成本"],
        "default_wacc": 0.10,
        "pb_threshold_undervalue": 0.5,
        "pb_threshold_overvalue": 1.0,
        "notes": "地产看土储价值(NAV)和资产负债表质量"
    },
    "公用事业": {
        "primary_model": "DDM",
        "secondary_models": ["PB"],
        "key_metrics": ["股息率", "利用率", "电价/水价", "CAPEX计划"],
        "default_wacc": 0.07,
        "terminal_growth_rate": 0.02,
        "notes": "公用事业看稳定分红(DDM)和资产价值(PB)"
    },
    "电力设备": {
        "primary_model": "PEG",
        "secondary_models": ["DCF", "PE"],
        "key_metrics": ["装机量", "渗透率", "毛利率", "订单增速"],
        "default_wacc": 0.09,
        "default_growth_rate": 0.18,
        "terminal_growth_rate": 0.03,
        "notes": "新能源电力设备看装机增速和渗透率提升"
    },
    "有色金属": {
        "primary_model": "PB",
        "secondary_models": ["周期调整PE"],
        "key_metrics": ["商品价格", "产能利用率", "库存周期", "吨成本"],
        "default_wacc": 0.10,
        "pb_threshold_undervalue": 1.0,
        "pb_threshold_overvalue": 3.0,
        "notes": "资源周期股看商品价格和产能周期"
    },
    "煤炭": {
        "primary_model": "PB",
        "secondary_models": ["股息率", "周期调整PE"],
        "key_metrics": ["煤价", "长协占比", "吨煤成本", "股息率"],
        "default_wacc": 0.09,
        "pb_threshold_undervalue": 0.8,
        "pb_threshold_overvalue": 2.0,
        "notes": "煤炭看煤价周期和分红能力"
    },
    "钢铁": {
        "primary_model": "PB",
        "secondary_models": ["周期调整PE"],
        "key_metrics": ["钢价", "吨钢毛利", "产能利用率"],
        "default_wacc": 0.10,
        "pb_threshold_undervalue": 0.6,
        "pb_threshold_overvalue": 1.5,
        "notes": "钢铁强周期，PB+产能周期判断"
    },
    "石油石化": {
        "primary_model": "PB",
        "secondary_models": ["PE", "EV/EBITDA"],
        "key_metrics": ["油价", "炼化毛利", "储量替代率"],
        "default_wacc": 0.09,
        "pb_threshold_undervalue": 0.8,
        "pb_threshold_overvalue": 2.0,
        "notes": "石油看油价中枢和储量价值"
    },
    "基础化工": {
        "primary_model": "PE",
        "secondary_models": ["PB", "EV/EBITDA"],
        "key_metrics": ["产品价差", "产能利用率", "毛利率"],
        "default_wacc": 0.09,
        "pe_threshold_undervalue": 12,
        "pe_threshold_overvalue": 25,
        "notes": "化工看产品周期和价差"
    },
    "建筑装饰": {
        "primary_model": "PE",
        "secondary_models": ["PB", "EV/EBITDA"],
        "key_metrics": ["新签订单增速", "在手订单", "毛利率", "现金流"],
        "default_wacc": 0.09,
        "pe_threshold_undervalue": 8,
        "pe_threshold_overvalue": 20,
        "notes": "建筑看订单增速和现金流质量"
    },
    "交通运输": {
        "primary_model": "PE",
        "secondary_models": ["EV/EBITDA", "DCF"],
        "key_metrics": ["客/货运量", "票价/运价", "燃油成本占比"],
        "default_wacc": 0.08,
        "pe_threshold_undervalue": 12,
        "pe_threshold_overvalue": 25,
        "notes": "交通运输看运量和定价能力"
    },
    "国防军工": {
        "primary_model": "PEG",
        "secondary_models": ["PS", "DCF"],
        "key_metrics": ["在手订单", "研发占比", "军品占比", "毛利率"],
        "default_wacc": 0.09,
        "default_growth_rate": 0.15,
        "terminal_growth_rate": 0.03,
        "notes": "军工看订单和研发驱动增长"
    },
    "农林牧渔": {
        "primary_model": "PE",
        "secondary_models": ["PB", "周期调整PE"],
        "key_metrics": ["猪价/粮价", "出栏量", "成本控制", "存栏量"],
        "default_wacc": 0.09,
        "pe_threshold_undervalue": 10,
        "pe_threshold_overvalue": 30,
        "notes": "农业强周期，关注价格和成本"
    },
    "社会服务": {
        "primary_model": "PE",
        "secondary_models": ["PEG", "EV/EBITDA"],
        "key_metrics": ["RevPAR", "客流增速", "客单价"],
        "default_wacc": 0.09,
        "pe_threshold_undervalue": 20,
        "pe_threshold_overvalue": 45,
        "notes": "消费服务看客流和客单价"
    },
    "商贸零售": {
        "primary_model": "PE",
        "secondary_models": ["PS", "EV/EBITDA"],
        "key_metrics": ["同店增速", "GMV", "毛利率", "坪效"],
        "default_wacc": 0.09,
        "pe_threshold_undervalue": 15,
        "pe_threshold_overvalue": 35,
        "notes": "零售看同店增长和坪效"
    },
    "机械设备": {
        "primary_model": "PE",
        "secondary_models": ["EV/EBITDA", "PEG"],
        "key_metrics": ["订单增速", "毛利率", "海外收入占比"],
        "default_wacc": 0.09,
        "pe_threshold_undervalue": 15,
        "pe_threshold_overvalue": 35,
        "notes": "制造业看订单和毛利率趋势"
    },
    "轻工制造": {
        "primary_model": "PE",
        "secondary_models": ["EV/EBITDA", "PB"],
        "key_metrics": ["毛利率", "出口占比", "原材料成本占比"],
        "default_wacc": 0.09,
        "pe_threshold_undervalue": 12,
        "pe_threshold_overvalue": 28,
        "notes": "轻工制造看成本控制和出口景气度"
    },
}


def get_stock_industry(stock_code: str) -> dict:
    """
    获取股票所属行业分类

    优先使用申万行业分类，降级使用东方财富行业分类

    Args:
        stock_code: 6位股票代码

    Returns:
        dict: 包含行业信息的字典
    """
    result = {
        "stock_code": stock_code,
        "industry": "未知",
        "industry_level2": "",
        "matched_category": None,
        "model_config": None,
    }

    try:
        # 尝试获取申万行业分类
        print(f"正在获取 {stock_code} 的行业分类...")
        try:
            industry_df = ak.stock_board_industry_name_em()
            # 获取个股所属行业
            stock_industry = ak.stock_individual_info_em(symbol=stock_code)
            industry_name = None
            if isinstance(stock_industry, pd.DataFrame):
                industry_row = stock_industry[stock_industry['item'] == '行业']
                if len(industry_row) > 0:
                    industry_name = industry_row['value'].values[0]
            result["industry"] = industry_name or "未知"
        except Exception:
            pass

        # 匹配行业分类
        for industry_key, model_config in INDUSTRY_MODEL_MAP.items():
            if result["industry"] and industry_key in result["industry"]:
                result["matched_category"] = industry_key
                result["model_config"] = model_config
                break

        # 如果未匹配，使用通用配置
        if result["matched_category"] is None:
            result["matched_category"] = "通用（制造业）"
            result["model_config"] = INDUSTRY_MODEL_MAP["机械设备"]

        print(f"  行业: {result['industry']}")
        print(f"  匹配分类: {result['matched_category']}")
        print(f"  推荐模型: {result['model_config']['primary_model']}")
        if result['model_config'].get('secondary_models'):
            print(f"  辅助模型: {', '.join(result['model_config']['secondary_models'])}")

        return result

    except Exception as e:
        print(f"获取行业分类失败: {e}")
        result["matched_category"] = "通用（制造业）"
        result["model_config"] = INDUSTRY_MODEL_MAP["机械设备"]
        return result


def get_stock_name(stock_code: str) -> str:
    """获取股票名称"""
    try:
        info = ak.stock_individual_info_em(symbol=stock_code)
        if isinstance(info, pd.DataFrame):
            name_row = info[info['item'] == '股票简称']
            if len(name_row) > 0:
                return name_row['value'].values[0]
    except Exception:
        pass
    return stock_code


def get_stock_price(stock_code: str) -> float:
    """获取最新股价"""
    try:
        df = ak.stock_zh_a_hist(symbol=stock_code, period='daily', adjust='qfq')
        if len(df) > 0:
            return float(df.iloc[-1]['收盘'])
    except Exception:
        pass
    return 0.0


def main():
    parser = argparse.ArgumentParser(description="行业→估值模型映射引擎")
    parser.add_argument("--stock-code", type=str, required=True, help="股票代码，如600519")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    args = parser.parse_args()

    stock_code = args.stock_code

    # 获取行业分类和模型配置
    result = get_stock_industry(stock_code)

    # 获取补充信息
    stock_name = get_stock_name(stock_code)
    stock_price = get_stock_price(stock_code)

    result["stock_name"] = stock_name
    result["current_price"] = stock_price

    if args.json:
        # JSON输出，便于程序调用
        output = {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "current_price": stock_price,
            "industry": result["industry"],
            "matched_category": result["matched_category"],
            "primary_model": result["model_config"]["primary_model"],
            "secondary_models": result["model_config"].get("secondary_models", []),
            "key_metrics": result["model_config"].get("key_metrics", []),
            "model_params": {
                "default_wacc": result["model_config"].get("default_wacc", 0.09),
                "default_growth_rate": result["model_config"].get("default_growth_rate"),
                "terminal_growth_rate": result["model_config"].get("terminal_growth_rate", 0.025),
                "pe_threshold_undervalue": result["model_config"].get("pe_threshold_undervalue"),
                "pe_threshold_overvalue": result["model_config"].get("pe_threshold_overvalue"),
                "pb_threshold_undervalue": result["model_config"].get("pb_threshold_undervalue"),
                "pb_threshold_overvalue": result["model_config"].get("pb_threshold_overvalue"),
            },
            "notes": result["model_config"].get("notes", ""),
        }
        print("\n" + json.dumps(output, ensure_ascii=False, indent=2))
    else:
        # 友好文本输出
        print(f"\n{'='*60}")
        print(f"  {stock_name} ({stock_code}) · 行业→估值模型匹配")
        print(f"{'='*60}")
        print(f"  所属行业:    {result['industry']}")
        print(f"  匹配分类:    {result['matched_category']}")
        print(f"  当前价格:    {stock_price:.2f}" if stock_price > 0 else "  当前价格:    获取失败")
        print(f"  首选模型:    {result['model_config']['primary_model']}")
        print(f"  辅助模型:    {', '.join(result['model_config'].get('secondary_models', []))}")
        print(f"  关键指标:    {', '.join(result['model_config'].get('key_metrics', []))}")
        print(f"  默认WACC:    {result['model_config'].get('default_wacc', 0.09):.1%}")
        print(f"  估值说明:    {result['model_config'].get('notes', '')}")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
