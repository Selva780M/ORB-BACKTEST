import os
import time as pytime
from datetime import time

import numpy as np
import pandas as pd
import streamlit as st


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="TradingView ORB Backtest",
    page_icon="📈",
    layout="wide"
)


# ============================================================
# IMPORTANT
# ============================================================
#
# Your TvDatafeed and Interval classes must already exist.
#
# Example:
#
# from tvDatafeed import TvDatafeed, Interval
#
# OR keep your custom TvDatafeed class above this code.
#
# ============================================================


# ============================================================
# NIFTY STOCK LIST
# ============================================================

NIFTY_SYMBOLS = [
    "ADANIENT",
    "ADANIPORTS",
    "APOLLOHOSP",
    "ASIANPAINT",
    "AXISBANK",
    "BAJAJ-AUTO",
    "BAJFINANCE",
    "BAJAJFINSV",
    "BEL",
    "BHARTIARTL",
    "CIPLA",
    "COALINDIA",
    "DRREDDY",
    "EICHERMOT",
    "ETERNAL",
    "GRASIM",
    "HCLTECH",
    "HDFCBANK",
    "HDFCLIFE",
    "HEROMOTOCO",
    "HINDALCO",
    "HINDUNILVR",
    "ICICIBANK",
    "INDUSINDBK",
    "INFY",
    "ITC",
    "JIOFIN",
    "JSWSTEEL",
    "KOTAKBANK",
    "LT",
    "M&M",
    "MARUTI",
    "MAXHEALTH",
    "NESTLEIND",
    "NTPC",
    "ONGC",
    "POWERGRID",
    "RELIANCE",
    "SBILIFE",
    "SBIN",
    "SHRIRAMFIN",
    "SUNPHARMA",
    "TATACONSUM",
    "TATAMOTORS",
    "TATASTEEL",
    "TCS",
    "TECHM",
    "TITAN",
    "TRENT",
    "ULTRACEMCO",
    "WIPRO",
]


# ============================================================
# SECRETS / LOGIN
# ============================================================

def get_secret(name):

    value = os.getenv(name)

    if value:
        return value

    try:
        return st.secrets[name]
    except Exception:
        return None


def create_tv_connection():

    tv_token = get_secret("TV_TOKEN")
    tv_username = get_secret("TV_USERNAME")
    tv_password = get_secret("TV_PASSWORD")

    try:

        # Token login
        if tv_token:

            st.info("🔐 Connecting to TradingView using token...")

            # IMPORTANT:
            # Pass token during construction.
            # Do NOT do tv.token = token after creating object.
            tv = TvDatafeed(
                token=tv_token
            )

            return tv

        # Username/password login
        if tv_username and tv_password:

            st.info("🔐 Connecting to TradingView using username/password...")

            tv = TvDatafeed(
                username=tv_username,
                password=tv_password
            )

            return tv

        raise RuntimeError(
            "TradingView credentials not found. "
            "Set TV_TOKEN or TV_USERNAME + TV_PASSWORD."
        )

    except Exception as e:

        raise RuntimeError(
            f"TradingView connection failed: {e}"
        )


# ============================================================
# NORMALIZE TRADINGVIEW DATA
# ============================================================

