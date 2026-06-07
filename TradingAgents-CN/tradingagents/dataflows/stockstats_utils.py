import pandas as pd
from stockstats import wrap
from typing import Annotated
import os
import time
import datetime
import threading
import random
from .config import get_config

# ============================================================
# Global BaoStock connection manager
# BaoStock uses a global singleton connection. Multiple login/logout
# calls in the same process will interfere with each other.
# Solution: login once, reuse, logout only at process exit.
# ============================================================
_bs_lock = threading.Lock()
_bs_logged_in = False


def _ensure_bs_login():
    """Ensure BaoStock is logged in exactly once per process."""
    global _bs_logged_in
    if _bs_logged_in:
        return
    with _bs_lock:
        if _bs_logged_in:
            return
        import baostock as bs
        lg = bs.login()
        if lg is None:
            raise Exception("BaoStock login returned None - connection failed")
        if lg.error_code != "0":
            raise Exception(f"BaoStock login failed: {lg.error_msg}")
        _bs_logged_in = True
        import atexit
        def _bs_logout():
            global _bs_logged_in
            if _bs_logged_in:
                try:
                    bs.logout()
                except Exception:
                    pass
                _bs_logged_in = False
        atexit.register(_bs_logout)
        print("[bs] BaoStock logged in (global, shared connection)")


def _convert_symbol_to_tickflow(symbol):
    """Convert symbol from project format (e.g. '000001.SZ' or '600000.SH') to TickFlow format.
    TickFlow uses: 代码.市场后缀 where suffix is SH/SZ/BJ/US/HK etc.
    The project already uses this format, but we ensure it's uppercased correctly.
    """
    # symbol is like "000001.SZ" or "600000.SH" - already compatible
    # Just ensure uppercase suffix
    parts = symbol.rsplit(".", 1)
    if len(parts) == 2:
        code = parts[0].zfill(6)
        suffix = parts[1].upper()
        # Normalize: SZ/SS/ZS → SZ, SH/HS → SH, BJ → BJ
        if suffix in ("SZ", "SS", "ZS", "SHE"):
            suffix = "SZ"
        elif suffix in ("SH", "HS", "SSH"):
            suffix = "SH"
        elif suffix == "BJ":
            suffix = "BJ"
        return f"{code}.{suffix}"
    return symbol


def _fetch_data_tickflow(symbol, start_date, end_date):
    """Fetch A-share stock data using TickFlow (free tier, no API key required).
    Returns DataFrame in yfinance-compatible format.
    
    TickFlow free tier supports: 1d/1w/1M/1Q/1Y periods, up to 10000 bars per call.
    Rate limiting: TickFlow free tier doesn't need manual delay (SDK handles it internally).
    
    Note: The free tier prints a lengthy notice to stdout on first init. We suppress it
    by redirecting stdout to a null device during initialization, then restore immediately.
    This is safe because TickFlow.free() only prints during construction, not during data calls.
    """
    import sys
    import os
    from contextlib import redirect_stdout
    from tickflow import TickFlow

    # Suppress TickFlow free tier notice banner (it uses emoji which breaks Windows GBK)
    with redirect_stdout(open(os.devnull, 'w', encoding='utf-8')):
        tf = TickFlow.free()

    # Convert dates to millisecond timestamps
    start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d")
    # Add 1 day to end to include end_date's data
    end_dt = end_dt + datetime.timedelta(days=1)
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    tickflow_symbol = _convert_symbol_to_tickflow(symbol)

    df = tf.klines.get(
        tickflow_symbol,
        period="1d",
        start_time=start_ms,
        end_time=end_ms,
        count=10000,
        adjust="forward",  # 前复权，与项目中其他数据源一致
        as_dataframe=True,
    )

    if df is None or df.empty:
        raise Exception(f"TickFlow returned empty data for {symbol}")

    # TickFlow returns columns: symbol, name, timestamp, trade_date, trade_time, open, high, low, close, volume, amount
    # Rename to yfinance-compatible format
    df.rename(columns={
        "trade_date": "Date",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
        "amount": "Amount",
    }, inplace=True)

    df["Date"] = pd.to_datetime(df["Date"])
    # TickFlow volume is in 手 (100 shares), convert to 股 for consistency with other sources
    # Note: BaoStock returns volume in 股, AKShare returns in 手
    # We keep TickFlow volume as-is (手) and let downstream stockstats handle it
    df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]

    return df


