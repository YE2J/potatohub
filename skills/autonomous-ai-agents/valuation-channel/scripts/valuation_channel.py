#!/usr/bin/env python3
"""
PE-TTM Valuation Channel Generator for A-Shares
================================================
Fully reproduces the 同花顺 (Tonghuashun) PE Band chart.
Data sources (both verified working):
  - K-line, PE, price: Tencent Finance (web.ifzq.gtimg.cn / qt.gtimg.cn)
  - Quarterly EPS: akshare (同花顺 backend, stock_financial_abstract_ths)

Algorithm:
  1. Collect daily K-line (unadjusted) + quarterly cumulative EPS
  2. Convert cumulative → standalone quarterly EPS → rolling TTM EPS
  3. PE = close / TTM_EPS on every trading day
  4. Window statistics: Min_PE (skip negative), Median_PE
  5. Step = 0.5 × (Median − Min)  →  5 channels: Min, Min+Step, Median, Min+3Step, Min+4Step
  6. For each date: theoretical_price = fixed_PE × TTM_EPS → 5 curved bands
  7. Interactive matplotlib chart with hover tooltip

Usage:
    from valuation_channel import ValuationChannelGenerator
    vcg = ValuationChannelGenerator()
    fig = vcg.generate('000001')
    vcg.save_image('/tmp/pe_band.png')
    df = vcg.export_data()
"""

import os, sys, json, time, re
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Optional, List, Tuple, Dict

import numpy as np
import pandas as pd
import requests
import matplotlib
import matplotlib
if os.environ.get('DISPLAY') or sys.platform != 'darwin':
    matplotlib.use('TkAgg')
else:
    matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch
import mplcursors

# ---------------------------------------------------------------------------
# 1.  Data Fetcher — Tencent K-line + 同花顺 EPS
# ---------------------------------------------------------------------------

class DataFetcher:
    """Unified data fetcher with in-memory caching."""

    _cache: Dict[str, object] = {}

    @staticmethod
    def _market_prefix(code: str) -> str:
        """Map 6-digit A-share code → 'sh' or 'sz'."""
        code = code.strip()
        if code.startswith(('6', '9')):
            return 'sh'
        return 'sz'  # 0, 3, 2 → Shenzhen

    @staticmethod
    def _normalise_code(code: str) -> str:
        """Return bare 6-digit code (strip any 'sh'/'sz' prefix)."""
        c = code.strip()
        for p in ('sh', 'sz', 'SH', 'SZ', 'SH', 'SZ'):
            if c.startswith(p):
                c = c[len(p):]
                break
        return c

    # ── Tencent K-line ──────────────────────────────────────────────

    @classmethod
    def get_kline(cls, code: str,
                  start_date: str = '2020-01-01',
                  end_date: Optional[str] = None,
                  freq: str = 'day') -> pd.DataFrame:
        """
        Fetch daily (unadjusted) K-line from Tencent.
        Returns DataFrame with columns:
          date, open, close, high, low, volume
        """
        cache_key = f'tencent_kline_{code}_{freq}_{start_date}_{end_date}'
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        bare = cls._normalise_code(code)
        prefixed = cls._market_prefix(bare) + bare
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')

        headers = {'User-Agent': 'Mozilla/5.0'}
        all_rows = []

        # Tencent API returns max ~640 records per call → paginate
        seg_start = datetime.strptime(start_date, '%Y-%m-%d')
        seg_end = datetime.strptime(end_date, '%Y-%m-%d')

        while seg_start < seg_end:
            s = seg_start.strftime('%Y-%m-%d')
            e = min(seg_start + timedelta(days=540), seg_end).strftime('%Y-%m-%d')
            url = (f'https://ifzq.gtimg.cn/appstock/app/fqkline/get'
                   f'?param={prefixed},{freq},{s},{e},800,')
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                raise RuntimeError(f'Tencent API failed [{prefixed} {s}→{e}]: {exc}')

            kdata = (data.get('data', {})
                         .get(prefixed, {})
                         .get('day', []))

            if not kdata:
                # Fall back to adjusted if no unadjusted available
                kdata = (data.get('data', {})
                             .get(prefixed, {})
                             .get('qfqday', []))

            if kdata:
                all_rows.extend(kdata)
                last_dt = datetime.strptime(kdata[-1][0], '%Y-%m-%d')
                seg_start = last_dt + timedelta(days=1)
            else:
                # No data in this range — advance to avoid infinite loop
                seg_start = seg_end

        if not all_rows:
            raise ValueError(f'No K-line data for {code}')

        # Some rows have a 7th field (dividend info on ex-dividend dates)
        all_rows = [r[:6] for r in all_rows]

        df = pd.DataFrame(all_rows, columns=[
            'date', 'open', 'close', 'high', 'low', 'volume'
        ])
        df['date'] = pd.to_datetime(df['date'])
        for col in ('open', 'close', 'high', 'low'):
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        df.sort_values('date', inplace=True)
        df.drop_duplicates(subset='date', keep='first', inplace=True)
        df.reset_index(drop=True, inplace=True)

        cls._cache[cache_key] = df
        return df

    # ── 同花顺 Quarterly EPS ────────────────────────────────────────

    @classmethod
    def get_eps_quarterly(cls, code: str) -> pd.DataFrame:
        """
        Fetch quarterly cumulative EPS via akshare 同花顺 backend.
        Returns DataFrame:
          report_date (datetime), cum_eps (float), standalone_eps (float)
        """
        cache_key = f'ths_eps_{code}'
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        import akshare as ak

        bare = cls._normalise_code(code)
        try:
            df = ak.stock_financial_abstract_ths(
                symbol=bare, indicator='按报告期'
            )
        except Exception as exc:
            raise RuntimeError(f'同花顺 EPS API failed for {code}: {exc}')

        if df.empty or '基本每股收益' not in df.columns:
            raise ValueError(f'No EPS data for {code}')

        raw = df[['报告期', '基本每股收益']].copy()
        raw.columns = ['report_date', 'cum_eps']
        raw['report_date'] = pd.to_datetime(raw['report_date'])
        raw['cum_eps'] = pd.to_numeric(raw['cum_eps'], errors='coerce')
        raw.sort_values('report_date', inplace=True)
        raw.dropna(subset=['cum_eps'], inplace=True)

        # Convert cumulative → standalone quarterly EPS
        eps_vals = raw['cum_eps'].values
        years = raw['report_date'].dt.year.values
        standalones = []
        prev_same_year = 0.0
        prev_year_end = 0.0

        for i, (dt, cum) in enumerate(zip(raw['report_date'], eps_vals)):
            if cum is False or pd.isna(cum) or cum == 0:
                standalones.append(0.0)
                continue
            m = dt.month
            if m == 3:      # Q1 standalone = cumulative Q1
                standalone = float(cum)
                prev_same_year = float(cum)
            elif m == 6:    # H1 standalone = cumulative H1 - cumulative Q1
                standalone = float(cum) - prev_same_year
                prev_same_year = float(cum)
            elif m == 9:    # 9M standalone = cumulative 9M - cumulative H1
                standalone = float(cum) - prev_same_year
                prev_same_year = float(cum)
            else:           # FY standalone = FY - 9M
                standalone = float(cum) - prev_same_year
                prev_year_end = float(cum)
                prev_same_year = 0.0
            standalones.append(round(standalone, 6))

        raw['standalone_eps'] = standalones
        # Clean False / 0 values
        raw = raw[raw['standalone_eps'] > 0].copy()

        cls._cache[cache_key] = raw
        return raw

    # ── Today's real-time PE (for verification / fallback) ───────────

    @classmethod
    def get_current_pe_ttm(cls, code: str) -> Optional[float]:
        """Get today's PE-TTM from Tencent real-time quote (position 39)."""
        bare = cls._normalise_code(code)
        prefixed = cls._market_prefix(bare) + bare
        headers = {'User-Agent': 'Mozilla/5.0'}
        try:
            resp = requests.get(
                f'https://qt.gtimg.cn/q={prefixed}',
                headers=headers, timeout=10
            )
            parts = resp.text.split('~')
            if len(parts) > 39:
                pe = float(parts[39])
                return pe if pe > 0 else None
        except Exception:
            pass
        return None

    @classmethod
    def get_stock_name(cls, code: str) -> str:
        """Fetch stock Chinese name from Tencent real-time quote."""
        bare = cls._normalise_code(code)
        prefixed = cls._market_prefix(bare) + bare
        try:
            resp = requests.get(
                f'https://qt.gtimg.cn/q={prefixed}',
                headers={'User-Agent': 'Mozilla/5.0'}, timeout=5
            )
            parts = resp.text.split('~')
            if len(parts) > 1:
                return parts[1].strip()
        except Exception:
            pass
        return code

    @classmethod
    def get_total_shares(cls, code: str) -> Optional[float]:
        """Get total shares (亿股) from Tencent real-time quote."""
        bare = cls._normalise_code(code)
        prefixed = cls._market_prefix(bare) + bare
        try:
            resp = requests.get(
                f'https://qt.gtimg.cn/q={prefixed}',
                headers={'User-Agent': 'Mozilla/5.0'}, timeout=5
            )
            parts = resp.text.split('~')
            if len(parts) > 45:
                mcap = float(parts[44])
                price = float(parts[3])
                if price > 0:
                    return mcap / price
        except Exception:
            pass
        return None

    @classmethod
    def clear_cache(cls):
        cls._cache.clear()