def normalize_tv_data(df, symbol):

    if df is None:
        return None

    if df.empty:
        return None

    df = df.copy()

    # --------------------------------------------------------
    # Reset index
    # --------------------------------------------------------

    if isinstance(df.index, pd.DatetimeIndex):

        df = df.reset_index()

    # --------------------------------------------------------
    # Rename columns
    # --------------------------------------------------------

    rename_map = {}

    for col in df.columns:

        c = str(col).strip().lower()

        if c in ["datetime", "date", "time", "index"]:
            rename_map[col] = "datetime"

        elif c == "open":
            rename_map[col] = "open"

        elif c == "high":
            rename_map[col] = "high"

        elif c == "low":
            rename_map[col] = "low"

        elif c == "close":
            rename_map[col] = "close"

        elif c == "volume":
            rename_map[col] = "volume"

        elif c == "symbol":
            rename_map[col] = "symbol"

    df = df.rename(columns=rename_map)

    # --------------------------------------------------------
    # Check required columns
    # --------------------------------------------------------

    required = [
        "datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    missing = [
        x for x in required
        if x not in df.columns
    ]

    if missing:

        raise ValueError(
            f"{symbol}: Missing columns {missing}. "
            f"Available: {list(df.columns)}"
        )

    # --------------------------------------------------------
    # Datetime
    # --------------------------------------------------------

    df["datetime"] = pd.to_datetime(
        df["datetime"],
        errors="coerce"
    )

    df = df.dropna(
        subset=[
            "datetime",
            "open",
            "high",
            "low",
            "close"
        ]
    )

    # --------------------------------------------------------
    # Numeric columns
    # --------------------------------------------------------

    numeric_cols = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    for col in numeric_cols:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    df = df.dropna(
        subset=[
            "open",
            "high",
            "low",
            "close"
        ]
    )

    # --------------------------------------------------------
    # Symbol
    # --------------------------------------------------------

    df["symbol"] = symbol

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    df = df.sort_values(
        "datetime"
    ).reset_index(drop=True)

    # --------------------------------------------------------
    # Required order
    # --------------------------------------------------------

    df = df[
        [
            "datetime",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "symbol",
        ]
    ]

    return df


# ============================================================
# FETCH ONE STOCK
# ============================================================

def fetch_one_stock(
    tv,
    symbol,
    n_bars=5000,
    retries=2
):

    last_error = None

    for attempt in range(retries + 1):

        try:

            raw = tv.get_hist(
                symbol=symbol,
                exchange="NSE",
                interval=Interval.in_5_minute,
                n_bars=n_bars,
                fut_contract=None,
                extended_session=False,
            )

            if raw is None:
                raise ValueError(
                    "TradingView returned None"
                )

            if raw.empty:
                raise ValueError(
                    "TradingView returned empty data"
                )

            df = normalize_tv_data(
                raw,
                symbol
            )

            if df is None or df.empty:
                raise ValueError(
                    "No usable OHLC data"
                )

            return df

        except Exception as e:

            last_error = e

            if attempt < retries:

                pytime.sleep(1)

    raise RuntimeError(
        f"{symbol}: {last_error}"
    )


# ============================================================
# FETCH ALL STOCKS
# ============================================================

def fetch_all_stocks(
    tv,
    symbols,
    n_bars=5000,
    delay=0.25
):

    data = {}

    failed = []

    progress = st.progress(
        0,
        text="Starting TradingView download..."
    )

    total = len(symbols)

    status_box = st.empty()

    for i, symbol in enumerate(symbols):

        status_box.info(
            f"📡 Fetching {symbol} "
            f"({i + 1}/{total})"
        )

        try:

            df = fetch_one_stock(
                tv=tv,
                symbol=symbol,
                n_bars=n_bars,
                retries=2
            )

            if df is not None and not df.empty:

                data[symbol] = df

        except Exception as e:

            failed.append(
                {
                    "Symbol": symbol,
                    "Error": str(e)
                }
            )

        progress.progress(
            (i + 1) / total,
            text=(
                f"Fetched {i + 1}/{total} "
                f"| Success: {len(data)} "
                f"| Failed: {len(failed)}"
            )
        )

        pytime.sleep(delay)

    status_box.empty()

    return data, failed


# ============================================================
# INDICATORS
# ============================================================

def rma(
    s,
    length
):

    return (
        s
        .ewm(
            alpha=1 / length,
            adjust=False,
            min_periods=length
        )
        .mean()
    )


def atr(
    df,
    length=14
):

    prev_close = df["close"].shift(1)

    tr1 = (
        df["high"]
        - df["low"]
    )

    tr2 = (
        df["high"]
        - prev_close
    ).abs()

    tr3 = (
        df["low"]
        - prev_close
    ).abs()

    tr = pd.concat(
        [
            tr1,
            tr2,
            tr3
        ],
        axis=1
    ).max(axis=1)

    return rma(
        tr,
        length
    )


def rsi(
    close,
    length=14
):

    delta = close.diff()

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    avg_gain = rma(
        gain,
        length
    )

    avg_loss = rma(
        loss,
        length
    )

    rs = avg_gain / avg_loss.replace(
        0,
        np.nan
    )

    result = (
        100
        - (
            100
            / (
                1 + rs
            )
        )
    )

    return result


