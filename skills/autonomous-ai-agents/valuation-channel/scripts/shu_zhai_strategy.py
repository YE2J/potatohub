#!/usr/bin/env python3
"""
薯仔交易系统 v1.0 — Python 版
=================================
移植自同花顺公式语言，原始逻辑：

买入 = COND1(主力持仓≥20%) + COND2(暗盘连流2日) + COND3(GS信号) + COND4(主力金叉)
卖出 = 主力拐头向下 + 暗盘资金流出 + 大单净量流出

已知局限：
- 大单净量、暗盘资金、主力持仓 需要 LV2 行情数据
- 当前版本用日线 OHLCV 实现可计算部分(GS信号+主力雷达)
- LV2 部分用模拟数据/占位，后续接入真实数据后替换

仓位规则：
- 最多持有3只股票
- 每只 ≤ 总资金 1/3
- 动态调仓：每周五收盘检查
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════
# 1.  GS 信号 — 价格中枢迭代收敛策略（纯OHLCV，无需LV2）
# ═══════════════════════════════════════════════════════════════════════

def compute_gs_signal(close: pd.Series, high: pd.Series, low: pd.Series,
                      open_: pd.Series) -> pd.Series:
    """
    GS 信号 (TCY=1) — 同花顺公式的 Python 移植。

    核心思想：通过对 (H+L+2O+6C)/10 加权价格 和
    (MA3+MA7+MA13+MA27)/4 均价中枢反复迭代收敛，
    在每次交叉时微调 (±2%)，最终判断价格处于中枢上方还是下方。

    Returns
    -------
    pd.Series: 1=买入信号, 0=无信号
    """
    # BB: 多均线中枢
    bb = (close.rolling(3).mean() +
          close.rolling(7).mean() +
          close.rolling(13).mean() +
          close.rolling(27).mean()) / 4
    bb = bb.fillna(close.ewm(span=5).mean())

    # A0: 加权价格
    a0 = (high + low + 2 * open_ + 6 * close) / 10

    # TK: 偏空条件 (close < open 或 冲高回落)
    tk_cond1 = close < open_
    tk_cond2 = (close < high.shift(1)) & (close >= open_)
    tk_cond3 = (close >= open_) & ((high - close) >= (close - open_)) & (close / close.shift(1) < 1.02)
    tk_cond4 = (close == open_) & ((high - close) >= (close - low)) & (close / close.shift(1) < 1.05)
    tk = tk_cond1 | tk_cond2 | tk_cond3 | tk_cond4

    # TP: 偏多条件
    tp_cond1 = (close > open_) & (close / close.shift(1) > 0.94)
    tp_cond2 = (close > low.shift(1)) & (close < open_)
    tp_cond3 = (close <= open_) & ((close - low) >= (open_ - close)) & (close / close.shift(1) > 0.98)
    tp_cond4 = (close == open_) & ((close - low) >= (high - close)) & (close / close.shift(1) > 0.95)
    tp = tp_cond1 | tp_cond2 | tp_cond3 | tp_cond4

    # 迭代收敛 (最多9次)
    a = a0.copy()
    for _ in range(9):
        c1 = (a > bb) & tk
        c2 = (bb > a) & tp
        a = np.where(c1, bb * 0.98, np.where(c2, bb * 1.02, a))

    # K = 价格中枢之上, P = 中枢之下
    k = a >= bb
    p = a < bb

    # 涨幅
    zf = close.pct_change(fill_method=None) * 100

    # 价格偏离 %
    zj = (a / bb - 1) * 100

    # TCY = K + 特定条件
    tcy = k & (
        ((close >= high.shift(1)) & ((high - close) < (close - open_))) |
        (zf >= 7) |
        ((close < high.shift(1)) & (close < open_) & (zf > -3) & (zj >= 10))
    )

    return tcy.astype(int)


# ═══════════════════════════════════════════════════════════════════════
# 2.  主力雷达 — MA乖离率（纯OHLCV，无需LV2）
# ═══════════════════════════════════════════════════════════════════════

def compute_main_force_radar(close: pd.Series) -> pd.DataFrame:
    """
    主力线 = EMA((close - MA7)/MA7 × 480, 2) × 5
    散户线 = EMA((close - MA11)/MA11 × 480, 7) × 5

    Returns
    -------
    DataFrame with columns: main_line, retail_line, cross_zero, retail_falling
    """
    ma7 = close.rolling(7).mean()
    ma11 = close.rolling(11).mean()

    raw_main = (close - ma7) / ma7 * 480
    raw_retail = (close - ma11) / ma11 * 480

    main_line = raw_main.ewm(span=2, adjust=False).mean() * 5
    retail_line = raw_retail.ewm(span=7, adjust=False).mean() * 5

    # 主力上穿零轴
    cross_zero = (main_line.shift(1) <= 0) & (main_line > 0)

    # 散户线下降
    retail_falling = retail_line < retail_line.shift(1)

    return pd.DataFrame({
        'main_line': main_line,
        'retail_line': retail_line,
        'cross_zero': cross_zero,
        'retail_falling': retail_falling,
    })


# ═══════════════════════════════════════════════════════════════════════
# 3.  大单净量 / 暗盘资金 / 主力持仓（需要 LV2 数据）
# ═══════════════════════════════════════════════════════════════════════

class Lv2DataProvider:
    """
    LV2 数据接口 — 抽象层。

    当前版本：用日线数据做近似模拟。
    接入真实 LV2 数据后，替换此类的实现即可。
    """

    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock

    def get_large_order_net(self, close: pd.Series,
                            volume: pd.Series) -> pd.Series:
        """
        大单净量 (ZDMR+BDMR-ZDMC-BDMC)/流通股本×100

        模拟版本：用量价关系估算大单活动。
        真实版本：从 LV2 逐笔成交数据计算。
        """
        if not self.use_mock:
            # TODO: 接入真实 LV2 接口
            return pd.Series(0, index=close.index)

        # 模拟：价格大幅变动+放量 = 大单活动
        price_change = close.pct_change().abs()
        vol_ratio = volume / volume.rolling(20).mean()
        direction = np.sign(close.diff())

        mock_net = direction * price_change * vol_ratio * 5
        mock_net = mock_net.clip(-3, 3)
        return mock_net.fillna(0)

    def get_dark_pool_flow(self, close: pd.Series, open_: pd.Series,
                           high: pd.Series, low: pd.Series,
                           volume: pd.Series) -> pd.Series:
        """
        暗盘资金 — 用盘中波动幅度估算"隐藏资金"。

        模拟版本：调整幅度公式近似。
        """
        if not self.use_mock:
            return pd.Series(0, index=close.index)

        prev_close = close.shift(1)
        open_pct = (open_ - prev_close) / prev_close
        body_pct = (close - open_) / open_
        high_pct = (high - open_) / open_
        low_pct = (low - open_) / open_
        close_high_pct = (close - high) / high
        close_low_pct = (close - low) / low

        adjust = open_pct + body_pct + high_pct + close_high_pct + low_pct + close_low_pct
        adjust = adjust.clip(-2, 2)

        money = close * volume
        dark_flow = np.where(adjust > 0,
                            money * adjust * 0.1,
                            money * adjust * 0.05)
        return pd.Series(dark_flow, index=close.index).fillna(0)

    def get_main_force_position(self, close: pd.Series,
                                 volume: pd.Series) -> pd.Series:
        """
        主力持仓比例 (%)。

        模拟版本：基于价格趋势的相对估计。
        真实版本：从 LV_D_SUPER_HLD_RATIO 获取。
        """
        if not self.use_mock:
            return pd.Series(50, index=close.index)

        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()

        # 趋势强度
        trend = (close - ma60) / ma60 * 100

        # 均量线
        vol_ma = volume.rolling(20).mean()
        vol_ratio = volume / vol_ma

        # 主力持仓 ≈ 趋势 + 量能修正
        position = 50 + trend * 2 + (vol_ratio - 1) * 10
        position = position.clip(2, 97)
        return position.fillna(50)


# ═══════════════════════════════════════════════════════════════════════
# 4.  薯仔策略主引擎
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class TradeSignal:
    """交易信号"""
    action: str          # 'buy', 'sell', 'hold'
    strength: float      # 0.0 ~ 1.0
    reason: str          # 触发原因
    price: float         # 信号价格
    date: pd.Timestamp   # 信号日期


@dataclass
class Position:
    """持仓信息"""
    code: str
    name: str = ''
    shares: int = 0
    avg_cost: float = 0.0
    current_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    @property
    def profit_pct(self) -> float:
        if self.avg_cost == 0:
            return 0.0
        return (self.current_price / self.avg_cost - 1) * 100


class ShuZhaiStrategy:
    """
    薯仔交易系统 — Python 实现

    参数
    ----
    max_positions : int
        最大持仓数 (默认 3)
    max_position_pct : float
        单只最大仓位比例 (默认 1/3)
    lv2_provider : Lv2DataProvider
        LV2 数据提供者
    """

    def __init__(self,
                 max_positions: int = 3,
                 max_position_pct: float = 1/3,
                 lv2_provider: Optional[Lv2DataProvider] = None):
        self.max_positions = max_positions
        self.max_position_pct = max_position_pct
        self.lv2_provider = lv2_provider or Lv2DataProvider(use_mock=True)
        self.positions: Dict[str, Position] = {}
        self.total_capital: float = 1_000_000  # 初始资金
        self.cash: float = 1_000_000
        self.signals: List[TradeSignal] = []
        self.trade_log: List[dict] = []

    # ── 核心信号计算 ────────────────────────────────────────────────

    def generate_signals(self, code: str,
                         df: pd.DataFrame) -> pd.DataFrame:
        """
        对单只股票生成完整的买入/卖出信号序列。

        Parameters
        ----------
        code : str
            股票代码
        df : pd.DataFrame
            必含列: open, high, low, close, volume
            索引: DatetimeIndex

        Returns
        -------
        pd.DataFrame with columns:
            gs_signal, main_line, cross_zero,
            dark_pool_flow, large_order_net,
            main_position, buy_signal, sell_signal
        """
        close = df['close']
        high = df['high']
        low = df['low']
        open_ = df['open']
        volume = df['volume']

        # GS 信号 (无需 LV2)
        gs = compute_gs_signal(close, high, low, open_)

        # 主力雷达 (无需 LV2)
        radar = compute_main_force_radar(close)

        # LV2 数据
        large_order_net = self.lv2_provider.get_large_order_net(close, volume)
        dark_pool = self.lv2_provider.get_dark_pool_flow(close, open_, high, low, volume)
        main_pos = self.lv2_provider.get_main_force_position(close, volume)

        # ── COND1: 主力持仓 ≥ 20 ──
        cond1 = main_pos >= 20

        # ── COND2: 暗盘资金连续两日流入 ──
        dark_positive = dark_pool > 0
        cond2 = dark_positive & dark_positive.shift(1)

        # ── COND3: GS 信号 ──
        cond3 = gs == 1

        # ── COND4: 主力上穿零轴 + 散户下降 ──
        cond4 = radar['cross_zero'] & radar['retail_falling']

        # ── 买入信号: COND1 + COND2 + COND3 + COND4 + 当日暗盘流入 ──
        dark_inflow_today = dark_pool > 0
        buy_signal = cond1 & cond2 & cond3 & cond4 & dark_inflow_today

        # ── 卖出信号 ──
        # 主力拐头向下
        main_turning_down = (radar['main_line'] < radar['main_line'].shift(1)) & \
                            (radar['main_line'].shift(1) > radar['main_line'].shift(2))
        # 暗盘流出
        dark_outflow = dark_pool < 0
        # 大单净量流出 (绿色)
        large_net_out = large_order_net < 0

        sell_signal = main_turning_down & dark_outflow & large_net_out

        result = pd.DataFrame({
            'gs_signal': gs,
            'main_line': radar['main_line'],
            'retail_line': radar['retail_line'],
            'cross_zero': radar['cross_zero'],
            'dark_pool_flow': dark_pool,
            'large_order_net': large_order_net,
            'main_position': main_pos,
            'cond1': cond1,
            'cond2': cond2,
            'cond3': cond3,
            'cond4': cond4,
            'buy_signal': buy_signal,
            'sell_signal': sell_signal,
            'main_turning_down': main_turning_down,
            'dark_outflow': dark_outflow,
            'large_net_out': large_net_out,
        }, index=df.index)

        return result

    # ── 仓位管理 ────────────────────────────────────────────────────

    def calculate_position_size(self, code: str,
                                signal_strength: float = 1.0) -> Tuple[int, float]:
        """
        计算买入股数和金额。

        规则：
        - 当前持仓数 < max_positions 才能买入
        - 新仓位 = min(可用现金 / 剩余仓位数, 总资金 × max_position_pct)
        - signal_strength 调节仓位比例

        Returns
        -------
        (shares, amount) 股数和金额
        """
        current_count = len(self.positions)
        if current_count >= self.max_positions:
            return 0, 0.0

        slots_left = self.max_positions - current_count
        max_per_slot = self.total_capital * self.max_position_pct
        per_slot_cash = self.cash / slots_left

        position_amount = min(per_slot_cash, max_per_slot) * signal_strength
        return 0, position_amount  # 股数需在调用时根据价格计算

    def can_open_new_position(self) -> bool:
        """检查是否能开新仓"""
        return len(self.positions) < self.max_positions

    def get_total_exposure(self) -> float:
        """当前总仓位比例"""
        invested = sum(p.market_value for p in self.positions.values())
        return invested / self.total_capital if self.total_capital > 0 else 0

    # ── 交易执行 ────────────────────────────────────────────────────

    def execute_buy(self, code: str, price: float, date: pd.Timestamp,
                    reason: str, strength: float = 1.0) -> Optional[TradeSignal]:
        """执行买入"""
        if not self.can_open_new_position():
            return None

        _, amount = self.calculate_position_size(code, strength)
        if amount <= 0:
            return None

        shares = int(amount / price / 100) * 100  # 按手(100股)取整
        if shares <= 0:
            return None

        actual_cost = shares * price
        self.cash -= actual_cost

        pos = Position(
            code=code,
            shares=shares,
            avg_cost=price,
            current_price=price,
        )
        self.positions[code] = pos

        signal = TradeSignal(
            action='buy', strength=strength,
            reason=reason, price=price, date=date
        )
        self.signals.append(signal)
        self.trade_log.append({
            'date': date, 'code': code, 'action': 'buy',
            'price': price, 'shares': shares, 'amount': actual_cost,
            'reason': reason,
        })
        return signal

    def execute_sell(self, code: str, price: float, date: pd.Timestamp,
                     reason: str) -> Optional[TradeSignal]:
        """执行卖出（全部清仓）"""
        if code not in self.positions:
            return None

        pos = self.positions[code]
        proceeds = pos.shares * price
        self.cash += proceeds

        signal = TradeSignal(
            action='sell', strength=1.0,
            reason=reason, price=price, date=date
        )
        self.signals.append(signal)
        self.trade_log.append({
            'date': date, 'code': code, 'action': 'sell',
            'price': price, 'shares': pos.shares,
            'amount': proceeds, 'reason': reason,
            'profit': (price - pos.avg_cost) * pos.shares,
        })
        del self.positions[code]
        return signal

    def update_positions(self, price_map: Dict[str, float]):
        """更新所有持仓的当前价"""
        for code, price in price_map.items():
            if code in self.positions:
                self.positions[code].current_price = price

    # ── 批量扫描 ────────────────────────────────────────────────────

    def scan(self, data_map: Dict[str, pd.DataFrame],
             verbose: bool = True) -> pd.DataFrame:
        """
        扫描多只股票，找出触发买入条件的。

        Returns
        -------
        DataFrame sorted by signal_strength descending
        """
        results = []
        for code, df in data_map.items():
            sig_df = self.generate_signals(code, df)
            latest = sig_df.iloc[-1]

            if latest['buy_signal']:
                strength = 1.0
                reasons = []
                if latest['cond1']: reasons.append('主力持仓达标')
                if latest['cond2']: reasons.append('暗盘连流')
                if latest['cond3']: reasons.append('GS信号')
                if latest['cond4']: reasons.append('主力金叉')
                results.append({
                    'code': code,
                    'price': float(df['close'].iloc[-1]),
                    'main_position': round(float(latest['main_position']), 1),
                    'gs': int(latest['gs_signal']),
                    'cross_zero': bool(latest['cross_zero']),
                    'strength': strength,
                    'reasons': '+'.join(reasons),
                })

        if results:
            result_df = pd.DataFrame(results)
            result_df.sort_values('strength', ascending=False, inplace=True)
            return result_df
        return pd.DataFrame()

    # ── 周度调仓 ────────────────────────────────────────────────────

    def weekly_rebalance(self, data_map: Dict[str, pd.DataFrame],
                         current_date: pd.Timestamp) -> List[TradeSignal]:
        """
        每周五收盘后执行调仓。

        1. 检查持仓中卖出信号
        2. 扫描全市场买入信号
        3. 按优先级调仓

        Returns
        -------
        List of executed TradeSignal
        """
        trades = []

        # Step 1: 检查持仓卖出信号
        for code in list(self.positions.keys()):
            if code not in data_map:
                continue
            sig_df = self.generate_signals(code, data_map[code])
            latest = sig_df.iloc[-1]

            if latest['sell_signal']:
                price = float(data_map[code]['close'].iloc[-1])
                reason = f"卖出信号: 主力拐头+暗盘流出+大单净量流出"
                sig = self.execute_sell(code, price, current_date, reason)
                if sig:
                    trades.append(sig)

        # Step 2: 扫描买入信号
        scan_result = self.scan(data_map, verbose=False)
        if not scan_result.empty:
            for _, row in scan_result.iterrows():
                if not self.can_open_new_position():
                    break
                code = row['code']
                price = float(data_map[code]['close'].iloc[-1])
                sig = self.execute_buy(code, price, current_date,
                                       str(row['reasons']))
                if sig:
                    trades.append(sig)

        # Step 3: 更新持仓价格
        price_map = {}
        for code in list(self.positions.keys()):
            if code in data_map:
                price_map[code] = float(data_map[code]['close'].iloc[-1])
        self.update_positions(price_map)

        return trades

    # ── 报告输出 ────────────────────────────────────────────────────

    def print_status(self):
        """打印当前持仓和资金状态"""
        sep = '━' * 50
        lines = [f'\n{sep}']
        lines.append(f'📊 薯仔交易系统 — 状态报告')
        lines.append(f'📅 {pd.Timestamp.now().strftime("%Y-%m-%d")}')
        lines.append(sep)
        lines.append(f'\n💰 总资金: {self.total_capital:,.0f}')
        lines.append(f'💵 可用现金: {self.cash:,.0f}')
        lines.append(f'📈 总仓位: {self.get_total_exposure()*100:.1f}%')
        lines.append(f'📊 持仓数: {len(self.positions)}/{self.max_positions}')

        if self.positions:
            lines.append(f'\n📋 持仓明细:')
            for code, pos in self.positions.items():
                lines.append(
                    f'  {code} {pos.name[:8] if pos.name else "":8s} '
                    f'{pos.shares:>6d}股 @ {pos.avg_cost:.2f} '
                    f'→ {pos.current_price:.2f} '
                    f'({pos.profit_pct:+.1f}%) '
                    f'市值{pos.market_value:,.0f}'
                )

        if self.trade_log:
            last5 = self.trade_log[-5:]
            lines.append(f'\n📝 最近5笔交易:')
            for t in reversed(last5):
                emoji = '🟢' if t['action'] == 'buy' else '🔴'
                lines.append(f'  {emoji} {t["date"][:10]} {t["code"]} '
                           f'{t["action"]} @ {t["price"]:.2f}')

        lines.append(sep)
        print('\n'.join(lines))


# ═══════════════════════════════════════════════════════════════════════
# 5.  CLI 入口（独立运行 + 回测）
# ═══════════════════════════════════════════════════════════════════════

def run_backtest(codes: List[str],
                 start_date: str = '2024-01-01',
                 end_date: Optional[str] = None,
                 initial_capital: float = 1_000_000):
    """
    简易回测 — 用腾讯数据 + 薯仔策略

    注意：由于缺少 LV2 数据，回测使用模拟 LV2 数据，
    结果仅供参考，不代表真实性能。
    """
    from valuation_channel import DataFetcher

    if end_date is None:
        from datetime import datetime
        end_date = datetime.now().strftime('%Y-%m-%d')

    fetcher = DataFetcher()
    strategy = ShuZhaiStrategy()
    strategy.total_capital = initial_capital
    strategy.cash = initial_capital

    data_map = {}
    for code in codes:
        try:
            df = fetcher.get_kline(code, start_date, end_date)
            data_map[code] = df
            print(f'✓ {code}: {len(df)} 交易日')
        except Exception as e:
            print(f'✗ {code}: {e}')

    if not data_map:
        print('没有数据，退出')
        return

    # 逐日回测
    all_dates = pd.DatetimeIndex([])
    for df in data_map.values():
        all_dates = all_dates.union(df.index if hasattr(df, 'index') else df['date'])
    all_dates = pd.Series(all_dates.sort_values().unique())

    for i, dt in enumerate(all_dates):
        # 取每天的数据
        day_data = {}
        for code, df in data_map.items():
            mask = df['date'] == dt
            if mask.any():
                day_data[code] = df[mask].copy()

        # 周五或月末调仓
        if dt.weekday() == 4 or i == len(all_dates) - 1:
            if day_data:
                strategy.weekly_rebalance(day_data, dt)

        # 更新价格
        price_map = {}
        for code in list(strategy.positions.keys()):
            if code in day_data and not day_data[code].empty:
                price_map[code] = float(day_data[code]['close'].iloc[-1])
        strategy.update_positions(price_map)

    strategy.print_status()

    # 打印交易记录
    if strategy.trade_log:
        print(f'\n📋 交易记录 ({len(strategy.trade_log)} 笔):')
        df_log = pd.DataFrame(strategy.trade_log)
        print(df_log.to_string(index=False))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='薯仔交易系统 — Python版')
    parser.add_argument('codes', nargs='+', help='股票代码, 如 000001 600519')
    parser.add_argument('--start', default='2024-01-01', help='开始日期')
    parser.add_argument('--end', default=None, help='结束日期')
    parser.add_argument('--capital', type=float, default=1_000_000, help='初始资金')
    args = parser.parse_args()

    run_backtest(args.codes, args.start, args.end, args.capital)