# ---------------------------------------------------------------------------
# 2.  TTM EPS Computation
# ---------------------------------------------------------------------------

def compute_ttm_eps(daily_dates: pd.DatetimeIndex,
                    eps_quarterly: pd.DataFrame) -> pd.Series:
    """
    For every date in `daily_dates`, compute the trailing-12-month EPS
    using the latest available quarterly standalone values.

    Parameters
    ----------
    daily_dates : pd.DatetimeIndex
        All trading days in the analysis window.
    eps_quarterly : pd.DataFrame
        Columns: report_date, standalone_eps (sorted).

    Returns
    -------
    pd.Series indexed by daily_dates, values = TTM EPS at that date.
    """
    qdata = eps_quarterly[['report_date', 'standalone_eps']].copy()
    qdata.sort_values('report_date', inplace=True)

    # Build a lookup: for each date, what 4 quarters' standalone EPS
    # constitute the trailing 12 months?
    qd = qdata['report_date'].values
    qv = qdata['standalone_eps'].values
    nq = len(qd)

    ttm = []
    for d in daily_dates:
        # Find all quarterly reports ≤ this date
        mask = qd <= np.datetime64(d)
        idx = np.where(mask)[0]

        if len(idx) < 4:
            # Not enough history — use whatever is available
            total = float(qv[idx].sum()) if len(idx) > 0 else 0.0
        else:
            # Latest 4 quarterly standalones
            total = float(qv[idx[-4:]].sum())

        ttm.append(total)

    return pd.Series(ttm, index=daily_dates, name='ttm_eps')


def compute_ttm_metric(daily_dates: pd.DatetimeIndex,
                       df_financial: pd.DataFrame,
                       metric_col: str) -> pd.Series:
    """
    Generic TTM computation for any quarterly cumulative metric.

    Parameters
    ----------
    daily_dates : pd.DatetimeIndex
        All trading days.
    df_financial : pd.DataFrame
        From stock_financial_abstract_ths with columns 报告期, metric_col.
    metric_col : str
        Column name for the metric (e.g., '营业总收入', '每股净资产').

    Returns
    -------
    pd.Series indexed by daily_dates, values = TTM metric at each date.
    """
    raw = df_financial[['报告期', metric_col]].copy()
    raw.columns = ['date', 'val']
    raw['date'] = pd.to_datetime(raw['date'])
    raw.sort_values('date', inplace=True)

    # Parse metric value (might be "1466.95亿" or a plain number)
    def parse_val(v):
        if v is None or v is False or pd.isna(v):
            return 0.0
        s = str(v).strip().replace('元', '').replace('亿', '').replace(' ', '')
        try:
            return float(s)
        except ValueError:
            return 0.0

    raw['val'] = raw['val'].apply(parse_val)

    qd = raw['date'].values
    qv = raw['val'].values
    nq = len(qd)

    # Convert cumulative → standalone (if it's a cumulative metric like revenue)
    # Determine if this is a cumulative metric by checking if values increase
    # within each year
    standalones = []
    prev_same_year = 0.0
    for i, (dt, v) in enumerate(zip(qd, qv)):
        if v == 0:
            standalones.append(0.0)
            continue
        m = pd.Timestamp(dt).month
        if m == 3:
            standalone = v
            prev_same_year = v
        elif m == 6:
            standalone = v - prev_same_year if v > prev_same_year else v
            prev_same_year = v
        elif m == 9:
            standalone = v - prev_same_year if v > prev_same_year else v
            prev_same_year = v
        else:
            standalone = v - prev_same_year if v > prev_same_year else v
            prev_same_year = 0.0
        standalones.append(max(0.0, standalone))

    # For non-cumulative metrics (BVPS), use raw values directly
    ttm = []
    for d in daily_dates:
        mask = qd <= np.datetime64(d)
        idx = np.where(mask)[0]
        total = sum(standalones[i] for i in idx[-4:]) if len(idx) > 0 else 0.0
        ttm.append(round(total, 4))

    return pd.Series(ttm, index=daily_dates, name=f'ttm_{metric_col}')