def adx(
    df,
    length=9
):

    high = df["high"]
    low = df["low"]

    up_move = (
        high
        - high.shift(1)
    )

    down_move = (
        low.shift(1)
        - low
    )

    plus_dm = pd.Series(
        np.where(
            (
                (up_move > down_move)
                & (up_move > 0)
            ),
            up_move,
            0
        ),
        index=df.index
    )

    minus_dm = pd.Series(
        np.where(
            (
                (down_move > up_move)
                & (down_move > 0)
            ),
            down_move,
            0
        ),
        index=df.index
    )

    prev_close = df["close"].shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1
    ).max(axis=1)

    atr_value = rma(
        tr,
        length
    )

    plus_di = (
        100
        * rma(
            plus_dm,
            length
        )
        / atr_value.replace(
            0,
            np.nan
        )
    )

    minus_di = (
        100
        * rma(
            minus_dm,
            length
        )
        / atr_value.replace(
            0,
            np.nan
        )
    )

    dx = (
        100
        * (
            (plus_di - minus_di).abs()
            /
            (
                plus_di
                + minus_di
            ).replace(
                0,
                np.nan
            )
        )
    )

    return rma(
        dx,
        length
    )


# ============================================================
# SESSION VWAP
# ============================================================

def session_vwap(df):

    temp = df.copy()

    typical_price = (
        temp["high"]
        + temp["low"]
        + temp["close"]
    ) / 3

    temp["_date"] = (
        temp["datetime"]
        .dt.date
    )

    pv = (
        typical_price
        * temp["volume"]
    )

    cumulative_pv = (
        pv.groupby(
            temp["_date"]
        )
        .cumsum()
    )

    cumulative_volume = (
        temp["volume"]
        .groupby(
            temp["_date"]
        )
        .cumsum()
    )

    result = (
        cumulative_pv
        /
        cumulative_volume.replace(
            0,
            np.nan
        )
    )

    return result


# ============================================================
# PREPARE DATA
# ============================================================

def prepare(
    df,
    orb_minutes,
    rsi_len,
    adx_len,
    atr_len
):

    df = df.copy()

    df = df.sort_values(
        "datetime"
    ).reset_index(
        drop=True
    )

    # --------------------------------------------------------
    # Indicators
    # --------------------------------------------------------

    df["atr"] = atr(
        df,
        atr_len
    )

    df["rsi"] = rsi(
        df["close"],
        rsi_len
    )

    df["adx"] = adx(
        df,
        adx_len
    )

    df["vwap"] = session_vwap(
        df
    )

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    df["vol_sma"] = (
        df["volume"]
        .rolling(
            20,
            min_periods=20
        )
        .mean()
    )

    df["recent_vol_sma"] = (
        df["volume"]
        .rolling(
            5,
            min_periods=5
        )
        .mean()
    )

    # --------------------------------------------------------
    # Previous close
    # --------------------------------------------------------

    df["prev_close"] = (
        df["close"]
        .shift(1)
    )

    # --------------------------------------------------------
    # Candle body
    # --------------------------------------------------------

    candle_range = (
        df["high"]
        - df["low"]
    )

    df["body_strength"] = (
        (
            df["close"]
            - df["open"]
        ).abs()
        /
        candle_range.replace(
            0,
            np.nan
        )
    )

    # --------------------------------------------------------
    # Bull / Bear
    # --------------------------------------------------------

    df["bull"] = (
        df["close"]
        > df["open"]
    )

    df["bear"] = (
        df["close"]
        < df["open"]
    )

    return df


# ============================================================
# BROKERAGE
# ============================================================

def broker_charge(
    entry,
    exit_price,
    qty,
    brokerage
):

    trade_value = (
        float(entry)
        +
        float(exit_price)
    ) * float(qty)

    # Fixed brokerage per completed trade
    brk = float(brokerage)

    return brk


# ============================================================
# BACKTEST
# ============================================================

