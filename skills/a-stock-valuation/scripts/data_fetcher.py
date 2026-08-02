#!/usr/bin/env python3
"""
数据获取共享模块
优先从 Hermes web_extract 生成的 JSON 文件读取，降级到 Tushare

Hermes 获取数据后存到: ~/.hermes/skills/a-stock-valuation/data/{code}_{type}.json
本模块统一读取这些文件，三个脚本不需要各自处理数据源。

新增股票时，让 Hermes 执行:
  curl -s -o data/{CODE}_quote.json 'https://push2.eastmoney.com/api/qt/stock/get?secid=MARKET.{CODE}&fields=f57,f58,f43,f169,f170,f46,f44,f60,f116,f117,f162,f167,f168,f100'
  web_extract: https://push2.eastmoney.com/api/qt/stock/get?secid=MARKET.{CODE}&fields=f127,f128,f129 → data/{CODE}_industry.json
  web_extract: https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=MARKET.{CODE}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58&klt=101&fqt=1&end=20500101&lmt=1&fmt=json → data/{CODE}_kline.json

其中 MARKET = 1(沪市) 或 0(深市)
"""

import json
import os
import time
import urllib.request
from datetime import datetime
import pandas as pd
import tushare as ts

# 数据文件目录
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')


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


# ============================================================
# JSON 文件读取
# ============================================================

def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _read_quote_json(stock_code: str) -> dict:
    path = os.path.join(DATA_DIR, f'{stock_code}_quote.json')
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _read_industry_json(stock_code: str) -> dict:
    path = os.path.join(DATA_DIR, f'{stock_code}_industry.json')
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _read_kline_json(stock_code: str) -> dict:
    path = os.path.join(DATA_DIR, f'{stock_code}_kline.json')
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _read_iwencai_quote_json(stock_code: str) -> dict:
    """读取问财行情JSON（优先于东方财富格式）"""
    path = os.path.join(DATA_DIR, f'{stock_code}_quote_iwencai.json')
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _read_iwencai_industry_json(stock_code: str) -> dict:
    """读取问财行业JSON（优先于东方财富格式）"""
    path = os.path.join(DATA_DIR, f'{stock_code}_industry_iwencai.json')
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _read_financial_json(stock_code: str, sheet_type: str) -> dict:
    """读取Hermes生成的财务三表JSON"""
    path = os.path.join(DATA_DIR, f'{stock_code}_{sheet_type}.json')
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


# ============================================================
# 腾讯行情 API 实时降级（缓存缺失时的兜底）
# ============================================================

_tencent_cache: dict = {}  # 进程级缓存，避免同一批次重复请求
_TENCENT_CACHE_TTL = 60    # 缓存60秒


def _fetch_tencent_quote(stock_code: str) -> dict:
    """腾讯行情 API — 稳定、无反爬、无频率限制

    返回 dict: name, price, pe_ttm, pb, total_mv, float_mv,
               turnover_rate, change_pct, volume, shares, ...
    """
    # 进程级短缓存
    now = time.time()
    if stock_code in _tencent_cache:
        cached = _tencent_cache[stock_code]
        if now - cached['_ts'] < _TENCENT_CACHE_TTL:
            return cached

    market = 'sh' if stock_code.startswith(('6', '9')) else 'sz'
    url = f"https://qt.gtimg.cn/q={market}{stock_code}"

    try:
        resp = urllib.request.urlopen(url, timeout=8)
        text = resp.read().decode('gbk')
        s = text.find('"')
        e = text.rfind('"')
        if s < 0 or e <= s:
            return {}
        fields = text[s+1:e].split('~')

        if len(fields) < 47:
            return {}

        price = float(fields[3]) if fields[3] else 0
        total_mv = float(fields[45]) if fields[45] else 0  # 总市值(亿)

        result = {
            'name': fields[1],
            'code': fields[2],
            'price': price,
            'pe_ttm': float(fields[39]) if len(fields) > 39 and fields[39] else 0,
            'pb': float(fields[46]) if len(fields) > 46 and fields[46] else 0,
            'total_mv': total_mv,       # 亿元
            'float_mv': float(fields[44]) if len(fields) > 44 and fields[44] else 0,
            'turnover_rate': float(fields[38]) if len(fields) > 38 and fields[38] else 0,
            'change_pct': float(fields[32]) if len(fields) > 32 and fields[32] else 0,
            'volume': int(fields[6]) if fields[6] else 0,
            'shares': total_mv / price if price > 0 else 0,  # 亿股
            '_ts': now,
        }
        _tencent_cache[stock_code] = result
        return result
    except Exception:
        return {}