class MultiChannelValuation:
    """
    Generate a 2×2 grid of 4 valuation channels (PE, PB, PS, PCF),
    matching the 同花顺 app's valuation channel layout.

    Channels:
    - PE-TTM (市盈率) = Price / TTM_EPS
    - PB-MRQ (市净率) = Price / BVPS (latest)
    - PS-TTM (市销率) = Price / TTM_SalesPerShare
    - PCF-TTM (市现率) = Price / TTM_CFPS
    """

    METRIC_CONFIG = {
        'PE': {
            'label': '市盈率 (PE-TTM)',
            'ylim_pad': 0.3,
            'color': '#2196F3',
            'unit': 'x',
        },
        'PB': {
            'label': '市净率 (PB-MRQ)',
            'ylim_pad': 0.3,
            'color': '#4CAF50',
            'unit': 'x',
        },
        'PS': {
            'label': '市销率 (PS-TTM)',
            'ylim_pad': 0.3,
            'color': '#FF9800',
            'unit': 'x',
        },
        'PCF': {
            'label': '市现率 (PCF-TTM)',
            'ylim_pad': 0.3,
            'color': '#9C27B0',
            'unit': 'x',
        },
    }

    def __init__(self):
        self.fetcher = DataFetcher()
        self._results: dict = {}

    def generate_all(self,
                     stock_code: str,
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None,
                     days: int = 252) -> plt.Figure:
        """
        Generate 2×2 grid of PE, PB, PS, PCF valuation channels.

        Returns matplotlib Figure with 4 subplots.
        """
        import akshare as ak

        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            sd = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=int(days*1.4))
            start_date = sd.strftime('%Y-%m-%d')

        bare = DataFetcher._normalise_code(stock_code)
        stock_name = DataFetcher.get_stock_name(stock_code)

        # Fetch data
        df_k = self.fetcher.get_kline(stock_code, start_date, end_date)
        df_fin = ak.stock_financial_abstract_ths(symbol=bare, indicator='按报告期')
        total_shares = self.fetcher.get_total_shares(stock_code) or 0

        current_price = float(df_k['close'].iloc[-1])
        dates = df_k['date'].values

        # Compute all TTM metrics
        ttm_eps = compute_ttm_eps(dates, self.fetcher.get_eps_quarterly(stock_code))
        ttm_rev = compute_ttm_metric(dates, df_fin, '营业总收入')
        ttm_cfps = compute_ttm_metric(dates, df_fin, '每股经营现金流')
        closes = df_k['close'].values

        # BVPS is a point-in-time metric, not cumulative
        bvps_raw = df_fin[['报告期', '每股净资产']].copy()
        bvps_raw.columns = ['date', 'bvps']
        bvps_raw['date'] = pd.to_datetime(bvps_raw['date'])
        bvps_raw['bvps'] = pd.to_numeric(bvps_raw['bvps'], errors='coerce')
        bvps_raw.sort_values('date', inplace=True)

        def get_latest_bvps(d):
            mask = bvps_raw['date'] <= pd.Timestamp(d)
            sub = bvps_raw[mask]
            return float(sub['bvps'].iloc[-1]) if not sub.empty else 0.0

        # Channel configurations
        channels_data = {}

        # PE Channel: PE = close / TTM_EPS at each date
        pe_vals = np.where(ttm_eps.values > 0,
                           closes / ttm_eps.values, np.nan)
        channels_data['PE'] = {
            'ratio': pe_vals,
            'unit': 'x',
            'label': '市盈率 (PE-TTM)',
        }

        # PB Channel: PB = close / BVPS at each date
        pb_vals_arr = np.full(len(dates), np.nan)
        for i, d in enumerate(dates):
            bv = get_latest_bvps(pd.Timestamp(d))
            pb_vals_arr[i] = closes[i] / bv if bv > 0 else np.nan
        channels_data['PB'] = {
            'ratio': pb_vals_arr,
            'unit': 'x',
            'label': '市净率 (PB-MRQ)',
        }

        # PS Channel: PS = close / SalesPerShare at each date
        # Convert TTM revenue (亿元) to sales per share
        rev_vals = ttm_rev.values
        if total_shares > 0:
            # total_shares is in 亿股, revenue is in 亿元
            # sales_per_share = revenue / shares
            sales_ps = np.where(rev_vals > 0, rev_vals / total_shares, 0)
        else:
            sales_ps = rev_vals
        ps_vals = np.where(sales_ps > 0, closes / sales_ps, np.nan)
        channels_data['PS'] = {
            'ratio': ps_vals,
            'unit': 'x',
            'label': '市销率 (PS-TTM)',
        }

        # PCF Channel: PCF = close / TTM_CFPS at each date
        cfps_arr = ttm_cfps.values
        pcf_vals = np.where(cfps_arr > 0, closes / cfps_arr, np.nan)
        channels_data['PCF'] = {
            'ratio': pcf_vals,
            'unit': 'x',
            'label': '市现率 (PCF-TTM)',
        }

        # Generate 2×2 plots
        plt.rcParams.update({
            'font.family': ['Heiti TC', 'PingFang HK', 'STHeiti', 'sans-serif'],
            'axes.unicode_minus': False,
        })

        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        fig.patch.set_facecolor('#f8f9fa')
        fig.suptitle(f'{stock_name} ({stock_code}) — 多维度估值通道',
                     fontsize=16, fontweight='bold', y=0.98)

        colors = {
            'PE': ['#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#2980b9'],
            'PB': ['#c0392b', '#d35400', '#f39c12', '#27ae60', '#2980b9'],
            'PS': ['#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#2196F3'],
            'PCF': ['#8e44ad', '#9b59b6', '#aed6f1', '#2ecc71', '#1abc9c'],
        }

        ax_map = {'PE': (0, 0), 'PB': (0, 1), 'PS': (1, 0), 'PCF': (1, 1)}

        for chan_name, ax_pos in ax_map.items():
            ax = axes[ax_pos]
            ch_data = channels_data[chan_name]
            ratio = ch_data['ratio']

            # Filter valid
            valid = ratio[~np.isnan(ratio) & (ratio > 0)]
            if len(valid) < 20:
                ax.text(0.5, 0.5, '数据不足', ha='center', va='center',
                       transform=ax.transAxes, fontsize=14, color='gray')
                ax.set_title(ch_data['label'])
                continue

            min_r = float(valid.min())
            median_r = float(np.median(valid))
            max_r = float(valid.max())
            step = 0.5 * (median_r - min_r)

            bands = {
                'low': min_r,
                'mid_low': min_r + step,
                'mid': median_r,
                'mid_high': min_r + 3 * step,
                'high': min_r + 4 * step,
            }

            band_labels = {
                'low': f'{min_r:.1f}x',
                'mid_low': f'{min_r+step:.1f}x',
                'mid': f'{median_r:.1f}x',
                'mid_high': f'{min_r+3*step:.1f}x',
                'high': f'{min_r+4*step:.1f}x',
            }

            label_names = ['低估', '偏低', '中位', '偏高', '高估']
            band_keys = ['low', 'mid_low', 'mid', 'mid_high', 'high']

            # Compute theoretical prices for each band
            if chan_name == 'PE':
                base_metric = ttm_eps.values
            elif chan_name == 'PB':
                base_metric = np.array([get_latest_bvps(pd.Timestamp(d)) for d in dates])
                base_metric = np.where(base_metric > 0, base_metric, np.nan)
            elif chan_name == 'PS':
                base_metric = sales_ps
            else:  # PCF
                base_metric = cfps_arr

            chan_colors = colors[chan_name]
            for i, bk in enumerate(band_keys):
                bp = bands[bk]
                price_line = bp * base_metric  # theoretical price
                ax.plot(dates, price_line,
                       color=chan_colors[i],
                       linewidth=1.0, alpha=0.8, linestyle='--',
                       label=f'{label_names[i]} ({band_labels[bk]})')

            # Actual price
            ax.plot(dates, df_k['close'].values,
                   color='#1a1a2e', linewidth=2.0, alpha=1.0,
                   label='收盘价', zorder=5)

            # Fill between bottom band
            bottom_band = bands['low'] * base_metric
            ax.fill_between(dates, df_k['close'].values, bottom_band,
                           where=(df_k['close'].values <= bottom_band),
                           color='#e74c3c', alpha=0.2)

            ax.set_title(ch_data['label'], fontsize=12, fontweight='bold')
            ax.legend(fontsize=7, loc='upper left', ncol=2)
            ax.grid(True, alpha=0.3, linestyle=':')
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=4))

            # Add stats text
            stats = (f'Min: {min_r:.1f}x  Med: {median_r:.1f}x  '
                    f'当前: {ratio[-1]:.1f}x' if not np.isnan(ratio[-1]) and ratio[-1] > 0 else '')
            ax.text(0.02, 0.98, stats, transform=ax.transAxes,
                   fontsize=8, va='top',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        plt.setp(axes, xticklabels=[])
        plt.setp(axes[1, 0].get_xticklabels(), rotation=45, ha='right', fontsize=8)
        plt.setp(axes[1, 1].get_xticklabels(), rotation=45, ha='right', fontsize=8)

        fig.tight_layout(rect=[0, 0, 1, 0.95])

        self._results[stock_code] = {
            'channels': channels_data,
            'stock_name': stock_name,
        }

        return fig


# ---------------------------------------------------------------------------
# 3.  Valuation Channel Generator (existing)
# ---------------------------------------------------------------------------

class ValuationChannelGenerator:
    """
    Generates a PE-TTM valuation channel (PE Band) for a given A-share stock.

    Channels (5 bands):
      Band 1 (bottom) = Min_PE
      Band 2          = Min + Step
      Band 3 (middle) = Median_PE
      Band 4          = Min + 3×Step
      Band 5 (top)    = Min + 4×Step
      where Step = 0.5 × (Median − Min)
    """

    def __init__(self):
        self.fetcher = DataFetcher()
        self._result: Optional[dict] = None

    # ── Core generation ─────────────────────────────────────────────

    def generate(self,
                 stock_code: str,
                 start_date: Optional[str] = None,
                 end_date: Optional[str] = None,
                 days: int = 252) -> plt.Figure:
        """
        Generate the valuation channel chart.

        Parameters
        ----------
        stock_code : str
            A-share stock code, e.g., '000001', '600519'.
        start_date : str, optional
            'YYYY-MM-DD'. Defaults to ~1 year ago (from `days`).
        end_date : str, optional
            'YYYY-MM-DD'. Defaults to today.
        days : int
            Approx trading days back from end_date (default 252 ≈ 1 year).

        Returns
        -------
        matplotlib.figure.Figure
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=int(days*1.4))
            start_date = start_dt.strftime('%Y-%m-%d')

        # 1. Fetch data
        df_k = self.fetcher.get_kline(stock_code, start_date, end_date)
        df_e = self.fetcher.get_eps_quarterly(stock_code)

        # 2. Compute TTM EPS
        ttm_eps = compute_ttm_eps(df_k['date'], df_e)
        df_k['ttm_eps'] = ttm_eps.values

        # 3. Calculate daily PE (filter TTM_EPS > 0 to avoid negative PE)
        mask = df_k['ttm_eps'] > 0
        df_k['pe_ttm'] = np.nan
        df_k.loc[mask, 'pe_ttm'] = df_k.loc[mask, 'close'] / df_k.loc[mask, 'ttm_eps']

        # 4. Filter analysis window
        window_start = pd.Timestamp(start_date)
        window_end = pd.Timestamp(end_date)
        in_window = (df_k['date'] >= window_start) & (df_k['date'] <= window_end)
        df_window = df_k[in_window].copy()

        if df_window.empty:
            raise ValueError(f'No data in window {start_date} → {end_date}')

        # 5. Compute channel statistics (filter PE > 0)
        pe_valid = df_window['pe_ttm'].dropna()
        pe_pos = pe_valid[pe_valid > 0]

        if len(pe_pos) < 20:
            raise ValueError(
                f'Insufficient valid PE data points ({len(pe_pos)}). '
                f'Stock may be loss-making or newly listed.'
            )

        min_pe = float(pe_pos.min())
        median_pe = float(pe_pos.median())
        max_pe = float(pe_pos.max())
        step = 0.5 * (median_pe - min_pe)

        # 6. Build 5 channels
        bands = {
            'band1_bottom': min_pe,
            'band2':        min_pe + step,
            'band3_mid':    median_pe,
            'band4':        min_pe + 3 * step,
            'band5_top':    min_pe + 4 * step,
        }

        # Build channel price curves (only where TTM_EPS > 0)
        df_display = df_window[df_window['ttm_eps'] > 0].copy()
        for name, pe_val in bands.items():
            df_display[f'price_{name}'] = pe_val * df_display['ttm_eps']

        # 7. Store result
        self._result = {
            'stock_code': stock_code,
            'start_date': start_date,
            'end_date': end_date,
            'df_kline': df_k,
            'df_display': df_display,
            'bands': bands,
            'min_pe': min_pe,
            'median_pe': median_pe,
            'max_pe': max_pe,
            'step': step,
        }

        # 8. Plot
        fig = self._plot(df_display, bands, stock_code, start_date, end_date)
        return fig

    # ── Plotting ─────────────────────────────────────────────────────

    def _plot(self,
              df: pd.DataFrame,
              bands: dict,
              code: str,
              start: str,
              end: str) -> plt.Figure:
        """Internal: build and return the matplotlib figure."""

        # Also try to get stock name from Tencent
        stock_name = self._get_stock_name(code)

        plt.rcParams.update({
            'font.family': ['Heiti TC', 'PingFang HK', 'STHeiti', 'Songti SC', 'sans-serif'],
            'axes.unicode_minus': False,
        })

        fig, ax = plt.subplots(figsize=(14, 7))
        fig.patch.set_facecolor('#f8f9fa')
        ax.set_facecolor('#ffffff')

        dates = df['date'].values
        colors = ['#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#2980b9']
        labels_order = ['band1_bottom', 'band2', 'band3_mid', 'band4', 'band5_top']
        label_names = {
            'band1_bottom': '低估值',
            'band2': '偏低',
            'band3_mid': '中位',
            'band4': '偏高',
            'band5_top': '高估值',
        }

        # Plot channel bands (fill between them for visual clarity)
        band_cols = [f'price_{b}' for b in labels_order]
        for i in range(len(band_cols) - 1):
            ax.fill_between(
                dates,
                df[band_cols[i]].values,
                df[band_cols[i + 1]].values,
                color=colors[i],
                alpha=0.08,
            )

        # Plot band lines
        band_lines = []
        band_legend = []
        for i, bname in enumerate(labels_order):
            col = f'price_{bname}'
            pe_val = bands[bname]
            line, = ax.plot(
                dates, df[col].values,
                color=colors[i],
                linewidth=1.0,
                alpha=0.85,
                linestyle='--',
                marker='',
            )
            band_lines.append(line)
            band_legend.append(f'{label_names[bname]} ({pe_val:.1f}x)')

        # Plot actual close price
        (price_line,) = ax.plot(
            dates, df['close'].values,
            color='#1a1a2e',
            linewidth=2.0,
            alpha=1.0,
            label='收盘价',
            zorder=5,
        )

        # Fill the area where price is below the lowest band
        ax.fill_between(
            dates,
            df['close'].values,
            df[band_cols[0]].values,
            where=(df['close'].values <= df[band_cols[0]].values),
            color='#e74c3c',
            alpha=0.25,
            label='低于底部 (低估)',
        )

        # Legend
        first_legend = ax.legend(
            handles=[price_line] + band_lines,
            labels=['收盘价'] + band_legend,
            loc='upper left',
            framealpha=0.9,
            fontsize=9,
            ncol=2,
        )
        ax.add_artist(first_legend)

        # Title
        title = f'{stock_name} ({code}) — PE-TTM 估值通道'
        subtitle = f'{start} 至 {end}  |  '
        subtitle += f'Min PE: {self._result["min_pe"]:.1f}x  '
        subtitle += f'Median PE: {self._result["median_pe"]:.1f}x  '
        subtitle += f'步长: {self._result["step"]:.1f}x'

        ax.set_title(f'{title}\n{subtitle}',
                     fontsize=14, fontweight='bold', linespacing=1.5)

        ax.set_ylabel('股价 (元)', fontsize=11)
        ax.set_xlabel('')

        # Date axis formatting
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax.get_xticklabels(), rotation=45, ha='right', fontsize=8)

        ax.grid(True, alpha=0.3, linestyle=':')
        ax.margins(x=0.02)

        # ── Interactive hover tooltip ────────────────────────────────
        cursor = mplcursors.cursor(price_line, hover=True)

        @cursor.connect('add')
        def on_hover(sel):
            idx = sel.index
            row = df.iloc[idx]
            d = row['date']
            if hasattr(d, 'strftime'):
                d_str = d.strftime('%Y-%m-%d')
            else:
                d_str = str(d)[:10]

            close_val = float(row['close'])
            text_lines = [
                f'📅 {d_str}',
                f'💰 收盘价: {close_val:.2f}',
                '',
                '📊 理论价位:',
            ]
            for bname in labels_order:
                col = f'price_{bname}'
                pe_val = bands[bname]
                pv = float(row.get(col, np.nan))
                if not np.isnan(pv):
                    text_lines.append(f'  {label_names[bname]} ({pe_val:.1f}x): {pv:.2f}')

            # PE at this date
            pe = row.get('pe_ttm', np.nan)
            if not np.isnan(pe) and pe > 0:
                text_lines.append(f'\n当前 PE-TTM: {pe:.1f}x')

            sel.annotation.set_text('\n'.join(text_lines))
            sel.annotation.get_bbox_patch().set(
                boxstyle='round,pad=0.5',
                facecolor='#1a1a2e',
                edgecolor='#333',
                alpha=0.92,
            )
            sel.annotation.set_color('#ffffff')
            sel.annotation.set_fontsize(9)

        fig.tight_layout()
        return fig

    def _get_stock_name(self, code: str) -> str:
        return DataFetcher.get_stock_name(code)

    # ── Utility methods ──────────────────────────────────────────────

    def save_image(self, path: str, dpi: int = 150):
        """Save the current chart to a file."""
        if self._result is None:
            raise RuntimeError('No chart generated. Call generate() first.')
        fig = plt.gcf()
        fig.savefig(path, dpi=dpi, bbox_inches='tight',
                    facecolor=fig.get_facecolor())

    def export_data(self) -> pd.DataFrame:
        """
        Return a DataFrame with all channel price data.

        Columns: date, close, ttm_eps, pe_ttm,
                 price_band1_bottom, price_band2, price_band3_mid,
                 price_band4, price_band5_top
        """
        if self._result is None:
            raise RuntimeError('No data. Call generate() first.')
        df = self._result['df_display'].copy()
        bands = self._result['bands']
        cols = ['date', 'close', 'ttm_eps', 'pe_ttm']
        cols += [f'price_{b}' for b in bands]
        available = [c for c in cols if c in df.columns]
        return df[available].round(4)


# ---------------------------------------------------------------------------
# 4.  Batch Scanner — find stocks near the bottom of their channel
# ---------------------------------------------------------------------------

class BatchScanner:
    """
    Scan a list of stocks and find those trading near the bottom
    of their PE channel.

    "At the bottom" = close price is ≤ band2 (i.e., in the lowest 2 bands).
    """

    def __init__(self, concurrency: int = 3):
        self.fetcher = DataFetcher()
        self.concurrency = concurrency
        self.results: List[dict] = []

    def scan(self,
             stock_codes: List[str],
             start_date: Optional[str] = None,
             end_date: Optional[str] = None,
             days: int = 252,
             verbose: bool = True) -> pd.DataFrame:
        """
        Scan all stocks and compute channel position.

        Returns DataFrame sorted by channel_position (0=bottom, 1=top).
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            sd = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=int(days*1.4))
            start_date = sd.strftime('%Y-%m-%d')

        results = []
        total = len(stock_codes)

        for i, code in enumerate(stock_codes):
            t0 = time.time()
            try:
                result = self._analyse_single(code, start_date, end_date)
                results.append(result)
                if verbose:
                    pct = result.get('channel_pct', 0)
                    marker = '⬇' if pct <= 20 else ('⬆' if pct >= 80 else '→')
                    print(f'[{i+1}/{total}] {code} {result.get("name","")}: '
                          f'通道位置={pct:.0f}% {marker}  '
                          f'({time.time()-t0:.1f}s)')
            except Exception as e:
                if verbose:
                    print(f'[{i+1}/{total}] {code}: SKIP — {e}')
                continue

        df = pd.DataFrame(results)
        if not df.empty:
            df['channel_pct'] = df['channel_pct'].clip(0, 100)
            df.sort_values('channel_pct', ascending=True, inplace=True)
            df.reset_index(drop=True, inplace=True)

        self.results = results
        return df

    def _analyse_single(self, code: str,
                        start_date: str,
                        end_date: str) -> dict:
        """Analyse one stock and return its channel position."""
        try:
            vcg = ValuationChannelGenerator()
            vcg.generate(code, start_date=start_date, end_date=end_date)
        except Exception:
            raise

        r = vcg._result
        df = r['df_display']
        last = df.iloc[-1]
        close = float(last['close'])
        bands = r['bands']
        band_cols = [f'price_{b}' for b in ['band1_bottom', 'band2',
                                              'band3_mid', 'band4', 'band5_top']]
        band_vals = [float(last[c]) for c in band_cols]

        # Channel position: where does the current price sit?
        # 0% = at bottom band, 100% = above top band
        bottom = band_vals[0]
        top = band_vals[-1]
        if close <= bottom:
            pct = 0.0
        elif close >= top:
            pct = 100.0
        else:
            pct = (close - bottom) / (top - bottom) * 100.0

        name = DataFetcher.get_stock_name(code)

        return {
            'code': code,
            'name': name,
            'close': round(close, 2),
            'pe_ttm': round(float(last.get('pe_ttm', 0)), 2) if last.get('pe_ttm') else 0,
            'min_pe': round(r['min_pe'], 1),
            'median_pe': round(r['median_pe'], 1),
            'max_pe': round(r['max_pe'], 1),
            'channel_pct': round(pct, 1),
            'band1_price': round(band_vals[0], 2),
            'band2_price': round(band_vals[1], 2),
            'band3_price': round(band_vals[2], 2),
            'band4_price': round(band_vals[3], 2),
            'band5_price': round(band_vals[4], 2),
        }


