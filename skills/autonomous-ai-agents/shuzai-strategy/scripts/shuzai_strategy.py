#!/usr/bin/env python3
"""
薯仔交易系统 v2 — Python 移植版
==================================
基于同花顺公式语言原版改写，保持原逻辑结构。

数据源（当前可用）：
  - 日K线: 腾讯财经 qt.gtimg.cn / web.ifzq.gtimg.cn ✅
  - 财务数据: akshare 同花顺 ✅
  - 流通股本: 腾讯实时行情 ✅

LV2 依赖标记：
  🟡 = 可用近似替代
  🔴 = 需要真实LV2数据（占位符）

待优化项（标记 TODO）：
  - 持股时间管理
  - 仓位管理
  - 止损止盈
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta


# ═══════════════════════════════════════════════════════════════════════
# 数据获取层
# ═══════════════════════════════════════════════════════════════════════

import sys, os
sys.path.insert(0, os.path.expanduser(
    '~/.hermes/skills/autonomous-ai-agents/valuation-channel/scripts'))
from valuation_channel import DataFetcher  # 复用已有的数据获取器


# ═══════════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ShuzaiConfig:
    """薯仔交易系统参数配置"""
    # 主力持仓阈值
    hld_threshold: float = 20.0       # COND1: 主力持仓 >= 20%
    
    # 暗盘资金
    dark_money_lookback: int = 2      # COND2: 连续流入天数
    
    # GS信号参数
    bb_window: int = 5                # GS信号交叉检测周期
    
    # 主力雷达参数
    radar_fast: int = 7               # 主力线均线周期
    radar_slow: int = 11              # 散户线均线周期
    
    # LV2 近似参数
    large_trade_threshold: float = 0.001  # 大单界定：成交额的千分之一
    large_trade_ratio: float = 0.15      # 大单占总成交比例估计


# ═══════════════════════════════════════════════════════════════════════
# 核心计算模块
# ═══════════════════════════════════════════════════════════════════════

class ShuzaiStrategy:
    """
    薯仔交易系统核心策略引擎
    
    输入: K线DataFrame (含 date, open, close, high, low, volume)
    输出: 信号DataFrame (含买卖信号列)
    """
    
    def __init__(self, config: Optional[ShuzaiConfig] = None):
        self.config = config or ShuzaiConfig()
        self._signals: Optional[pd.DataFrame] = None
    
    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        主入口：对输入的K线数据执行全部指标计算
        
        Parameters
        ----------
        df : pd.DataFrame
            必须包含列: date, open, close, high, low, volume
            建议至少 60 根K线
        
        Returns
        -------
        pd.DataFrame : 原DataFrame + 所有指标列 + 买卖信号
        """
        df = df.copy().sort_values('date').reset_index(drop=True)
        
        # ── 1. 大单净量（明盘大单资金）🟡 ──────────────────────────
        # 原公式: (ZDMR+BDMR-ZDMC-BDMC)/流通股本*100
        # 近似: 用成交额 × 估算大单比例模拟
        df = self._compute_dadan_net(df)
        
        # ── 2. 暗盘资金 🟡 ──────────────────────────────────────────
        # 原公式: 用撮合数据反推隐藏资金
        # 近似: 利用价格行为 + 成交额变化估算主力方向
        df = self._compute_dark_money(df)
        
        # ── 3. 主力持仓 🔴 + 🟡 ────────────────────────────────────
        # 原公式: HLD_BASE + DDX 修正
        # DDX部分可用成交数据近似，HLD需要真实LV2
        df = self._compute_holder_position(df)
        
        # ── 4. GS信号 (TCY) ✅ 完整实现 ────────────────────────────
        # 仅需K线数据，可完整计算
        df = self._compute_gs_signal(df)
        
        # ── 5. 主力雷达 ✅ 完整实现 ─────────────────────────────────
        # 仅需K线数据
        df = self._compute_radar(df)
        
        # ── 6. 生成买卖信号 ─────────────────────────────────────────
        df = self._generate_signals(df)
        
        self._signals = df
        return df
    
    # ═══════════════════════════════════════════════════════════════════
    # 1. 大单净量计算 🟡
    # ═══════════════════════════════════════════════════════════════════
    
    def _compute_dadan_net(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        原同花顺公式:
            ZDMR_/BDMR_/ZDMC_/BDMC_ = LV2逐单数据
            大单净量 = ((ZDMR_+BDMR_)-(ZDMC_+BDMC_))/流通股本*100
        
        近似方案:
            1. 计算每日成交额
            2. 估算大单成交占比（默认15%主力交易）
            3. 用涨跌方向 + 成交量变化推断净方向
        """
        close = df['close'].values
        volume = df['volume'].values
        amount = close * volume  # 成交额
        
        # 估算流通股本（取前5日均量放大作为近似）
        float_shares = np.median(volume[:min(20, len(volume))]) * 100
        if float_shares > 0:
            df['流通股本_估'] = float_shares
        else:
            df['流通股本_估'] = volume.max()
        
        # 估算大单买入/卖出方向
        # 逻辑: 阳线且量放大 → 大单买入偏多
        #       阴线且量放大 → 大单卖出偏多
        price_change = np.diff(close, prepend=close[0])
        vol_ratio = volume / np.roll(volume, 1)
        vol_ratio[0] = 1.0
        
        # 方向因子: +1(买入偏多) ~ -1(卖出偏多)
        direction = np.where(
            price_change > 0,
            np.minimum(vol_ratio, 2.0) * 0.5,   # 上涨放量 → 买入
            -np.minimum(vol_ratio, 2.0) * 0.5    # 下跌放量 → 卖出
        )
        
        # 大单净量 ≈ 方向 × 流通股本占比
        net_amount = amount * direction * self.config.large_trade_ratio
        net_ratio = net_amount / df['流通股本_估'].values * 100
        
        df['大单净量'] = np.round(net_ratio, 4)
        df['明盘流入'] = df['大单净量'] > 0
        df['明盘流出'] = df['大单净量'] < 0
        
        return df
    
    # ═══════════════════════════════════════════════════════════════════
    # 2. 暗盘资金计算 🟡
    # ═══════════════════════════════════════════════════════════════════
    
    def _compute_dark_money(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        原同花顺公式:
            调整幅度 = 高低开1+实体涨跌+冲高1+回落1+杀跌1+V反1
            暗盘资金 = (中买初+小买初)×调整幅度 (调整>0时)
                    或 (中卖初+小卖初)×调整幅度 (调整<0时)
        
        近似: 用价格行为的综合强度模拟"调整幅度"
        """
        o = df['open'].values
        c = df['close'].values
        h = df['high'].values
        l = df['low'].values
        prev_c = np.roll(c, 1)
        prev_c[0] = o[0]
        
        # 原公式各分量
        gap = (o - prev_c) / prev_c          # 高低开
        body = (c - o) / o                    # 实体涨跌
        upside = (h - o) / o                  # 冲高
        downside = (c - h) / h               # 回落
        kill_down = (l - o) / o              # 杀跌
        v_reversal = (c - l) / l             # V反
        
        adjust = gap + body + upside + downside + kill_down + v_reversal
        adjust = np.where(adjust >= 1, 0.8, adjust)  # 原公式截断
        
        # 估算中单+小单资金（总成交额 - 估算大单）
        amount = c * df['volume'].values
        mid_small_amount = amount * (1 - self.config.large_trade_ratio)
        
        # 暗盘资金 = 调整幅度 × 中/小单资金
        dark = np.where(
            adjust > 0,
            mid_small_amount * adjust,        # 看多暗盘
            mid_small_amount * adjust         # 看空暗盘（adjust为负）
        )
        
        df['暗盘资金'] = np.round(dark, 2)
        df['暗盘流入'] = df['暗盘资金'] > 0
        
        return df
    
    # ═══════════════════════════════════════════════════════════════════
    # 3. 主力持仓计算 🔴 + 🟡
    # ═══════════════════════════════════════════════════════════════════
    
    def _compute_holder_position(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        原公式复杂: DDX + LV_D_SUPER_HLD_RATIO 多层修正
        
        当前实现:
            DDX部分用大单净量近似 ✅
            HLD部分因需要真实LV2，用默认值 🔴
        
        NOTE: 接入真实LV2后替换此函数
        """
        # DDX ≈ 大单净量的移动累积
        df['DDX_估'] = df['大单净量'].rolling(5).mean().fillna(0)
        
        # HLD_BASE: 需要LV_D_SUPER_HLD_RATIO 🔴
        # 使用流通股本累计净买入的百分比估算
        cum_net = df['大单净量'].cumsum()
        hld_base = np.clip(cum_net * 0.5 + 30, 5, 95)  # 粗略估算
        
        ddx = df['DDX_估'].values
        hld = hld_base.values
        
        # 原逻辑: 根据DDX正负和HLD位置决定修正系数
        hld_corrected = np.copy(hld)
        for i in range(len(hld)):
            if ddx[i] > 0:
                if hld[i] > 95:
                    hld_corrected[i] = hld[i] + ddx[i] * 0.1
                elif hld[i] > 90:
                    hld_corrected[i] = hld[i] + ddx[i] * 0.5
                elif hld[i] > 85:
                    hld_corrected[i] = hld[i] + ddx[i] * 0.8
                else:
                    hld_corrected[i] = hld[i] + ddx[i]
            else:
                if hld[i] < 5:
                    hld_corrected[i] = hld[i] + ddx[i] * 0.1
                elif hld[i] < 10:
                    hld_corrected[i] = hld[i] + ddx[i] * 0.5
                elif hld[i] < 15:
                    hld_corrected[i] = hld[i] + ddx[i] * 0.8
                else:
                    hld_corrected[i] = hld[i] + ddx[i]
        
        # 截断到 [2.08, 97.18]
        df['主力持仓'] = np.clip(np.round(hld_corrected, 2), 2.08, 97.18)
        df['COND1_主力持仓'] = df['主力持仓'] >= self.config.hld_threshold
        
        # 暗盘资金连续流入检测
        df['暗盘连流'] = (
            (df['暗盘资金'] > 0) & 
            (df['暗盘资金'].shift(1) > 0)
        )
        df['COND2_暗盘连流'] = df['暗盘连流']
        
        return df
    
    # ═══════════════════════════════════════════════════════════════════
    # 4. GS信号 (TCY=1) ✅ 完整实现
    # ═══════════════════════════════════════════════════════════════════
    
    def _compute_gs_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        GS信号（同花顺TCY指标）
        通过多轮迭代收敛计算价格中枢，判断趋势方向
        
        原逻辑:
            BB = MA3/7/13/27均值
            A0 = (H+L+2×O+6×C)/10
            TK/TP = 价格形态判断
            A = 多轮CROSS(A, BB)迭代 → 收敛到中枢
            K/P = A与BB的关系
            TCY = K + 形态条件
        """
        c = df['close'].values
        h = df['high'].values
        l = df['low'].values
        o = df['open'].values
        n = len(c)
        
        # BB: 多周期均线中枢
        if n >= 27:
            ma3 = pd.Series(c).rolling(3).mean().values
            ma7 = pd.Series(c).rolling(7).mean().values
            ma13 = pd.Series(c).rolling(13).mean().values
            ma27 = pd.Series(c).rolling(27).mean().values
            bb = (ma3 + ma7 + ma13 + ma27) / 4
            bb = np.where(np.isnan(bb), pd.Series(c).ewm(span=5).mean().values, bb)
        else:
            bb = pd.Series(c).ewm(span=5).mean().values
        
        # A0: 加权价格
        a0 = (h + l + 2 * o + 6 * c) / 10
        
        # TK条件: 阴线或冲高回落形态
        tk = (
            (c < o) |                                         # 阴线
            ((c < np.roll(h, 1)) & (c > o)) |                 # 阳线但未创新高
            ((c >= o) & ((h - c) >= (c - o)) &                 # 上影线长
             (np.divide(c, np.roll(c, 1), out=np.ones_like(c), where=np.roll(c, 1)!=0) < 1.02)) |
            ((c == o) & ((h - c) >= (c - l)) &                # 十字星阴
             (np.divide(c, np.roll(c, 1), out=np.ones_like(c), where=np.roll(c, 1)!=0) < 1.05))
        )
        
        # TP条件: 阳线或探底回升形态
        tp = (
            ((c > o) & (np.divide(c, np.roll(c, 1), out=np.ones_like(c), where=np.roll(c, 1)!=0) > 0.94)) |
            ((c > np.roll(l, 1)) & (c < o)) |
            ((c <= o) & ((c - l) >= (o - c)) &
             (np.divide(c, np.roll(c, 1), out=np.ones_like(c), where=np.roll(c, 1)!=0) > 0.98)) |
            ((c == o) & ((c - l) >= (h - c)) &
             (np.divide(c, np.roll(c, 1), out=np.ones_like(c), where=np.roll(c, 1)!=0) > 0.95))
        )
        
        # 多轮CROSS(A, BB)迭代 → 收敛到中枢 A
        # 原公式做了9轮迭代，这里简化但保持核心逻辑
        a = np.copy(a0)
        for _ in range(9):
            cross_up = (a > bb) & (np.roll(a, 1) <= np.roll(bb, 1))
            cross_dn = (a < bb) & (np.roll(a, 1) >= np.roll(bb, 1))
            a = np.where(cross_up & tk, bb * 0.98,
                        np.where(cross_dn & tp, bb * 1.02, a))
        
        # 趋势方向
        k = a >= bb  # 价格在中枢上方
        p = a < bb   # 价格在中枢下方
        
        # ZF: 涨跌幅，ZJ: 中枢偏离度
        prev_c = np.roll(c, 1)
        zf = np.where(prev_c != 0, (c / prev_c - 1) * 100, 0)
        zj = np.where(bb != 0, (a / bb - 1) * 100, 0)
        
        # TCY = K + 价格强势条件
        prev_h = np.roll(h, 1)
        tcy = (
            k &
            (
                ((c >= prev_h) & ((h - c) < (c - o)) | (zf >= 7)) |
                ((c < prev_h) & (c < o) & (zf > -3) & (zj >= 10))
            )
        )
        
        df['GS_BB'] = np.round(bb, 4)
        df['GS_A'] = np.round(a, 4)
        df['GS_K'] = k
        df['GS_P'] = p
        df['GS_ZF'] = np.round(zf, 2)
        df['GS_ZJ'] = np.round(zj, 2)
        df['COND3_TCY'] = tcy
        
        return df
    
    # ═══════════════════════════════════════════════════════════════════
    # 5. 主力雷达 ✅ 完整实现
    # ═══════════════════════════════════════════════════════════════════
    
    def _compute_radar(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        原公式:
            主力线 = EMA((CLOSE-MA7)/MA7×480, 2)×5
            散户线 = EMA((CLOSE-MA11)/MA11×480, 7)×5
        """
        c = df['close'].values
        
        ma7 = pd.Series(c).rolling(7).mean().values
        ma11 = pd.Series(c).rolling(11).mean().values
        
        # 主力线: 快速EMA
        raw1 = np.where(ma7 != 0, (c - ma7) / ma7 * 480, 0)
        main_line = pd.Series(raw1).ewm(span=2, adjust=False).mean().values * 5
        
        # 散户线: 慢速EMA
        raw2 = np.where(ma11 != 0, (c - ma11) / ma11 * 480, 0)
        retail_line = pd.Series(raw2).ewm(span=7, adjust=False).mean().values * 5
        
        # 上穿零轴
        main_cross_up = (main_line > 0) & (np.roll(main_line, 1) <= 0)
        
        # 散户下降
        retail_down = retail_line < np.roll(retail_line, 1)
        
        df['主力线'] = np.round(main_line, 4)
        df['散户线'] = np.round(retail_line, 4)
        df['主力上穿零轴'] = main_cross_up
        df['散户下降'] = retail_down
        df['COND4_雷达'] = main_cross_up & retail_down
        
        return df
    
    # ═══════════════════════════════════════════════════════════════════
    # 6. 买卖信号生成
    # ═══════════════════════════════════════════════════════════════════
    
    def _generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        买入条件: COND1 AND COND2 AND COND3 AND COND4 AND 暗盘流入
        卖出条件: 主力拐头向下 AND 暗盘流出 AND 明盘流出
        """
        # 买入信号
        buy = (
            df['COND1_主力持仓'] &
            df['COND2_暗盘连流'] &
            df['COND3_TCY'] &
            df['COND4_雷达'] &
            df['暗盘流入']
        )
        
        # 卖出条件
        main_line = df['主力线'].values
        main_peak = (
            (main_line < np.roll(main_line, 1)) &
            (np.roll(main_line, 1) > np.roll(main_line, 2))
        )
        
        sell = (
            main_peak &
            (df['暗盘资金'] < 0) &
            (df['大单净量'] < 0)
        )
        
        df['买入信号'] = buy
        df['卖出信号'] = sell
        
        # 信号计数（用于回测分析）
        df['信号累积'] = df['买入信号'].cumsum() - df['卖出信号'].cumsum()
        
        return df
    
    # ═══════════════════════════════════════════════════════════════════
    # 结果导出
    # ═══════════════════════════════════════════════════════════════════
    
    def get_signals(self) -> Optional[pd.DataFrame]:
        """获取计算完成的信号DataFrame"""
        return self._signals
    
    def signal_summary(self) -> dict:
        """生成信号统计摘要"""
        if self._signals is None:
            return {}
        
        df = self._signals
        total = len(df)
        buy_count = df['买入信号'].sum()
        sell_count = df['卖出信号'].sum()
        
        return {
            '总交易日': total,
            '买入信号': int(buy_count),
            '卖出信号': int(sell_count),
            '买入频率': f'{buy_count/total*100:.1f}%',
            '卖出频率': f'{sell_count/total*100:.1f}%',
            '当前信号': '买入' if buy_count > sell_count else
                       '卖出' if sell_count > buy_count else '无',
        }


# ═══════════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    
    code = sys.argv[1] if len(sys.argv) > 1 else '000001'
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 365
    
    print(f'正在获取 {code} 数据...')
    fetcher = DataFetcher()
    end = datetime.now().strftime('%Y-%m-%d')
    start = (datetime.now() - timedelta(days=int(days*1.4))).strftime('%Y-%m-%d')
    
    df = fetcher.get_kline(code, start, end)
    print(f'获取到 {len(df)} 根K线')
    
    print('执行薯仔策略计算...')
    strategy = ShuzaiStrategy()
    result = strategy.compute(df)
    
    summary = strategy.signal_summary()
    print(f'\n📊 信号统计:')
    for k, v in summary.items():
        print(f'   {k}: {v}')
    
    # 显示最近10个信号
    signals = result[result['买入信号'] | result['卖出信号']].tail(10)
    if not signals.empty:
        print(f'\n📈 最近信号:')
        for _, row in signals.iterrows():
            tag = '🟢买入' if row['买入信号'] else '🔴卖出'
            print(f'  {row["date"]:%Y-%m-%d} {tag}  '
                  f'收盘:{row["close"]:.2f} '
                  f'主力持仓:{row["主力持仓"]:.1f}%')
    else:
        print('\n⚠️ 近一年无信号产生')
        print('可能原因:')
        print('  1. LV2数据用近似替代后信号精度下降')
        print('  2. 建议接入真实LV2数据后重新运行')
        print('  3. 或当前股票确实不符合薯仔系统条件')

print('\n⚠️ 注意: 当前版本使用近似数据代替LV2字段')
print('  大单净量/暗盘资金/主力持仓为估算值')
print('  接入同花顺LV2后替换 _compute_dadan_net 等函数即可')