# ============================================================
# Tushare 降级辅助函数
# ============================================================

def _ts_stock_code(code: str) -> str:
    """将6位股票代码转为 Tushare 格式（如 600519 → 600519.SH）"""
    if code.endswith(('.SH', '.SZ', '.BJ')):
        return code
    suffix = 'SH' if code.startswith(('6', '9')) else 'SZ'
    return f"{code}.{suffix}"


def _fetch_ts_daily(code: str) -> pd.DataFrame:
    """Tushare 历史日线兜底"""
    pro = _get_ts_pro()
    if pro is None:
        return pd.DataFrame()
    try:
        ts_code = _ts_stock_code(code)
        df = pro.daily(ts_code=ts_code, start_date='20000101', end_date='20500101')
        time.sleep(1.1)  # 限频退避，防止429
        if df is not None and len(df) > 0:
            df = df.sort_values('trade_date')
            return df
    except Exception:
        pass
    return pd.DataFrame()


def _fetch_ts_stock_basic(code: str) -> dict:
    """Tushare 股票基本信息兜底（含行业）"""
    pro = _get_ts_pro()
    if pro is None:
        return {}
    try:
        ts_code = _ts_stock_code(code)
        df = pro.stock_basic(ts_code=ts_code, fields='ts_code,name,industry,area,list_date,market')
        time.sleep(1.1)  # 限频退避，防止429
        if df is not None and len(df) > 0:
            row = df.iloc[0]
            result = {'name': row.get('name', ''), 'industry': row.get('industry', '')}
            return result
    except Exception:
        pass
    return {}


def _fetch_ts_financial_abstract(code: str) -> dict:
    """Tushare 财务指标兜底（取最近一期年报数据）
    返回: {'revenue': 元, 'net_profit': 元, 'roe': 小数, 'debt_ratio': 小数, ...}
    """
    pro = _get_ts_pro()
    if pro is None:
        return {}
    result = {}
    try:
        ts_code = _ts_stock_code(code)

        # 1. 财务指标 (ROE/毛利率/净利率)
        df_fi = pro.fina_indicator(ts_code=ts_code, fields='ts_code,end_date,roe,roa,gross_margin,netprofit_margin,eps,bps,ocfps',
                                    start_date='20100101', end_date=datetime.now().strftime('%Y1231'))
        time.sleep(1.1)  # 限频退避，防止429
        if df_fi is not None and len(df_fi) > 0:
            # 取最新年报（end_date 以 1231 结尾）
            annual = df_fi[df_fi['end_date'].astype(str).str.endswith('1231')]
            if len(annual) > 0:
                latest = annual.sort_values('end_date').iloc[-1]
            else:
                latest = df_fi.sort_values('end_date').iloc[-1]

            roe_val = float(latest.get('roe', 0) or 0) / 100.0  # Tushare ROE 是百分比值（15.2 → 0.152）
            result['roe'] = roe_val
            if 'eps' in latest:
                result['eps'] = float(latest['eps'] or 0)
            if 'bps' in latest:
                result['bps'] = float(latest['bps'] or 0)
            if 'ocfps' in latest:
                result['ocfps'] = float(latest['ocfps'] or 0)

        # 2. 利润表 (营收/净利润)
        df_inc = pro.income(ts_code=ts_code, fields='ts_code,end_date,revenue,n_income_attr_p,operate_profit',
                             start_date='20100101', end_date=datetime.now().strftime('%Y1231'))
        time.sleep(1.1)  # 限频退避，防止429
        if df_inc is not None and len(df_inc) > 0:
            annual_inc = df_inc[df_inc['end_date'].astype(str).str.endswith('1231')]
            if len(annual_inc) > 0:
                latest_inc = annual_inc.sort_values('end_date').iloc[-1]
            else:
                latest_inc = df_inc.sort_values('end_date').iloc[-1]
            result['revenue'] = float(latest_inc.get('revenue', 0) or 0)
            result['net_profit'] = float(latest_inc.get('n_income_attr_p', 0) or 0)
            result['operating_profit'] = float(latest_inc.get('operate_profit', 0) or 0)

        # 3. 资产负债表 (总资产/负债)
        df_bs = pro.balancesheet(ts_code=ts_code, fields='ts_code,end_date,total_assets,total_liab,total_hldr_eqy_exc_min_int',
                                  start_date='20100101', end_date=datetime.now().strftime('%Y1231'))
        time.sleep(1.1)  # 限频退避，防止429
        if df_bs is not None and len(df_bs) > 0:
            annual_bs = df_bs[df_bs['end_date'].astype(str).str.endswith('1231')]
            if len(annual_bs) > 0:
                latest_bs = annual_bs.sort_values('end_date').iloc[-1]
            else:
                latest_bs = df_bs.sort_values('end_date').iloc[-1]
            result['total_assets'] = float(latest_bs.get('total_assets', 0) or 0)
            result['total_liabilities'] = float(latest_bs.get('total_liab', 0) or 0)
            result['total_equity'] = float(latest_bs.get('total_hldr_eqy_exc_min_int', 0) or 0)

    except Exception:
        pass

    return result