def run_backtest(
    df,
    p
):

    df = df.copy()

    trades = []

    equity_curve = []

    position = None

    current_day = None

    orb_high = None
    orb_low = None
    orb_locked = False

    daily_pnl = 0.0
    daily_trades = 0

    equity = float(
        p["initial_capital"]
    )

    # --------------------------------------------------------
    # Loop candles
    # --------------------------------------------------------

    for i in range(
        len(df)
    ):

        row = df.iloc[i]

        ts = row["datetime"]

        day = ts.date()

        tm = ts.time()

        # ----------------------------------------------------
        # New day
        # ----------------------------------------------------

        if current_day != day:

            # Previous position should normally
            # already have been squared off.

            position = None

            current_day = day

            orb_high = None
            orb_low = None

            orb_locked = False

            daily_pnl = 0.0

            daily_trades = 0

        # ----------------------------------------------------
        # ORB BUILD
        # ----------------------------------------------------

        orb_start = p["orb_start"]

        orb_end = p["orb_end"]

        if (
            tm >= orb_start
            and tm < orb_end
        ):

            if orb_high is None:

                orb_high = row["high"]
                orb_low = row["low"]

            else:

                orb_high = max(
                    orb_high,
                    row["high"]
                )

                orb_low = min(
                    orb_low,
                    row["low"]
                )

            continue

        # ----------------------------------------------------
        # Lock ORB
        # ----------------------------------------------------

        if (
            not orb_locked
            and tm >= orb_end
            and orb_high is not None
        ):

            orb_locked = True

        # ----------------------------------------------------
        # Manage open position
        # ----------------------------------------------------

        if position is not None:

            side = position["side"]

            entry = position["entry"]

            sl = position["sl"]

            tp = position["tp"]

            qty = position["qty"]

            exit_price = None
            exit_reason = None

            # ------------------------------------------------
            # LONG
            # ------------------------------------------------

            if side == "LONG":

                hit_sl = (
                    row["low"]
                    <= sl
                )

                hit_tp = (
                    row["high"]
                    >= tp
                )

                if (
                    hit_sl
                    and hit_tp
                ):

                    # Conservative assumption
                    exit_price = sl
                    exit_reason = "SL"

                elif hit_sl:

                    exit_price = sl
                    exit_reason = "SL"

                elif hit_tp:

                    exit_price = tp
                    exit_reason = "TP"

            # ------------------------------------------------
            # SHORT
            # ------------------------------------------------

            elif side == "SHORT":

                hit_sl = (
                    row["high"]
                    >= sl
                )

                hit_tp = (
                    row["low"]
                    <= tp
                )

                if (
                    hit_sl
                    and hit_tp
                ):

                    exit_price = sl
                    exit_reason = "SL"

                elif hit_sl:

                    exit_price = sl
                    exit_reason = "SL"

                elif hit_tp:

                    exit_price = tp
                    exit_reason = "TP"

            # ------------------------------------------------
            # Square off
            # ------------------------------------------------

            if (
                exit_price is None
                and tm >= p["squareoff_time"]
            ):

                exit_price = row["close"]

                exit_reason = "SquareOff"

            # ------------------------------------------------
            # Exit
            # ------------------------------------------------

            if exit_price is not None:

                if side == "LONG":

                    gross_pnl = (
                        exit_price
                        - entry
                    ) * qty

                else:

                    gross_pnl = (
                        entry
                        - exit_price
                    ) * qty

                brokerage = broker_charge(
                    entry,
                    exit_price,
                    qty,
                    p["brokerage"]
                )

                net_pnl = (
                    gross_pnl
                    - brokerage
                )

                equity += net_pnl

                daily_pnl += net_pnl

                trades.append(
                    {
                        "Date": day,
                        "Symbol": row.get(
                            "symbol",
                            ""
                        ),
                        "Side": side,
                        "Entry Time": position[
                            "entry_time"
                        ],
                        "Entry": entry,
                        "SL": sl,
                        "TP": tp,
                        "Exit Time": ts,
                        "Exit": exit_price,
                        "Reason": exit_reason,
                        "Qty": qty,
                        "Gross P&L": gross_pnl,
                        "Brokerage": brokerage,
                        "Net P&L": net_pnl,
                        "Equity": equity,
                    }
                )

                position = None

                # ------------------------------------------------
                # Do not immediately re-enter on same candle
                # ------------------------------------------------

                continue

        # ----------------------------------------------------
        # Entry conditions
        # ----------------------------------------------------

        if not orb_locked:
            continue

        if orb_high is None or orb_low is None:
            continue

        # ----------------------------------------------------
        # Entry time
        # ----------------------------------------------------

        if tm < p["entry_start"]:
            continue

        if tm > p["entry_end"]:
            continue

        # ----------------------------------------------------
        # Daily loss lock
        # ----------------------------------------------------

        if (
            daily_pnl
            <= -abs(
                p["daily_max_loss"]
            )
        ):

            continue

        # ----------------------------------------------------
        # Max trades
        # ----------------------------------------------------

        if (
            daily_trades
            >= p["max_trades_day"]
        ):

            continue

        # ----------------------------------------------------
        # Continuous / non-continuous
        # ----------------------------------------------------

        if (
            not p["continuous"]
            and daily_trades > 0
        ):

            continue

        # ----------------------------------------------------
        # Indicators available?
        # ----------------------------------------------------

        if pd.isna(row["atr"]):
            continue

        if pd.isna(row["rsi"]):
            continue

        if pd.isna(row["adx"]):
            continue

        if pd.isna(row["vwap"]):
            continue

        # ----------------------------------------------------
        # ORB range
        # ----------------------------------------------------

        orb_range = (
            orb_high
            - orb_low
        )

        if orb_range <= 0:
            continue

        # ----------------------------------------------------
        # ORB ATR filter
        # ----------------------------------------------------

        orb_atr_ratio = (
            orb_range
            /
            row["atr"]
        )

        if (
            orb_atr_ratio
            < p["orb_min_atr"]
        ):

            continue

        if (
            orb_atr_ratio
            > p["orb_max_atr"]
        ):

            continue

        # ----------------------------------------------------
        # ADX
        # ----------------------------------------------------

        if (
            row["adx"]
            < p["adx_min"]
        ):

            continue

        # ----------------------------------------------------
        # ADX rising
        # ----------------------------------------------------

        if p["adx_rising"]:

            if i == 0:
                continue

            prev_adx = df.iloc[
                i - 1
            ]["adx"]

            if pd.isna(prev_adx):
                continue

            if (
                row["adx"]
                <= prev_adx
            ):

                continue

        # ----------------------------------------------------
        # Volume
        # ----------------------------------------------------

        if (
            p["volume_multiplier"]
            > 0
        ):

            if pd.isna(
                row["vol_sma"]
            ):

                continue

            if (
                row["volume"]
                <
                row["vol_sma"]
                * p["volume_multiplier"]
            ):

                continue

        # ----------------------------------------------------
        # Recent volume
        # ----------------------------------------------------

        if (
            p["recent_volume_multiplier"]
            > 0
        ):

            if pd.isna(
                row["recent_vol_sma"]
            ):

                continue

            if (
                row["volume"]
                <
                row["recent_vol_sma"]
                * p["recent_volume_multiplier"]
            ):

                continue

        # ----------------------------------------------------
        # Body strength
        # ----------------------------------------------------

        if (
            row["body_strength"]
            < p["body_strength"]
        ):

            continue

        # ----------------------------------------------------
        # LONG SIGNAL
        # ----------------------------------------------------

        long_signal = False

        if p["allow_long"]:

            long_signal = (
                row["close"]
                > orb_high
                and
                row["close"]
                > row["open"]
                and
                row["rsi"]
                >= p["rsi_long"]
                and
                row["close"]
                > row["vwap"]
            )

        # ----------------------------------------------------
        # SHORT SIGNAL
        # ----------------------------------------------------

        short_signal = False

        if p["allow_short"]:

            short_signal = (
                row["close"]
                < orb_low
                and
                row["close"]
                < row["open"]
                and
                row["rsi"]
                <= p["rsi_short"]
                and
                row["close"]
                < row["vwap"]
            )

        # ----------------------------------------------------
        # LONG ENTRY
        # ----------------------------------------------------

        if long_signal:

            entry = float(
                row["close"]
            )

            atr_value = float(
                row["atr"]
            )

            sl = min(
                orb_low,
                entry
                - (
                    atr_value
                    * p["sl_atr"]
                )
            )

            risk = (
                entry
                - sl
            )

            if risk <= 0:
                continue

            tp = (
                entry
                + (
                    risk
                    * p["rr"]
                )
            )

            position = {
                "side": "LONG",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "qty": p["qty"],
                "entry_time": ts,
            }

            daily_trades += 1

            continue

        # ----------------------------------------------------
        # SHORT ENTRY
        # ----------------------------------------------------

        if short_signal:

            entry = float(
                row["close"]
            )

            atr_value = float(
                row["atr"]
            )

            sl = max(
                orb_high,
                entry
                + (
                    atr_value
                    * p["sl_atr"]
                )
            )

            risk = (
                sl
                - entry
            )

            if risk <= 0:
                continue

            tp = (
                entry
                - (
                    risk
                    * p["rr"]
                )
            )

            position = {
                "side": "SHORT",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "qty": p["qty"],
                "entry_time": ts,
            }

            daily_trades += 1

            continue

    # ========================================================
    # DATAFRAME
    # ========================================================

    trades_df = pd.DataFrame(
        trades
    )

    if trades_df.empty:

        return (
            trades_df,
            pd.DataFrame()
        )

    # --------------------------------------------------------
    # Equity curve
    # --------------------------------------------------------

    equity_curve = trades_df[
        [
            "Exit Time",
            "Equity"
        ]
    ].copy()

    equity_curve = (
        equity_curve
        .rename(
            columns={
                "Exit Time": "datetime",
                "Equity": "equity"
            }
        )
    )

    return (
        trades_df,
        equity_curve
    )


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(
    trades
):

    if trades is None or trades.empty:

        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "gross_profit": 0,
            "gross_loss": 0,
            "net_pnl": 0,
            "profit_factor": 0,
            "max_drawdown": 0,
        }

    pnl = pd.to_numeric(
        trades["Net P&L"],
        errors="coerce"
    ).fillna(0)

    wins = (
        pnl > 0
    ).sum()

    losses = (
        pnl < 0
    ).sum()

    total_trades = len(
        pnl
    )

    win_rate = (
        wins
        /
        total_trades
        * 100
        if total_trades > 0
        else 0
    )

    gross_profit = pnl[
        pnl > 0
    ].sum()

    gross_loss = abs(
        pnl[
            pnl < 0
        ].sum()
    )

    net_pnl = pnl.sum()

    if gross_loss > 0:

        profit_factor = (
            gross_profit
            /
            gross_loss
        )

    else:

        profit_factor = np.inf

    # --------------------------------------------------------
    # Drawdown
    # --------------------------------------------------------

    equity = (
        pnl.cumsum()
    )

    running_high = (
        equity.cummax()
    )

    drawdown = (
        equity
        - running_high
    )

    max_drawdown = (
        drawdown.min()
    )

    return {
        "trades": int(total_trades),
        "wins": int(wins),
        "losses": int(losses),
        "win_rate": float(win_rate),
        "gross_profit": float(gross_profit),
        "gross_loss": float(gross_loss),
        "net_pnl": float(net_pnl),
        "profit_factor": float(profit_factor),
        "max_drawdown": float(max_drawdown),
    }