def _fetch_data_efinance(symbol, start_date, end_date):
    """Fetch A-share stock data using efinance (东方财富), returns DataFrame in yfinance-compatible format.
    efinance is free, stable, and doesn't have rate-limiting issues like yfinance.
    
    Rate limiting: 0.3~0.6s random delay to avoid triggering anti-scraping on eastmoney.
    """
    import efinance as ef

    # Rate limiting
    delay = random.uniform(0.3, 0.6)
    time.sleep(delay)

    # Strip suffix like .SZ, .SS, .SHE, .SH etc., get pure 6-digit code
    code = symbol.split(".")[0].zfill(6)

    df = ef.stock.get_quote_history(code)

    if df is None or df.empty:
        raise Exception(f"efinance returned empty data for {symbol}")

    # efinance returns columns: 股票名称, 股票代码, 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
    df.rename(columns={
        "日期": "Date",
        "开盘": "Open",
        "最高": "High",
        "最低": "Low",
        "收盘": "Close",
        "成交量": "Volume",
        "成交额": "Amount",
    }, inplace=True)

    df["Date"] = pd.to_datetime(df["Date"])
    df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]

    # Filter by date range
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    df = df[(df["Date"] >= start_dt) & (df["Date"] <= end_dt)]

    if df.empty:
        raise Exception(f"efinance returned no data in range {start_date} to {end_date} for {symbol}")

    return df


def _fetch_data_akshare(symbol, start_date, end_date):
    """Fetch A-share stock data using AKShare, returns DataFrame in yfinance-compatible format.
    
    Rate limiting: 0.5~1.0s random delay before each AKShare API call to avoid IP ban.
    """
    import akshare as ak
    
    # Strip suffix like .SZ, .SS, .SHE, .SH etc.
    code = symbol.split(".")[0].zfill(6)
    if code.startswith(('6', '9')):
        akshare_code = f"sh{code}"
    elif code.startswith(('0', '3')):
        akshare_code = f"sz{code}"
    elif code.startswith(('4', '8')):
        akshare_code = f"bj{code}"
    else:
        akshare_code = f"sz{code}"

    # Rate limiting: random delay 0.5~1.0s to avoid triggering anti-scraping
    delay = random.uniform(0.5, 1.0)
    time.sleep(delay)

    df = ak.stock_zh_a_hist(
        symbol=code,
        period="daily",
        start_date=start_date.replace("-", ""),
        end_date=end_date.replace("-", ""),
        adjust="qfq",
    )

    if df.empty:
        raise Exception(f"AKShare returned empty data for {symbol}")

    # Convert to yfinance-compatible format
    # AKShare 1.16.98 returns columns: 日期, 股票代码, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
    df.rename(columns={
        "日期": "Date",
        "开盘": "Open",
        "最高": "High",
        "最低": "Low",
        "收盘": "Close",
        "成交量": "Volume",
        "成交额": "Amount",
    }, inplace=True)

    df["Date"] = pd.to_datetime(df["Date"])
    df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]
    return df