# ============================================================
# 数据提取函数
# ============================================================

def get_stock_name(stock_code: str) -> str:
    """获取股票名称"""
    # 1. 问财行情 JSON（优先）
    iw = _read_iwencai_quote_json(stock_code)
    if iw.get('name'):
        return iw['name']
    # 2. 腾讯行情 API（稳定降级）
    tq = _fetch_tencent_quote(stock_code)
    if tq.get('name'):
        return tq['name']
    # 3. 东方财富 quote JSON
    quote = _read_quote_json(stock_code)
    data = quote.get('data', {})
    if data.get('f58'):
        return data['f58']
    # 4. 财务 JSON
    bs = _read_financial_json(stock_code, 'balance_sheet')
    if bs.get('name'):
        return bs['name']
    # 5. Tushare 兜底
    ts_info = _fetch_ts_stock_basic(stock_code)
    if ts_info.get('name'):
        return ts_info['name']
    return stock_code


def get_stock_price(stock_code: str) -> float:
    """获取最新股价（元）"""
    # 1. 问财行情 JSON（优先）
    iw = _read_iwencai_quote_json(stock_code)
    if iw.get('price'):
        return float(iw['price'])
    # 2. 腾讯行情 API（稳定降级）
    tq = _fetch_tencent_quote(stock_code)
    if tq.get('price'):
        return tq['price']
    # 3. 东方财富 quote JSON（f43 单位：分）
    quote = _read_quote_json(stock_code)
    data = quote.get('data', {})
    if 'f43' in data:
        return data['f43'] / 100.0
    # 4. kline JSON（收盘价）
    kline = _read_kline_json(stock_code)
    kdata = kline.get('data', {})
    if kdata.get('klines'):
        last = kdata['klines'][-1]
        return float(last.split(',')[2])
    # 5. Tushare 历史数据降级
    df = _fetch_ts_daily(stock_code)
    if len(df) > 0:
        return float(df.iloc[-1]['close'])
    return 0.0


def get_stock_industry_name(stock_code: str) -> str:
    """获取申万一级行业名称"""
    # 1. 问财行业 JSON（优先，直接给 sw_l1）
    iw = _read_iwencai_industry_json(stock_code)
    if iw.get('sw_l1'):
        return iw['sw_l1']
    # 2. 东方财富 industry JSON（申万二级，需映射）
    ind = _read_industry_json(stock_code)
    data = ind.get('data', {})
    level2 = data.get('f127', '')
    if level2 and level2 != '未知':
        return SW_LEVEL2_TO_LEVEL1.get(level2, level2)
    # 3. Tushare stock_basic 降级
    ts_info = _fetch_ts_stock_basic(stock_code)
    if ts_info.get('industry'):
        return ts_info['industry']
    return '未知'


def get_stock_concepts(stock_code: str) -> list:
    """获取概念板块列表"""
    # 1. 问财行业 JSON
    iw = _read_iwencai_industry_json(stock_code)
    if iw.get('ths_industry'):
        return iw['ths_industry']
    # 2. 东方财富 industry JSON
    ind = _read_industry_json(stock_code)
    data = ind.get('data', {})
    concepts = data.get('f129', '')
    return [c.strip() for c in concepts.split(',') if c.strip()] if concepts else []