# ============================================================
# PORTFOLIO BACKTEST
# ============================================================

def run_all_stocks(
    market_data,
    p
):

    all_trades = []

    stock_summary = []

    total = len(
        market_data
    )

    progress = st.progress(
        0,
        text="Running backtest..."
    )

    for idx, (
        symbol,
        raw_df
    ) in enumerate(
        market_data.items()
    ):

        try:

            prepared = prepare(
                raw_df,
                p["orb_minutes"],
                p["rsi_len"],
                p["adx_len"],
                p["atr_len"],
            )

            trades, equity = run_backtest(
                prepared,
                p
            )

            if (
                trades is not None
                and not trades.empty
            ):

                trades = trades.copy()

                trades["Symbol"] = symbol

                all_trades.append(
                    trades
                )

            metrics = calculate_metrics(
                trades
            )

            stock_summary.append(
                {
                    "Symbol": symbol,
                    "Trades": metrics[
                        "trades"
                    ],
                    "Wins": metrics[
                        "wins"
                    ],
                    "Losses": metrics[
                        "losses"
                    ],
                    "Win Rate %": round(
                        metrics[
                            "win_rate"
                        ],
                        2
                    ),
                    "Net P&L": round(
                        metrics[
                            "net_pnl"
                        ],
                        2
                    ),
                    "Profit Factor": round(
                        metrics[
                            "profit_factor"
                        ],
                        2
                    )
                    if np.isfinite(
                        metrics[
                            "profit_factor"
                        ]
                    )
                    else np.inf,
                    "Max DD": round(
                        metrics[
                            "max_drawdown"
                        ],
                        2
                    ),
                }
            )

        except Exception as e:

            stock_summary.append(
                {
                    "Symbol": symbol,
                    "Trades": 0,
                    "Wins": 0,
                    "Losses": 0,
                    "Win Rate %": 0,
                    "Net P&L": 0,
                    "Profit Factor": 0,
                    "Max DD": 0,
                    "Error": str(e),
                }
            )

        progress.progress(
            (idx + 1) / total,
            text=(
                f"Backtest "
                f"{idx + 1}/{total}"
            )
        )

    progress.empty()

    if all_trades:

        combined_trades = pd.concat(
            all_trades,
            ignore_index=True
        )

        if "Symbol" not in combined_trades.columns:

            combined_trades["Symbol"] = ""

        combined_trades = combined_trades.sort_values(
            "Exit Time"
        ).reset_index(
            drop=True
        )

    else:

        combined_trades = pd.DataFrame()

    summary_df = pd.DataFrame(
        stock_summary
    )

    return (
        combined_trades,
        summary_df
    )