# ---------------------------------------------------------------------------
# 5.  ValuationAssessor — Multi-Model Valuation Engine
# ---------------------------------------------------------------------------

class GrowthRateEstimator:
    """Estimate growth rates from historical financial data."""

    @staticmethod
    def parse_pct(val) -> float:
        """Parse percentage string (e.g. '15.66%' or '-1.20%') to float."""
        if isinstance(val, str):
            return float(val.replace('%', '').strip()) / 100.0
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    @classmethod
    def revenue_growth_3yr(cls, df: pd.DataFrame) -> Tuple[float, float]:
        """
        Compute 3-year and 1-year revenue CAGR from annual (Q4) data.
        Returns (cagr_3y, growth_1y).
        """
        rev = df[['报告期', '营业总收入']].copy()
        rev.columns = ['date', 'revenue']
        rev['date'] = pd.to_datetime(rev['date'])
        rev.sort_values('date', inplace=True)

        # Take year-end (December) data only
        annual = rev[rev['date'].dt.month == 12].copy()
        annual['year'] = annual['date'].dt.year
        annual = annual[annual['revenue'].notna()]

        if len(annual) < 2:
            return 0.0, 0.0

        vals = []
        for _, row in annual.iterrows():
            try:
                v = float(str(row['revenue']).replace('亿', '').replace('元', '').strip())
                vals.append(v)
            except (ValueError, TypeError):
                vals.append(0.0)

        cagr_3y = 0.0
        if len(vals) >= 4 and vals[-1] > 0 and vals[-4] > 0:
            cagr_3y = (vals[-1] / vals[-4]) ** (1/3) - 1

        growth_1y = 0.0
        if len(vals) >= 2 and vals[-2] > 0:
            growth_1y = (vals[-1] - vals[-2]) / vals[-2]

        return cagr_3y, growth_1y

    @classmethod
    def eps_growth_rate(cls, eps_series: pd.Series) -> Tuple[float, float]:
        """
        Estimate EPS growth rate from a TTM EPS time series.
        Returns (cagr_3y, recent_growth).
        """
        vals = eps_series.dropna().values
        if len(vals) < 252:
            return 0.0, 0.0

        # Sample at ~yearly intervals
        n = len(vals)
        yearly = []
        for i in range(n - 1, -1, -int(n / 5)):
            if vals[i] > 0:
                yearly.append(vals[i])
            if len(yearly) >= 5:
                break
        yearly = yearly[::-1]

        cagr_3y = 0.0
        if len(yearly) >= 4 and yearly[-1] > 0 and yearly[-4] > 0:
            cagr_3y = (yearly[-1] / yearly[-4]) ** (1/3) - 1

        recent_growth = 0.0
        if len(yearly) >= 2 and yearly[-2] > 0:
            recent_growth = (yearly[-1] - yearly[-2]) / yearly[-2]

        return cagr_3y, recent_growth