def _fetch_data_baostock(symbol, start_date, end_date):
    """Fetch A-share stock data using BaoStock, returns DataFrame in yfinance-compatible format.
    Uses global shared connection - does NOT login/logout (managed by _ensure_bs_login)."""
    import baostock as bs

    # Ensure global login (idempotent - only logs in once per process)
    _ensure_bs_login()

    code = symbol.split(".")[0].zfill(6)
    if code.startswith(('6', '9')):
        baostock_code = f"sh.{code}"
    elif code.startswith(('0', '3')):
        baostock_code = f"sz.{code}"
    elif code.startswith(('4', '8')):
        baostock_code = f"bj.{code}"
    else:
        baostock_code = f"sz.{code}"

    rs = bs.query_history_k_data_plus(
        baostock_code,
        "date,open,high,low,close,volume",
        start_date=start_date.replace("-", ""),
        end_date=end_date.replace("-", ""),
        frequency="d",
        adjustflag="2",
    )

    if rs.error_code != "0":
        raise Exception(f"BaoStock query failed: {rs.error_msg}")

    rows = []
    while rs.next():
        rows.append(rs.get_row_data())

    if not rows:
        raise Exception(f"BaoStock returned empty data for {symbol}")

    data = pd.DataFrame(rows, columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data["Date"] = pd.to_datetime(data["Date"])
    return data


class StockstatsUtils:
    @staticmethod
    def get_stock_stats(
        symbol: Annotated[str, "ticker symbol for the company"],
        indicator: Annotated[
            str, "quantitative indicators based off of the stock data for the company"
        ],
        curr_date: Annotated[
            str, "curr date for retrieving stock price data, YYYY-mm-dd"
        ],
        data_dir: Annotated[
            str,
            "directory where the stock data is stored.",
        ],
        online: Annotated[
            bool,
            "whether to use online tools to fetch data or offline tools. If True, will use online tools.",
        ] = False,
    ):
        df = None
        data = None

        if not online:
            try:
                data = pd.read_csv(
                    os.path.join(
                        data_dir,
                        f"{symbol}-YFin-data-2015-01-01-2025-03-25.csv",
                    )
                )
                df = wrap(data)
            except FileNotFoundError:
                raise Exception("Stockstats fail: Yahoo Finance data not fetched yet!")
        else:
            # Use curr_date (analysis date) as end_date to avoid future data leakage
            # Critical: do NOT use pd.Timestamp.today() — that would leak future data in backtests
            curr_date_dt = pd.to_datetime(curr_date)

            end_date = curr_date_dt
            start_date = curr_date_dt - pd.DateOffset(years=15)
            start_date = start_date.strftime("%Y-%m-%d")
            end_date = end_date.strftime("%Y-%m-%d")

            # Get config and ensure cache directory exists
            config = get_config()
            os.makedirs(config["data_cache_dir"], exist_ok=True)

            data_file = os.path.join(
                config["data_cache_dir"],
                f"{symbol}-YFin-data-{start_date}-{end_date}.csv",
            )

            if os.path.exists(data_file):
                cached = pd.read_csv(data_file)
                if len(cached) > 0:
                    data = cached
                    data["Date"] = pd.to_datetime(data["Date"])
                # If cached file is empty, ignore it and re-fetch

            if data is None:
                errors = []

                # Priority: 1. TickFlow (free, stable, official API) → 2. AKShare → 3. BaoStock
                # 1. Try TickFlow first (free tier, no API key needed, stable official API)
                try:
                    print(f"[stockstats] Trying TickFlow for {symbol}...")
                    data = _fetch_data_tickflow(symbol, start_date, end_date)
                    if data is not None and not data.empty:
                        print(f"[stockstats] TickFlow success: {len(data)} rows")
                except Exception as e:
                    errors.append(f"TickFlow: {str(e)[:80]}")
                    print(f"[stockstats] TickFlow failed: {str(e)[:80]}")

                # 2. Try AKShare
                if data is None:
                    try:
                        print(f"[stockstats] Trying AKShare for {symbol}...")
                        data = _fetch_data_akshare(symbol, start_date, end_date)
                        if data is not None and not data.empty:
                            print(f"[stockstats] AKShare success: {len(data)} rows")
                    except Exception as e:
                        errors.append(f"AKShare: {str(e)[:80]}")
                        print(f"[stockstats] AKShare failed: {str(e)[:80]}")

                # 3. Fallback to BaoStock
                if data is None:
                    try:
                        print(f"[stockstats] Trying BaoStock for {symbol}...")
                        data = _fetch_data_baostock(symbol, start_date, end_date)
                        if data is not None and not data.empty:
                            print(f"[stockstats] BaoStock success: {len(data)} rows")
                    except Exception as e:
                        errors.append(f"BaoStock: {str(e)[:80]}")
                        print(f"[stockstats] BaoStock failed: {str(e)[:80]}")

                if data is None or data.empty:
                    raise Exception(f"All data sources failed for {symbol}: {'; '.join(errors)}")

                # Save successful data to cache
                data.to_csv(data_file, index=False)
                print(f"[stockstats] Saved {len(data)} rows to cache: {data_file}")

            df = wrap(data)
            # Ensure Date column is datetime before formatting
            if not pd.api.types.is_datetime64_any_dtype(df["Date"]):
                df["Date"] = pd.to_datetime(df["Date"])
            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
            # curr_date may already be a string (annotation says str), ensure string
            curr_date_str = str(curr_date)[:10]

        df[indicator]  # trigger stockstats to calculate the indicator
        matching_rows = df[df["Date"].str.startswith(curr_date_str)]

        if not matching_rows.empty:
            indicator_value = matching_rows[indicator].values[0]
            return indicator_value
        else:
            return "N/A: Not a trading day (weekend or holiday)"