def get_stock_info(stock_code: str) -> dict:
    """获取股票基本信息"""
    info = {}
    # 1. 问财行情（优先）
    iw = _read_iwencai_quote_json(stock_code)
    if iw:
        info['股票简称'] = iw.get('name', stock_code)
        info['总市值'] = f"{iw.get('total_mv', 0) / 1e8:.2f}亿"
        info['市盈率-动态'] = str(iw.get('pe_ttm', ''))
        info['市净率'] = f"{iw.get('pb', 0):.2f}"
        info['换手率'] = f"{iw.get('turnover_rate', 0):.2f}%"
        return info
    # 2. 东方财富 quote JSON（降级）
    quote = _read_quote_json(stock_code)
    data = quote.get('data', {})
    if data:
        info['股票简称'] = data.get('f58', stock_code)
        total_cap = data.get('f116', 0)
        info['总市值'] = f"{total_cap / 1e8:.2f}亿"
        info['市盈率-动态'] = str(data.get('f162', ''))
        info['市净率'] = f"{data.get('f167', 0) / 100:.2f}"
    return info


def get_shares_outstanding(stock_code: str) -> float:
    """获取总股本（亿股）"""
    # 1. 问财行情
    iw = _read_iwencai_quote_json(stock_code)
    if iw.get('total_mv') and iw.get('price'):
        return iw['total_mv'] / iw['price'] / 1e8
    # 2. 腾讯行情 API（市值/股价推算）
    tq = _fetch_tencent_quote(stock_code)
    if tq.get('shares'):
        return tq['shares']
    # 3. 东方财富 quote JSON
    quote = _read_quote_json(stock_code)
    data = quote.get('data', {})
    price = data.get('f43', 0) / 100.0
    total_cap = data.get('f116', 0)
    if total_cap > 0 and price > 0:
        return total_cap / price / 1e8
    return 0.0


def get_market_cap(stock_code: str) -> float:
    """总市值（亿元）"""
    # 1. 问财行情
    iw = _read_iwencai_quote_json(stock_code)
    if iw.get('total_mv'):
        return iw['total_mv'] / 1e8
    # 2. 腾讯行情 API
    tq = _fetch_tencent_quote(stock_code)
    if tq.get('total_mv'):
        return tq['total_mv']
    # 3. 东方财富
    quote = _read_quote_json(stock_code)
    return quote.get('data', {}).get('f116', 0) / 1e8


def get_pe_ratio(stock_code: str) -> float:
    """市盈率（TTM）"""
    # 1. 问财行情
    iw = _read_iwencai_quote_json(stock_code)
    if iw.get('pe_ttm'):
        return float(iw['pe_ttm'])
    # 2. 腾讯行情 API
    tq = _fetch_tencent_quote(stock_code)
    if tq.get('pe_ttm'):
        return tq['pe_ttm']
    # 3. 东方财富
    quote = _read_quote_json(stock_code)
    return quote.get('data', {}).get('f162', 0)


def get_pb_ratio(stock_code: str) -> float:
    """市净率"""
    # 1. 问财行情
    iw = _read_iwencai_quote_json(stock_code)
    if iw.get('pb'):
        return float(iw['pb'])
    # 2. 腾讯行情 API
    tq = _fetch_tencent_quote(stock_code)
    if tq.get('pb'):
        return tq['pb']
    # 3. 东方财富（f167 单位：百分之一）
    quote = _read_quote_json(stock_code)
    return quote.get('data', {}).get('f167', 0) / 100.0


# ============================================================
# 财务三表数据（从 Hermes JSON 读取）
# ============================================================