class ValuationAssessor:
    """
    Multi-model A-share stock valuation assessment.

    Combines 5 valuation models into a consolidated fair-value estimate:

    1. **PE-TTM Channel** — historical valuation position
    2. **DCF (simplified)** — operating cash flow / FCF proxy
    3. **PB-ROE Framework** — justified PB → implied price
    4. **Graham Formula** — V = EPS × (8.5 + 2g)
    5. **PEG Ratio** — PE / growth rate
    6. **DDM (Dividend Discount)** — stable dividend model

    Usage:
        v = ValuationAssessor()
        report = v.evaluate('600519')
        print(report)
    """

    COST_OF_EQUITY = 0.10   # 10% required return for A-shares
    AAA_YIELD = 0.045       # ~4.5% for Chinese corporate bonds
    TERMINAL_GROWTH = 0.03  # perpetual growth rate

    def __init__(self):
        self.fetcher = DataFetcher()
        self._result: Optional[dict] = None

    def evaluate(self,
                 stock_code: str,
                 days: int = 252) -> str:
        """
        Run all valuation models and return a formatted report.

        Parameters
        ----------
        stock_code : str
            6-digit A-share code.
        days : int
            Lookback window for PE channel.

        Returns
        -------
        str : Formatted multi-line report.
        """
        bare = DataFetcher._normalise_code(stock_code)
        name = DataFetcher.get_stock_name(stock_code)

        # 1. Fetch data
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_dt = datetime.now() - timedelta(days=int(days * 1.4))
        start_date = start_dt.strftime('%Y-%m-%d')

        df_k = self.fetcher.get_kline(stock_code, start_date, end_date)
        df_e = self.fetcher.get_eps_quarterly(stock_code)

        # 2. Full financials (for growth rates & ROE)
        import akshare as ak
        df_fin = ak.stock_financial_abstract_ths(symbol=bare, indicator='按报告期')

        # 3. Current price
        current_price = float(df_k['close'].iloc[-1])

        # 4. TTM EPS & current PE
        ttm = compute_ttm_eps(df_k['date'], df_e)
        ttm_eps = float(ttm.iloc[-1])
        current_pe = current_price / ttm_eps if ttm_eps > 0 else 0

        # 5. ROE (latest annual)
        roe = self._get_roe(df_fin)
        bvps = self._get_bvps(df_fin)
        ops_cfps = self._get_ops_cfps(df_fin)

        # 6. Growth rates
        rev_cagr_3y, rev_growth_1y = GrowthRateEstimator.revenue_growth_3yr(df_fin)
        eps_cagr, eps_recent = GrowthRateEstimator.eps_growth_rate(ttm)

        # Conservative growth estimate (blend of EPS and revenue)
        growth_rate = max(0.0, min(
            (eps_cagr * 0.6 + rev_cagr_3y * 0.4),
            0.30  # Cap at 30%
        ))

        # 7. PE Channel
        vcg = ValuationChannelGenerator()
        try:
            vcg.generate(stock_code, start_date=start_date,
                         end_date=end_date, days=days)
            chan = vcg._result
            min_pe = chan['min_pe']
            median_pe = chan['median_pe']
            max_pe = chan['max_pe']
            channel_pct = self._calc_channel_pct(current_price, chan)
        except Exception:
            min_pe = median_pe = max_pe = channel_pct = 0

        # 8. Run models
        results = {}

        # DCF valuation
        fair_dcf, dcf_params = self._dcf_valuation(ops_cfps, growth_rate,
                                                      rev_cagr_3y)
        results['DCF'] = fair_dcf

        # PB-ROE valuation
        fair_pb_roe, pb_roe_params = self._pb_roe_valuation(
            bvps, roe, growth_rate)
        results['PB-ROE'] = fair_pb_roe

        # Graham valuation
        fair_graham, graham_params = self._graham_valuation(
            ttm_eps, growth_rate)
        results['Graham'] = fair_graham

        # PEG assessment
        peg, peg_status = self._peg_assessment(current_pe, growth_rate)
        results['PEG'] = peg

        # DDM valuation
        fair_ddm, ddm_params = self._ddm_valuation(bvps, roe, ttm_eps)
        results['DDM'] = fair_ddm

        # 9. Consensus & safety margin
        valid_vals = [v for v in [fair_dcf, fair_pb_roe, fair_graham, fair_ddm]
                      if v and v > 0]
        if valid_vals:
            consensus_fair = float(np.mean(valid_vals))
            consensus_low = float(np.min(valid_vals))
            consensus_high = float(np.max(valid_vals))
        else:
            consensus_fair = current_price
            consensus_low = current_price * 0.8
            consensus_high = current_price * 1.2

        safety_margin = (consensus_fair - current_price) / consensus_fair
        upside_pct = (consensus_high - current_price) / current_price * 100
        downside_pct = (consensus_low - current_price) / current_price * 100

        # 10. Store result
        self._result = {
            'stock_code': stock_code,
            'name': name,
            'price': current_price,
            'pe': current_pe,
            'ttm_eps': ttm_eps,
            'roe': roe,
            'bvps': bvps,
            'ops_cfps': ops_cfps,
            'growth_rate': growth_rate,
            'rev_cagr_3y': rev_cagr_3y,
            'channel': {
                'pos_pct': channel_pct,
                'min_pe': min_pe,
                'median_pe': median_pe,
                'max_pe': max_pe,
            },
            'dcf': fair_dcf,
            'pb_roe': fair_pb_roe,
            'graham': fair_graham,
            'peg': peg,
            'peg_status': peg_status,
            'ddm': fair_ddm,
            'consensus_fair': consensus_fair,
            'consensus_range': (consensus_low, consensus_high),
            'safety_margin': safety_margin,
            'upside': upside_pct,
            'downside': downside_pct,
        }

        return self._format_report()

    # ── Helper: extract financial metrics ────────────────────────────

    @staticmethod
    def _get_roe(df: pd.DataFrame) -> float:
        """Latest annual ROE (full year, last December)."""
        if '净资产收益率' not in df.columns:
            return 0.0
        mask = df['报告期'].str.endswith('12-31', na=False)
        annual = df[mask].tail(1)
        if annual.empty:
            return 0.0
        val = annual['净资产收益率'].iloc[-1]
        return GrowthRateEstimator.parse_pct(val)

    @staticmethod
    def _get_bvps(df: pd.DataFrame) -> float:
        """Latest book value per share."""
        if '每股净资产' not in df.columns:
            return 0.0
        val = df['每股净资产'].iloc[-1]
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _get_ops_cfps(df: pd.DataFrame) -> float:
        """Latest operating cash flow per share (annual)."""
        if '每股经营现金流' not in df.columns:
            return 0.0
        mask = df['报告期'].str.endswith('12-31', na=False)
        annual = df[mask].tail(1)
        if annual.empty:
            return 0.0
        val = annual['每股经营现金流'].iloc[-1]
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _calc_channel_pct(price: float, chan: dict) -> float:
        """Compute 0-100% position in the PE channel."""
        df = chan['df_display']
        last = df.iloc[-1]
        bands = chan['bands']
        bcols = [f'price_{b}' for b in ['band1_bottom', 'band5_top']]
        bottom = float(last[bcols[0]])
        top = float(last[bcols[1]])
        if top <= bottom:
            return 50.0
        return max(0.0, min(100.0, (price - bottom) / (top - bottom) * 100.0))

    # ── Valuation models ─────────────────────────────────────────────

    def _dcf_valuation(self, ops_cfps: float,
                       growth_rate: float,
                       rev_cagr: float) -> Tuple[Optional[float], dict]:
        """
        Simplified 2-stage DCF using operating CFPS as FCF proxy.

        Stage 1: 5 years at declining growth rate.
        Stage 2: Perpetuity at terminal_growth.
        """
        if ops_cfps <= 0:
            return None, {}

        # Use revenue CAGR as FCF growth proxy (more stable)
        fcf_growth = max(0.0, rev_cagr * 0.8)
        fcf_0 = ops_cfps
        disc_rate = self.COST_OF_EQUITY

        pv_fcf = 0.0
        fcf = fcf_0
        for yr in range(1, 6):
            decay = 1.0 - yr * 0.08  # gradually slow down
            g = max(fcf_growth * decay, self.TERMINAL_GROWTH)
            fcf *= (1 + g)
            pv_fcf += fcf / ((1 + disc_rate) ** yr)

        # Terminal value
        terminal_fcf = fcf * (1 + self.TERMINAL_GROWTH)
        terminal_value = terminal_fcf / (disc_rate - self.TERMINAL_GROWTH)
        pv_terminal = terminal_value / ((1 + disc_rate) ** 5)

        fair_value = pv_fcf + pv_terminal
        return round(fair_value, 2), {'fcf_0': fcf_0, 'terminal': pv_terminal}

    def _pb_roe_valuation(self, bvps: float, roe: float,
                          growth: float) -> Tuple[Optional[float], dict]:
        """
        PB = ROE × (1 - payout) / (r - g)

        Implied price = justified_PB × BVPS
        """
        if bvps <= 0 or roe <= 0:
            return None, {}

        r = self.COST_OF_EQUITY
        g = min(growth, roe * 0.6)  # sustainable growth = ROE × retention
        payout = max(0.2, 1.0 - g / max(roe, 0.01))

        justified_pb = roe * payout / (r - g) if r > g else 10.0
        justified_pb = max(0.5, min(justified_pb, 20.0))

        fair_value = justified_pb * bvps
        return round(fair_value, 2), {'pb': justified_pb}

    def _graham_valuation(self, eps_ttm: float,
                          growth: float) -> Tuple[Optional[float], dict]:
        """
        Graham formula: V = EPS × (8.5 + 2g) × 4.4 / Y

        Where:
          EPS = trailing 12-month EPS
          8.5 = base P/E for zero-growth stock
          g   = expected growth rate (%)
          4.4 = AAA bond yield in Graham's era
          Y   = current AAA bond yield
        """
        if eps_ttm <= 0:
            return None, {}

        g_pct = growth * 100  # convert to percentage
        base = 8.5 + 2 * g_pct
        fair_value = eps_ttm * base * (4.4 / (self.AAA_YIELD * 100))
        return round(fair_value, 2), {'base_pe': base}

    def _peg_assessment(self, pe: float,
                        growth: float) -> Tuple[Optional[float], str]:
        """
        PEG = PE / (growth × 100)
        PEG < 1 = undervalued, PEG > 2 = overvalued
        """
        if pe <= 0 or growth <= 0:
            return None, '数据不足'
        peg = pe / (growth * 100)
        status = '低估' if peg < 1.0 else '合理' if peg < 1.5 else '偏高' if peg < 2.0 else '高估'
        return round(peg, 2), status

    def _ddm_valuation(self, bvps: float, roe: float,
                       eps_ttm: float) -> Tuple[Optional[float], dict]:
        """
        DDM with stable dividend assumption.

        Dividend = EPS × payout_ratio (estimated from ROE × BVPS = EPS)
        Fair price = Dividend / (r - g)
        """
        if bvps <= 0 or eps_ttm <= 0:
            return None, {}

        r = self.COST_OF_EQUITY
        # Estimate retention ratio from sustainable growth
        implied_roe = eps_ttm / bvps if bvps > 0 else roe
        retention = max(0.1, min(0.7, self.TERMINAL_GROWTH / max(implied_roe, 0.01)))
        payout = 1 - retention
        dividend = eps_ttm * payout

        if dividend <= 0:
            return None, {}

        g_ddm = min(self.TERMINAL_GROWTH, r - 0.02)
        fair_value = dividend / (r - g_ddm) if r > g_ddm else dividend * 15
        return round(fair_value, 2), {'dividend': dividend}

    # ── Report formatting ──────────────────────────────────────────

    def _format_report(self) -> str:
        r = self._result
        lines = []
        sep = '━' * 48

        # Header
        lines.append(f'\n{sep}')
        lines.append(f'📊  {r["name"]} ({r["stock_code"]})  —  多模型估值')
        lines.append(f'📅  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
        lines.append(sep)

        # Current status
        lines.append(f'\n💰 当前价: {r["price"]:.2f}')
        lines.append(f'    PE-TTM: {r["pe"]:.1f}x   EPS-TTM: {r["ttm_eps"]:.4f}')
        lines.append(f'    ROE: {r["roe"]*100:.1f}%   BVPS: {r["bvps"]:.2f}')
        lines.append(f'   经营CFPS: {r["ops_cfps"]:.2f}')

        # Growth
        lines.append(f'\n📈 增长预估')
        lines.append(f'   营收3年CAGR: {r["rev_cagr_3y"]*100:.1f}%')
        lines.append(f'   综合增长预估: {r["growth_rate"]*100:.1f}%')

        # PE Channel
        ch = r['channel']
        lines.append(f'\n📊 PE通道 (1年)')
        lines.append(f'   通道位置: {ch["pos_pct"]:.0f}%  ' +
                     ('⬇ 低估' if ch['pos_pct'] < 20 else
                      '⬆ 高估' if ch['pos_pct'] > 80 else
                      '→ 合理'))
        lines.append(f'   Min PE: {ch["min_pe"]:.1f}x  →  ' +
                     f'Median: {ch["median_pe"]:.1f}x  →  Max: {ch["max_pe"]:.1f}x')

        # Model results
        lines.append(f'\n🔬 各模型估值')
        dcf = r['dcf']
        pb_roe = r['pb_roe']
        graham = r['graham']
        ddm = r['ddm']

        if dcf:
            lines.append(f'   📐 DCF(现金流折现):    {dcf:.2f}  ' +
                         self._vs_price(dcf, r['price']))
        if pb_roe:
            lines.append(f'   📐 PB-ROE框架:        {pb_roe:.2f}  ' +
                         self._vs_price(pb_roe, r['price']))
        if graham:
            lines.append(f'   📐 格雷厄姆公式:      {graham:.2f}  ' +
                         self._vs_price(graham, r['price']))
        if ddm:
            lines.append(f'   📐 DDM(股息折现):     {ddm:.2f}  ' +
                         self._vs_price(ddm, r['price']))

        peg_val = r['peg']
        if peg_val:
            peg_label = r.get('peg_status', '')
            lines.append(f'   📐 PEG:               {peg_val:.2f}  ({peg_label})')

        # Consensus
        cf = r['consensus_fair']
        cl, ch_ = r['consensus_range']
        sm = r['safety_margin']
        up = r['upside']
        down = r['downside']

        lines.append(f'\n{sep}')
        lines.append(f'🎯 综合合理估值区间: {cl:.2f}  ~  {ch_:.2f}')
        lines.append(f'   中轴: {cf:.2f}')
        lines.append(f'🔐 安全边际: {sm*100:.1f}%  ' +
                     ('✅ 充足' if sm > 0.2 else
                      '⚠️ 适中' if sm > 0.05 else
                      '❌ 不足'))
        lines.append(f'📈 潜在上涨空间: +{up:.1f}%')
        lines.append(f'📉 潜在下跌空间: {down:.1f}%')

        # Rating
        rating, stars = self._rating(sm, ch['pos_pct'], r['pe'], r['growth_rate'])
        lines.append(f'\n⭐ 综合评级: {stars}  {rating}')
        lines.append(sep)

        return '\n'.join(lines)

    @staticmethod
    def _vs_price(fair: float, price: float) -> str:
        if fair <= 0 or price <= 0:
            return ''
        ratio = (fair - price) / fair
        if ratio > 0.15:
            return '⬆ 被低估'
        elif ratio > -0.15:
            return '→ 合理'
        else:
            return '⬇ 被高估'

    @staticmethod
    def _rating(safety_margin: float, channel_pct: float,
                pe: float, growth: float) -> Tuple[str, str]:
        score = 0
        if safety_margin > 0.20:
            score += 3
        elif safety_margin > 0.05:
            score += 1

        if channel_pct < 20:
            score += 2
        elif channel_pct < 50:
            score += 1

        if growth > 0.10 and pe < growth * 100:
            score += 2

        if score >= 5:
            return '强烈推荐 ⭐⭐⭐⭐⭐', '⭐⭐⭐⭐⭐'
        elif score >= 3:
            return '推荐 ⭐⭐⭐⭐', '⭐⭐⭐⭐'
        elif score >= 2:
            return '中性 ⭐⭐⭐', '⭐⭐⭐'
        elif score >= 1:
            return '谨慎 ⭐⭐', '⭐⭐'
        else:
            return '回避 ⭐', '⭐'


# ---------------------------------------------------------------------------
# 6.  CLI Entry Point
# ---------------------------------------------------------------------------

def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='PE-TTM Valuation Channel Generator for A-Shares'
    )
    parser.add_argument('code', nargs='?', default='000001',
                        help='Stock code, e.g., 000001, 600519')
    parser.add_argument('--start', default=None,
                        help='Start date YYYY-MM-DD')
    parser.add_argument('--end', default=None,
                        help='End date YYYY-MM-DD')
    parser.add_argument('--days', type=int, default=252,
                        help='Trading days lookback (default: 252)')
    parser.add_argument('--output', '-o', default=None,
                        help='Save chart to file (.png)')
    parser.add_argument('--export-csv', default=None,
                        help='Export channel data to CSV')
    parser.add_argument('--batch', default=None,
                        help='Comma-separated stock codes for batch scan')
    parser.add_argument('--top', type=int, default=10,
                        help='Show top N in batch scan (default: 10)')
    parser.add_argument('--no-show', action='store_true',
                        help='Do not call plt.show()')
    parser.add_argument('--evaluate', '-e', action='store_true',
                        help='Run multi-model valuation assessment instead of chart')
    parser.add_argument('--all-channels', '-a', action='store_true',
                        help='Generate 2x2 grid of PE/PB/PS/PCF channels')

    args = parser.parse_args()

    if args.evaluate:
        va = ValuationAssessor()
        report = va.evaluate(args.code, days=args.days)
        print(report)
        sys.exit(0)

    if args.all_channels:
        mcv = MultiChannelValuation()
        fig = mcv.generate_all(args.code, args.start, args.end, args.days)
        print(f'✓ 四通道估值图生成完毕')
        if args.output:
            fig.savefig(args.output, dpi=150, bbox_inches='tight')
            print(f'✓ 已保存: {args.output}')
        if not args.no_show:
            plt.show()
        else:
            plt.close(fig)
        sys.exit(0)

    if args.batch:
        codes = [c.strip() for c in args.batch.split(',') if c.strip()]
        scanner = BatchScanner()
        df = scanner.scan(codes, args.start, args.end, args.days)
        print(f'\n==== 通道底部排名 (Top {args.top}) ====')
        print(df.head(args.top).to_string(index=False))
        if args.export_csv:
            df.to_csv(args.export_csv, index=False)
            print(f'\n已导出: {args.export_csv}')
        sys.exit(0)

    # Single stock mode
    print(f'正在获取 {args.code} 的数据...')
    vcg = ValuationChannelGenerator()
    fig = vcg.generate(args.code, start_date=args.start,
                        end_date=args.end, days=args.days)
    print('✓ PE通道生成完毕')

    data = vcg.export_data()
    print(data.tail(3).to_string(index=False))

    if args.output:
        vcg.save_image(args.output)
        print(f'✓ 图表已保存: {args.output}')

    if args.export_csv:
        data.to_csv(args.export_csv, index=False)
        print(f'✓ 数据已导出: {args.export_csv}')

    if args.no_show:
        plt.close(fig)
    else:
        plt.show()