# ============================================================
# SESSION STATE
# ============================================================

if "market_data" not in st.session_state:

    st.session_state.market_data = {}

if "failed_symbols" not in st.session_state:

    st.session_state.failed_symbols = []


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title(
    "📡 TradingView Data"
)

st.sidebar.caption(
    "5-minute NSE market data"
)

# ------------------------------------------------------------
# Bars
# ------------------------------------------------------------

n_bars = st.sidebar.number_input(
    "Bars per stock",
    min_value=500,
    max_value=5000,
    value=5000,
    step=500
)

# ------------------------------------------------------------
# Delay
# ------------------------------------------------------------

fetch_delay = st.sidebar.number_input(
    "Fetch delay (seconds)",
    min_value=0.0,
    max_value=5.0,
    value=0.25,
    step=0.05
)

st.sidebar.write(
    f"Stocks: **{len(NIFTY_SYMBOLS)}**"
)

# ------------------------------------------------------------
# Fetch button
# ------------------------------------------------------------

if st.sidebar.button(
    "📡 FETCH TRADINGVIEW DATA",
    type="primary",
    use_container_width=True
):

    try:

        with st.spinner(
            "Connecting to TradingView..."
        ):

            tv = create_tv_connection()

        market_data, failed = fetch_all_stocks(
            tv=tv,
            symbols=NIFTY_SYMBOLS,
            n_bars=int(n_bars),
            delay=float(fetch_delay)
        )

        st.session_state.market_data = (
            market_data
        )

        st.session_state.failed_symbols = (
            failed
        )

        st.success(
            f"✅ Download complete. "
            f"{len(market_data)} stocks loaded."
        )

    except Exception as e:

        st.error(
            f"❌ Fetch failed: {e}"
        )


# ------------------------------------------------------------
# Clear
# ------------------------------------------------------------

if st.sidebar.button(
    "🗑️ CLEAR DATA",
    use_container_width=True
):

    st.session_state.market_data = {}

    st.session_state.failed_symbols = []

    st.rerun()


# ============================================================
# MAIN TITLE
# ============================================================

st.title(
    "📈 TradingView 5-Min ORB Backtest"
)

st.caption(
    "TradingView → 5 Minute NSE Data → ORB Strategy → Backtest"
)


# ============================================================
# DATA STATUS
# ============================================================

market_data = (
    st.session_state.market_data
)

if not market_data:

    st.info(
        "👈 Click **FETCH TRADINGVIEW DATA** "
        "from the sidebar first."
    )

    st.markdown(
        """