def get_financial_data_from_json(stock_code: str) -> dict:
    """从 Hermes 生成的财务 JSON 读取三表关键数据，缺失时降级到 Tushare"""
    result = {}
    bs = _read_financial_json(stock_code, 'balance_sheet')
    inc = _read_financial_json(stock_code, 'income')
    cf = _read_financial_json(stock_code, 'cashflow')

    if bs:
        result['total_assets'] = bs.get('total_assets', 0) or 0
        result['total_liabilities'] = bs.get('total_liabilities', 0) or 0
        result['total_equity'] = bs.get('equity', 0) or 0
    if inc:
        result['revenue'] = inc.get('total_revenue', 0) or 0
        result['operating_profit'] = inc.get('operating_profit', 0) or 0
        result['net_profit'] = inc.get('net_profit', 0) or 0
    if cf:
        result['operating_cf'] = cf.get('operating_cf', 0) or 0

    # 降级：JSON 缺失时从 Tushare 拉取财务摘要
    need_fallback = (not result.get('revenue') or not result.get('net_profit'))
    if need_fallback:
        ts_data = _fetch_ts_financial_abstract(stock_code)
        if ts_data:
            for key in ('revenue', 'net_profit', 'operating_profit', 'total_assets',
                        'total_liabilities', 'total_equity', 'roe', 'eps', 'bps', 'ocfps'):
                if key in ts_data and not result.get(key):
                    result[key] = ts_data[key]
            # Tushare 的 debt_ratio 需要从资产/负债计算
            if result.get('total_assets') and result.get('total_liabilities'):
                result['debt_ratio'] = result['total_liabilities'] / result['total_assets']

    # 计算衍生指标（仅当 Tushare 未提供时）
    if result.get('total_equity', 0) > 0 and result.get('net_profit', 0) > 0:
        if result.get('roe') is None or (isinstance(result.get('roe'), float) and (result['roe'] != result['roe'] or result['roe'] == 0)):
            result['roe'] = result['net_profit'] / result['total_equity']
    if result.get('revenue', 0) > 0 and result.get('net_profit', 0) > 0:
        result['net_margin'] = result['net_profit'] / result['revenue']
    if result.get('total_assets', 0) > 0:
        result['debt_ratio'] = result.get('total_liabilities', 0) / result['total_assets']

    # FCF 估算
    ocf = result.get('operating_cf', 0)
    result['fcf'] = ocf if ocf > 0 else result.get('net_profit', 0) * 0.8

    # 注入机构盈利预测增长率（替代缺失的3年历史CAGR）
    inst = _load_institutional_data(stock_code)
    if inst:
        eps_fc = inst.get('eps_forecast', [])
        if eps_fc:
            for fc in eps_fc:
                if fc.get('level') == 't+1' and fc.get('np_yoy') is not None:
                    result['net_profit_cagr_3y'] = fc['np_yoy'] / 100.0
                    break
            result['institutional'] = inst

    # 降级：机构数据缺失时从腾讯 API 获取 PE/PB 补充
    if not result.get('net_profit_cagr_3y'):
        tq = _fetch_tencent_quote(stock_code)
        if tq.get('pe_ttm') and tq.get('price') and result.get('net_profit'):
            # 用 PE 反推增长率（PEG=1 时的隐含增速）
            pass  # 后续可扩展

    return result


def _safe_float(val):
    """安全转换为 float"""
    try:
        v = float(val)
        return v if v == v else 0.0  # NaN check
    except (ValueError, TypeError):
        return 0.0


def _parse_cn_amount(val) -> float:
    """解析中文金额 '1845.27万' → 18452700, '1.57亿' → 157000000"""
    if val is None or val is False or val == '':
        return 0.0
    s = str(val).replace(',', '').strip()
    if not s or s == 'False':
        return 0.0
    try:
        if '亿' in s:
            return float(s.replace('亿', '')) * 1e8
        elif '万' in s:
            return float(s.replace('万', '')) * 1e4
        else:
            return float(s)
    except (ValueError, TypeError):
        return 0.0


def _parse_pct(val) -> float:
    """解析百分比 '19.27%' → 0.1927"""
    if val is None or val is False or val == '':
        return 0.0
    s = str(val).replace('%', '').strip()
    if not s or s == 'False':
        return 0.0
    try:
        return float(s) / 100.0
    except (ValueError, TypeError):
        return 0.0


def _load_institutional_data(stock_code: str) -> dict:
    """加载恒生聚源机构预测数据"""
    path = os.path.join(DATA_DIR, 'institutional', 'consolidated.json')
    if os.path.exists(path):
        with open(path) as f:
            all_data = json.load(f)
        return all_data.get(stock_code, {})
    return {}


# ============================================================
# 申万二级行业 → 一级行业映射（用于估值模型匹配）
# ============================================================

SW_LEVEL2_TO_LEVEL1 = {
    # ── 食品饮料 ──
    "白酒Ⅱ": "食品饮料", "白酒": "食品饮料", "啤酒": "食品饮料",
    "乳品": "食品饮料", "调味发酵品Ⅱ": "食品饮料",
    "食品加工": "食品饮料", "饮料乳品": "食品饮料",
    "休闲食品": "食品饮料", "熟食": "食品饮料",
    # ── 银行 ──
    "股份制银行Ⅱ": "银行", "国有大型银行Ⅱ": "银行",
    "城商行Ⅱ": "银行", "农商行Ⅱ": "银行",
    # ── 证券 ──
    "证券Ⅱ": "证券", "证券": "证券",
    # ── 保险 ──
    "保险Ⅱ": "保险", "保险": "保险",
    # ── 医药生物 ──
    "化学制药": "医药生物", "生物制品Ⅱ": "医药生物",
    "中药Ⅱ": "医药生物", "医疗器械Ⅱ": "医药生物",
    "医药商业Ⅱ": "医药生物", "医疗服务Ⅱ": "医药生物",
    # ── 计算机 ──
    "软件开发": "计算机", "IT服务Ⅱ": "计算机", "计算机设备": "计算机",
    # ── 电子 ──
    "半导体": "电子", "元件": "电子", "光学光电子": "电子",
    "消费电子": "电子", "电子化学品Ⅱ": "电子",
    # ── 汽车 ──
    "汽车零部件Ⅱ": "汽车", "乘用车": "汽车", "商用车": "汽车", "汽车服务": "汽车",
    # ── 房地产 ──
    "房地产开发": "房地产", "房地产服务": "房地产",
    # ── 公用事业 ──
    "电力": "公用事业", "水力发电": "公用事业",
    "火力发电": "公用事业", "燃气Ⅱ": "公用事业", "水务及水治理": "公用事业",
    # ── 电力设备 ──
    "电池": "电力设备", "光伏设备": "电力设备",
    "电网设备": "电力设备", "风电设备": "电力设备",
    # ── 有色金属 ──
    "工业金属": "有色金属", "贵金属": "有色金属",
    "小金属": "有色金属", "能源金属": "有色金属",
    # ── 煤炭 ──
    "煤炭开采": "煤炭", "焦炭Ⅱ": "煤炭",
    # ── 石油石化 ──
    "炼化及贸易": "石油石化", "油气开采Ⅱ": "石油石化", "油服工程": "石油石化",
    # ── 基础化工 ──
    "化学原料": "基础化工", "化学制品": "基础化工",
    "农化制品": "基础化工", "化学纤维": "基础化工",
    "塑料": "基础化工", "橡胶": "基础化工",
    # ── 钢铁 ──
    "普钢": "钢铁", "特钢Ⅱ": "钢铁",
    # ── 家用电器 ──
    "白色家电": "家用电器", "黑色家电": "家用电器",
    "小家电": "家用电器", "家电零部件Ⅱ": "家用电器",
    # ── 通信 ──
    "通信服务": "通信", "通信设备": "通信",
    # ── 传媒 ──
    "游戏Ⅱ": "传媒", "广告营销": "传媒", "影视院线": "传媒",
    "数字媒体": "传媒", "出版": "传媒", "电视广播Ⅱ": "传媒",
    # ── 交通运输 ──
    "航空机场": "交通运输", "航运港口": "交通运输",
    "铁路公路": "交通运输", "物流": "交通运输",
    # ── 国防军工 ──
    "航空装备Ⅱ": "国防军工", "航天装备Ⅱ": "国防军工",
    "军工电子Ⅱ": "国防军工", "地面兵装Ⅱ": "国防军工",
    # ── 农林牧渔 ──
    "养殖业": "农林牧渔", "饲料": "农林牧渔", "种植业": "农林牧渔", "渔业": "农林牧渔",
    # ── 建筑装饰 ──
    "房屋建设Ⅱ": "建筑装饰", "基础建设": "建筑装饰",
    "装修装饰Ⅱ": "建筑装饰", "专业工程": "建筑装饰",
    # ── 机械设备 ──
    "通用设备": "机械设备", "专用设备": "机械设备",
    "自动化设备": "机械设备", "工程机械": "机械设备",
    # ── 纺织服饰 ──
    "服装家纺": "纺织服饰", "纺织制造": "纺织服饰", "饰品": "纺织服饰",
    # ── 社会服务 ──
    "酒店餐饮": "社会服务", "旅游及景区": "社会服务",
    "教育": "社会服务", "体育Ⅱ": "社会服务",
    # ── 商贸零售 ──
    "一般零售": "商贸零售", "专业连锁Ⅱ": "商贸零售",
    "互联网电商": "商贸零售", "贸易Ⅱ": "商贸零售",
    # ── 轻工制造 ──
    "造纸": "轻工制造", "包装印刷": "轻工制造",
    "家居用品": "轻工制造", "文娱用品": "轻工制造",
}


def batch_fetch_ts_financial(stock_codes: list) -> dict:
    """批量获取多只股票的核心财务数据

    Args:
        stock_codes: 股票代码列表（6位数字，如 ['600519', '000858']）

    Returns:
        dict: {stock_code: {roe, eps, revenue, net_profit, total_assets, ...}}
    """
    result = {}
    for code in stock_codes:
        try:
            data = _fetch_ts_financial_abstract(code)
            if data:
                result[code] = data
            time.sleep(1.1)  # 每只股票之间限频退避
        except Exception:
            pass
    return result
