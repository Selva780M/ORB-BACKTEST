import os
import time as pytime
from datetime import time

import numpy as np
import pandas as pd
import streamlit as st

import tvDatafeed
from tvDatafeed import TvDatafeed, Interval


st.set_page_config(
    page_title="TradingView ORB Backtest",
    page_icon="📈",
    layout="wide"
)


# ============================================================
# NIFTY STOCKS
# ============================================================

NIFTY_SYMBOLS = [
    "ADANIENT",
    "ADANIPORTS",
    "APOLLOHOSP",
]


# ============================================================
# SECRETS
# ============================================================

def get_secret(name):

    value = os.getenv(name)

    if value:
        return value

    try:
        value = st.secrets[name]

        if value:
            return value

    except Exception:
        pass

    return None


# ============================================================
# TRADINGVIEW CONNECTION
# ============================================================

@st.cache_resource
def create_tv_connection():

    token = get_secret("TV_TOKEN")
    username = get_secret("TV_USERNAME")
    password = get_secret("TV_PASSWORD")

    # --------------------------------------------------------
    # SHOW WHICH tvDatafeed.py IS ACTUALLY LOADED
    # --------------------------------------------------------

    try:
        st.sidebar.caption(
            f"📁 tvDatafeed: {tvDatafeed.__file__}"
        )
    except Exception:
        pass

    # --------------------------------------------------------
    # TOKEN LOGIN
    # --------------------------------------------------------

    if token:

        st.sidebar.success(
            "🔐 TradingView: TOKEN"
        )

        return TvDatafeed(
            token=token
        )

    # --------------------------------------------------------
    # USERNAME / PASSWORD
    # --------------------------------------------------------

    if username and password:

        st.sidebar.success(
            "🔐 TradingView: USERNAME/PASSWORD"
        )

        return TvDatafeed(
            username=username,
            password=password
        )

    # --------------------------------------------------------
    # ANONYMOUS CONNECTION
    # --------------------------------------------------------

    st.sidebar.warning(
        "⚠️ TradingView credentials not found."
    )

    st.sidebar.info(
        "Using anonymous TradingView connection."
    )

    return TvDatafeed()


# ============================================================
# NORMALIZE TRADINGVIEW DATA
# ============================================================

def normalize_tv_data(
    df,
    symbol
):

    if df is None:
        return None

    if not isinstance(df, pd.DataFrame):
        raise ValueError(
            f"{symbol}: TradingView returned "
            f"{type(df).__name__}, not DataFrame"
        )

    if df.empty:
        return None

    df = df.copy()

    # --------------------------------------------------------
    # RESET DATETIME INDEX
    # --------------------------------------------------------

    if isinstance(
        df.index,
        pd.DatetimeIndex
    ):

        df = df.reset_index()

    # --------------------------------------------------------
    # RENAME COLUMNS
    # --------------------------------------------------------

    rename_map = {}

    for col in df.columns:

        c = str(col).strip().lower()

        if c in [
            "datetime",
            "date",
            "time",
            "timestamp",
            "index"
        ]:

            rename_map[col] = "datetime"

        elif c == "open":

            rename_map[col] = "open"

        elif c == "high":

            rename_map[col] = "high"

        elif c == "low":

            rename_map[col] = "low"

        elif c == "close":

            rename_map[col] = "close"

        elif c in [
            "volume",
            "vol"
        ]:

            rename_map[col] = "volume"

    df = df.rename(
        columns=rename_map
    )

    # --------------------------------------------------------
    # REQUIRED COLUMNS
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
        col
        for col in required
        if col not in df.columns
    ]

    if missing:

        available = list(df.columns)

        raise ValueError(
            f"{symbol}: missing columns "
            f"{missing}. "
            f"Available columns: {available}"
        )

    # --------------------------------------------------------
    # DATETIME
    # --------------------------------------------------------

    df["datetime"] = pd.to_datetime(
        df["datetime"],
        errors="coerce"
    )

    # --------------------------------------------------------
    # NUMERIC
    # --------------------------------------------------------

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    for col in numeric_columns:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    # --------------------------------------------------------
    # DROP BAD ROWS
    # --------------------------------------------------------

    df = df.dropna(
        subset=[
            "datetime",
            "open",
            "high",
            "low",
            "close"
        ]
    )

    if df.empty:

        raise ValueError(
            f"{symbol}: all rows became invalid "
            f"after datetime/numeric conversion"
        )

    # --------------------------------------------------------
    # SYMBOL
    # --------------------------------------------------------

    df["symbol"] = symbol

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    df = (
        df
        .sort_values(
            "datetime"
        )
        .drop_duplicates(
            subset=["datetime"],
            keep="last"
        )
        .reset_index(
            drop=True
        )
    )

    # --------------------------------------------------------
    # FINAL DATAFRAME
    # --------------------------------------------------------

    return df[
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

    for attempt in range(
        retries + 1
    ):

        try:

            # ------------------------------------------------
            # IMPORTANT:
            # NSE CASH STOCK => fut_contract=None
            # ------------------------------------------------

            raw = tv.get_hist(
                symbol=symbol,
                exchange="NSE",
                interval=Interval.in_5_minute,
                n_bars=int(n_bars),
                fut_contract=None,
                extended_session=False,
            )

            # ------------------------------------------------
            # DEBUG
            # ------------------------------------------------

            if raw is None:

                raise ValueError(
                    f"{symbol}: TradingView returned None"
                )

            if not isinstance(
                raw,
                pd.DataFrame
            ):

                raise ValueError(
                    f"{symbol}: invalid response type: "
                    f"{type(raw).__name__}"
                )

            if raw.empty:

                raise ValueError(
                    f"{symbol}: TradingView returned "
                    f"an empty DataFrame"
                )

            # ------------------------------------------------
            # NORMALIZE
            # ------------------------------------------------

            df = normalize_tv_data(
                raw,
                symbol
            )

            if (
                df is None
                or df.empty
            ):

                raise ValueError(
                    f"{symbol}: No candle data after normalization"
                )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            return df

        except Exception as e:

            last_error = e

            if attempt < retries:

                pytime.sleep(1)

    # --------------------------------------------------------
    # FINAL ERROR
    # --------------------------------------------------------

    raise RuntimeError(
        f"{symbol}: {repr(last_error)}"
    )


# ============================================================
# FETCH ALL STOCKS
# ============================================================

def fetch_all_stocks(
    tv,
    symbols,
    n_bars,
    delay
):

    data = {}

    failed = []

    # --------------------------------------------------------
    # PROGRESS
    # --------------------------------------------------------

    progress = st.progress(
        0
    )

    status = st.empty()

    total = len(symbols)

    if total == 0:

        status.error(
            "❌ No symbols found."
        )

        return (
            data,
            failed
        )

    # --------------------------------------------------------
    # LOOP STOCKS
    # --------------------------------------------------------

    for i, symbol in enumerate(
        symbols
    ):

        status.info(
            f"📡 Fetching "
            f"**{symbol}** "
            f"({i + 1}/{total})"
        )

        try:

            df = fetch_one_stock(
                tv=tv,
                symbol=symbol,
                n_bars=int(n_bars),
                retries=2
            )

            if (
                df is None
                or df.empty
            ):

                raise ValueError(
                    "Empty dataframe"
                )

            data[symbol] = df

            st.toast(
                f"✅ {symbol}: "
                f"{len(df):,} candles",
                icon="📈"
            )

        except Exception as e:

            error_text = str(e)

            failed.append(
                {
                    "Symbol": symbol,
                    "Error": error_text
                }
            )

            # ------------------------------------------------
            # SHOW ERROR IMMEDIATELY
            # ------------------------------------------------

            st.warning(
                f"⚠️ {symbol} failed: "
                f"{error_text}"
            )

        # ----------------------------------------------------
        # PROGRESS
        # ----------------------------------------------------

        progress.progress(
            int(
                ((i + 1) / total) * 100
            )
        )

        # ----------------------------------------------------
        # DELAY
        # ----------------------------------------------------

        if delay > 0:

            pytime.sleep(
                float(delay)
            )

    # --------------------------------------------------------
    # CLEANUP
    # --------------------------------------------------------

    progress.empty()

    status.empty()

    return (
        data,
        failed
    )


# ============================================================
# DISPLAY FETCH RESULT
# ============================================================

def display_fetch_result(
    data,
    failed
):

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    if data:

        st.success(
            f"✅ Loaded {len(data)} stocks."
        )

        summary = []

        for symbol, df in data.items():

            summary.append(
                {
                    "Symbol": symbol,
                    "Candles": len(df),
                    "Start": df["datetime"].min(),
                    "End": df["datetime"].max(),
                }
            )

        summary_df = pd.DataFrame(
            summary
        )

        st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.error(
            "❌ Loaded 0 stocks."
        )

    # --------------------------------------------------------
    # FAILED SYMBOLS
    # --------------------------------------------------------

    if failed:

        with st.expander(
            f"❌ Failed Symbols ({len(failed)})",
            expanded=True
        ):

            failed_df = pd.DataFrame(
                failed
            )

            st.dataframe(
                failed_df,
                use_container_width=True,
                hide_index=True
            )


# ============================================================
# TEST SINGLE SYMBOL
# ============================================================

def test_tradingview_symbol(
    tv,
    symbol="SBIN"
):

    st.subheader(
        f"🧪 TradingView Test — {symbol}"
    )

    try:

        df = fetch_one_stock(
            tv=tv,
            symbol=symbol,
            n_bars=500,
            retries=1
        )

        st.success(
            f"✅ {symbol} working — "
            f"{len(df):,} candles received."
        )

        st.write(
            "Columns:",
            list(df.columns)
        )

        st.dataframe(
            df.tail(20),
            use_container_width=True,
            hide_index=True
        )

        return True

    except Exception as e:

        st.error(
            f"❌ {symbol} test failed:"
        )

        st.code(
            repr(e)
        )

        return False
        
# ============================================================
# RMA
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


# ============================================================
# ATR
# ============================================================

def atr(
    df,
    length=14
):

    prev_close = (
        df["close"]
        .shift(1)
    )

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
    ).max(
        axis=1
    )

    return rma(
        tr,
        length
    )


# ============================================================
# RSI
# ============================================================

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

    rs = (
        avg_gain /
        avg_loss.replace(
            0,
            np.nan
        )
    )

    return (
        100
        -
        (
            100 /
            (
                1 + rs
            )
        )
    )


# ============================================================
# ADX
# ============================================================

def adx(
    df,
    length=9
):

    high = df["high"]

    low = df["low"]

    up_move = (
        high -
        high.shift(1)
    )

    down_move = (
        low.shift(1) -
        low
    )

    plus_dm = pd.Series(
        np.where(
            (
                (up_move > down_move)
                &
                (up_move > 0)
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
                &
                (down_move > 0)
            ),
            down_move,
            0
        ),
        index=df.index
    )

    prev_close = (
        df["close"]
        .shift(1)
    )

    tr = pd.concat(
        [
            high - low,
            (
                high -
                prev_close
            ).abs(),
            (
                low -
                prev_close
            ).abs()
        ],
        axis=1
    ).max(
        axis=1
    )

    atr_value = rma(
        tr,
        length
    )

    plus_di = (
        100
        *
        rma(
            plus_dm,
            length
        )
        /
        atr_value.replace(
            0,
            np.nan
        )
    )

    minus_di = (
        100
        *
        rma(
            minus_dm,
            length
        )
        /
        atr_value.replace(
            0,
            np.nan
        )
    )

    dx = (
        100
        *
        (
            plus_di -
            minus_di
        ).abs()
        /
        (
            plus_di +
            minus_di
        ).replace(
            0,
            np.nan
        )
    )

    return rma(
        dx,
        length
    )


# ============================================================
# SESSION VWAP
# ============================================================

def session_vwap(
    df
):

    typical_price = (
        df["high"]
        +
        df["low"]
        +
        df["close"]
    ) / 3

    day = (
        df["datetime"]
        .dt.date
    )

    pv = (
        typical_price
        *
        df["volume"]
    )

    cumulative_pv = (
        pv
        .groupby(day)
        .cumsum()
    )

    cumulative_volume = (
        df["volume"]
        .groupby(day)
        .cumsum()
    )

    return (
        cumulative_pv
        /
        cumulative_volume.replace(
            0,
            np.nan
        )
    )


# ============================================================
# PREPARE DATA
# ============================================================

def prepare(
    df,
    rsi_len,
    adx_len,
    atr_len
):

    df = df.copy()

    df = (
        df
        .sort_values(
            "datetime"
        )
        .reset_index(
            drop=True
        )
    )

    # --------------------------------------------------------
    # INDICATORS
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
    # VOLUME
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
    # CANDLE BODY
    # --------------------------------------------------------

    candle_range = (
        df["high"]
        -
        df["low"]
    )

    df["body_strength"] = (
        (
            df["close"]
            -
            df["open"]
        ).abs()
        /
        candle_range.replace(
            0,
            np.nan
        )
    )

    # --------------------------------------------------------
    # BULL / BEAR
    # --------------------------------------------------------

    df["bull"] = (
        df["close"]
        >
        df["open"]
    )

    df["bear"] = (
        df["close"]
        <
        df["open"]
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

    return float(
        brokerage
    )


# ============================================================
# ORB BACKTEST
# ============================================================

def run_backtest(
    df,
    p
):

    trades = []

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

    # ========================================================
    # CANDLE LOOP
    # ========================================================

    for i in range(
        len(df)
    ):

        row = df.iloc[i]

        ts = row["datetime"]

        day = ts.date()

        tm = ts.time()

        # ====================================================
        # NEW DAY
        # ====================================================

        if current_day != day:

            position = None

            current_day = day

            orb_high = None

            orb_low = None

            orb_locked = False

            daily_pnl = 0.0

            daily_trades = 0

        # ====================================================
        # BUILD ORB
        # ====================================================

        if (
            tm >= p["orb_start"]
            and
            tm < p["orb_end"]
        ):

            if orb_high is None:

                orb_high = (
                    row["high"]
                )

                orb_low = (
                    row["low"]
                )

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

        # ====================================================
        # LOCK ORB
        # ====================================================

        if (
            not orb_locked
            and
            tm >= p["orb_end"]
            and
            orb_high is not None
        ):

            orb_locked = True

        # ====================================================
        # MANAGE POSITION
        # ====================================================

        if position is not None:

            side = (
                position["side"]
            )

            entry = (
                position["entry"]
            )

            sl = (
                position["sl"]
            )

            tp = (
                position["tp"]
            )

            qty_value = (
                position["qty"]
            )

            exit_price = None

            reason = None

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

                # Conservative:
                # if SL and TP both hit,
                # assume SL first.

                if hit_sl:

                    exit_price = sl

                    reason = "SL"

                elif hit_tp:

                    exit_price = tp

                    reason = "TP"

            # ------------------------------------------------
            # SHORT
            # ------------------------------------------------

            else:

                hit_sl = (
                    row["high"]
                    >= sl
                )

                hit_tp = (
                    row["low"]
                    <= tp
                )

                if hit_sl:

                    exit_price = sl

                    reason = "SL"

                elif hit_tp:

                    exit_price = tp

                    reason = "TP"

            # ------------------------------------------------
            # SQUARE OFF
            # ------------------------------------------------

            if (
                exit_price is None
                and
                tm >= p[
                    "squareoff_time"
                ]
            ):

                exit_price = (
                    row["close"]
                )

                reason = "SquareOff"

            # ------------------------------------------------
            # EXIT
            # ------------------------------------------------

            if exit_price is not None:

                if side == "LONG":

                    gross = (
                        exit_price
                        -
                        entry
                    ) * qty_value

                else:

                    gross = (
                        entry
                        -
                        exit_price
                    ) * qty_value

                brokerage = (
                    broker_charge(
                        entry,
                        exit_price,
                        qty_value,
                        p["brokerage"]
                    )
                )

                net = (
                    gross -
                    brokerage
                )

                equity += net

                daily_pnl += net

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
                        "Reason": reason,
                        "Qty": qty_value,
                        "Gross P&L": gross,
                        "Brokerage": brokerage,
                        "Net P&L": net,
                        "Equity": equity,
                    }
                )

                position = None

                continue

        # ====================================================
        # ENTRY FILTER
        # ====================================================

        if not orb_locked:

            continue

        if (
            orb_high is None
            or
            orb_low is None
        ):

            continue

        # ----------------------------------------------------
        # ENTRY WINDOW
        # ----------------------------------------------------

        if (
            tm < p["entry_start"]
            or
            tm > p["entry_end"]
        ):

            continue

        # ----------------------------------------------------
        # DAILY LOSS
        # ----------------------------------------------------

        if (
            daily_pnl
            <=
            -abs(
                p["daily_max_loss"]
            )
        ):

            continue

        # ----------------------------------------------------
        # MAX TRADES
        # ----------------------------------------------------

        if (
            daily_trades
            >=
            p["max_trades_day"]
        ):

            continue

        # ----------------------------------------------------
        # CONTINUOUS MODE
        # ----------------------------------------------------

        if (
            not p["continuous"]
            and
            daily_trades > 0
        ):

            continue

        # ----------------------------------------------------
        # INDICATORS READY
        # ----------------------------------------------------

        if pd.isna(
            row["atr"]
        ):

            continue

        if pd.isna(
            row["rsi"]
        ):

            continue

        if pd.isna(
            row["adx"]
        ):

            continue

        if pd.isna(
            row["vwap"]
        ):

            continue

        # ====================================================
        # ORB RANGE
        # ====================================================

        orb_range = (
            orb_high -
            orb_low
        )

        if orb_range <= 0:

            continue

        orb_ratio = (
            orb_range /
            row["atr"]
        )

        if (
            orb_ratio
            <
            p["orb_min_atr"]
        ):

            continue

        if (
            orb_ratio
            >
            p["orb_max_atr"]
        ):

            continue

        # ====================================================
        # ADX
        # ====================================================

        if (
            row["adx"]
            <
            p["adx_min"]
        ):

            continue

        # ----------------------------------------------------
        # ADX RISING
        # ----------------------------------------------------

        if p["adx_rising"]:

            if i == 0:

                continue

            previous_adx = (
                df.iloc[
                    i - 1
                ]["adx"]
            )

            if pd.isna(
                previous_adx
            ):

                continue

            if (
                row["adx"]
                <=
                previous_adx
            ):

                continue

        # ====================================================
        # VOLUME
        # ====================================================

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
                *
                p["volume_multiplier"]
            ):

                continue

        # ====================================================
        # RECENT VOLUME
        # ====================================================

        if (
            p[
                "recent_volume_multiplier"
            ]
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
                *
                p[
                    "recent_volume_multiplier"
                ]
            ):

                continue

        # ====================================================
        # BODY
        # ====================================================

        if (
            row["body_strength"]
            <
            p["body_strength"]
        ):

            continue

        # ====================================================
        # LONG SIGNAL
        # ====================================================

        long_signal = (
            p["allow_long"]
            and
            row["close"]
            >
            orb_high
            and
            row["close"]
            >
            row["open"]
            and
            row["rsi"]
            >=
            p["rsi_long"]
            and
            row["close"]
            >
            row["vwap"]
        )

        # ====================================================
        # SHORT SIGNAL
        # ====================================================

        short_signal = (
            p["allow_short"]
            and
            row["close"]
            <
            orb_low
            and
            row["close"]
            <
            row["open"]
            and
            row["rsi"]
            <=
            p["rsi_short"]
            and
            row["close"]
            <
            row["vwap"]
        )

        # ====================================================
        # LONG ENTRY
        # ====================================================

        if long_signal:

            entry = float(
                row["close"]
            )

            sl = min(
                orb_low,
                entry -
                (
                    float(
                        row["atr"]
                    )
                    *
                    p["sl_atr"]
                )
            )

            risk = (
                entry -
                sl
            )

            if risk <= 0:

                continue

            tp = (
                entry
                +
                (
                    risk *
                    p["rr"]
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

        # ====================================================
        # SHORT ENTRY
        # ====================================================

        if short_signal:

            entry = float(
                row["close"]
            )

            sl = max(
                orb_high,
                entry +
                (
                    float(
                        row["atr"]
                    )
                    *
                    p["sl_atr"]
                )
            )

            risk = (
                sl -
                entry
            )

            if risk <= 0:

                continue

            tp = (
                entry
                -
                (
                    risk *
                    p["rr"]
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

    return pd.DataFrame(
        trades
    )


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(
    trades
):

    if (
        trades is None
        or
        trades.empty
    ):

        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "net_pnl": 0,
            "profit_factor": 0,
            "max_drawdown": 0
        }

    pnl = pd.to_numeric(
        trades["Net P&L"],
        errors="coerce"
    ).fillna(0)

    wins = int(
        (
            pnl > 0
        ).sum()
    )

    losses = int(
        (
            pnl < 0
        ).sum()
    )

    total = len(
        pnl
    )

    win_rate = (
        wins /
        total *
        100
        if total
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

    if gross_loss > 0:

        profit_factor = (
            gross_profit /
            gross_loss
        )

    else:

        profit_factor = np.inf

    equity = (
        pnl.cumsum()
    )

    peak = (
        equity.cummax()
    )

    drawdown = (
        equity -
        peak
    )

    return {
        "trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "net_pnl": pnl.sum(),
        "profit_factor": profit_factor,
        "max_drawdown": drawdown.min()
    }


# ============================================================
# ALL STOCK BACKTEST
# ============================================================

def backtest_all_stocks(
    market_data,
    params
):

    all_trades = []

    summary = []

    progress = st.progress(
        0
    )

    total = len(
        market_data
    )

    for i, (
        symbol,
        raw_df
    ) in enumerate(
        market_data.items()
    ):

        try:

            prepared = prepare(
                raw_df,
                params["rsi_len"],
                params["adx_len"],
                params["atr_len"]
            )

            trades = run_backtest(
                prepared,
                params
            )

            if (
                trades is not None
                and
                not trades.empty
            ):

                trades = trades.copy()

                trades["Symbol"] = (
                    symbol
                )

                all_trades.append(
                    trades
                )

            m = calculate_metrics(
                trades
            )

            summary.append(
                {
                    "Symbol": symbol,
                    "Trades": m[
                        "trades"
                    ],
                    "Wins": m[
                        "wins"
                    ],
                    "Losses": m[
                        "losses"
                    ],
                    "Win Rate %": round(
                        m[
                            "win_rate"
                        ],
                        2
                    ),
                    "Net P&L": round(
                        m[
                            "net_pnl"
                        ],
                        2
                    ),
                    "Profit Factor": (
                        round(
                            m[
                                "profit_factor"
                            ],
                            2
                        )
                        if np.isfinite(
                            m[
                                "profit_factor"
                            ]
                        )
                        else np.inf
                    ),
                    "Max DD": round(
                        m[
                            "max_drawdown"
                        ],
                        2
                    )
                }
            )

        except Exception as e:

            summary.append(
                {
                    "Symbol": symbol,
                    "Trades": 0,
                    "Wins": 0,
                    "Losses": 0,
                    "Win Rate %": 0,
                    "Net P&L": 0,
                    "Profit Factor": 0,
                    "Max DD": 0,
                    "Error": str(e)
                }
            )

        progress.progress(
            (
                i + 1
            )
            /
            total
        )

    progress.empty()

    if all_trades:

        combined = pd.concat(
            all_trades,
            ignore_index=True
        )

        combined = (
            combined
            .sort_values(
                "Exit Time"
            )
            .reset_index(
                drop=True
            )
        )

    else:

        combined = pd.DataFrame()

    return (
        combined,
        pd.DataFrame(
            summary
        )
    )


# ============================================================
# SESSION STATE
# ============================================================

if "market_data" not in st.session_state:

    st.session_state.market_data = {}


if "failed_symbols" not in st.session_state:

    st.session_state.failed_symbols = []


if "backtest_trades" not in st.session_state:

    st.session_state.backtest_trades = (
        pd.DataFrame()
    )


if "summary_df" not in st.session_state:

    st.session_state.summary_df = (
        pd.DataFrame()
    )


# ============================================================
# SIDEBAR - DATA
# ============================================================

st.sidebar.title(
    "📡 TradingView Data"
)

n_bars = st.sidebar.number_input(
    "5-Min Bars / Stock",
    min_value=500,
    max_value=5000,
    value=5000,
    step=500
)

fetch_delay = st.sidebar.number_input(
    "Fetch Delay",
    min_value=0.0,
    max_value=5.0,
    value=0.25,
    step=0.05
)


# ============================================================
# FETCH
# ============================================================

if st.sidebar.button(
    "📡 FETCH 5-MIN DATA",
    type="primary",
    use_container_width=True
):

    try:

        with st.spinner(
            "Connecting to TradingView..."
        ):

            tv = (
                create_tv_connection()
            )

        data, failed = (
            fetch_all_stocks(
                tv,
                NIFTY_SYMBOLS,
                int(n_bars),
                float(fetch_delay)
            )
        )

        st.session_state.market_data = (
            data
        )

        st.session_state.failed_symbols = (
            failed
        )

        st.session_state.backtest_trades = (
            pd.DataFrame()
        )

        st.session_state.summary_df = (
            pd.DataFrame()
        )

        st.success(
            f"✅ Loaded "
            f"{len(data)} stocks."
        )

    except Exception as e:

        st.error(
            f"❌ Fetch failed: {e}"
        )


# ============================================================
# CLEAR
# ============================================================

if st.sidebar.button(
    "🗑️ CLEAR DATA",
    use_container_width=True
):

    st.session_state.market_data = {}

    st.session_state.failed_symbols = []

    st.session_state.backtest_trades = (
        pd.DataFrame()
    )

    st.session_state.summary_df = (
        pd.DataFrame()
    )

    st.rerun()


# ============================================================
# MAIN
# ============================================================

st.title(
    "📈 TradingView 5-Min ORB Backtest"
)

st.caption(
    "Direct TradingView Data • No Input CSV"
)


market_data = (
    st.session_state.market_data
)


if not market_data:

    st.info(
        "👈 Click "
        "**FETCH 5-MIN DATA** "
        "from the sidebar."
    )

    st.stop()


# ============================================================
# DATA STATUS
# ============================================================

col1, col2, col3 = (
    st.columns(3)
)

with col1:

    st.metric(
        "Stocks Loaded",
        len(market_data)
    )

with col2:

    total_rows = sum(
        len(df)
        for df in market_data.values()
    )

    st.metric(
        "Total Rows",
        f"{total_rows:,}"
    )

with col3:

    st.metric(
        "Failed",
        len(
            st.session_state.failed_symbols
        )
    )


# ============================================================
# FAILED
# ============================================================

if st.session_state.failed_symbols:

    with st.expander(
        "⚠️ Failed Symbols"
    ):

        st.dataframe(
            pd.DataFrame(
                st.session_state.failed_symbols
            ),
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# STOCK SELECT
# ============================================================

st.sidebar.divider()

available_symbols = sorted(
    market_data.keys()
)

selected_stock = st.sidebar.selectbox(
    "Backtest Stock",
    [
        "ALL STOCKS"
    ]
    +
    available_symbols
)


# ============================================================
# ORB SETTINGS
# ============================================================

st.sidebar.subheader(
    "🎯 ORB"
)

orb_end = st.sidebar.time_input(
    "ORB End",
    value=time(
        9,
        30
    )
)

entry_start = st.sidebar.time_input(
    "Entry Start",
    value=time(
        9,
        30
    )
)

entry_end = st.sidebar.time_input(
    "Entry End",
    value=time(
        10,
        30
    )
)

squareoff = st.sidebar.time_input(
    "Squareoff",
    value=time(
        15,
        13
    )
)


# ============================================================
# INDICATORS
# ============================================================

st.sidebar.subheader(
    "📊 Indicators"
)

rsi_len = st.sidebar.number_input(
    "RSI Length",
    min_value=2,
    max_value=100,
    value=14
)

rsi_long = st.sidebar.number_input(
    "Long RSI >= ",
    min_value=1.0,
    max_value=99.0,
    value=50.0,
    step=1.0
)

rsi_short = st.sidebar.number_input(
    "Short RSI <= ",
    min_value=1.0,
    max_value=99.0,
    value=40.0,
    step=1.0
)

adx_len = st.sidebar.number_input(
    "ADX Length",
    min_value=2,
    max_value=100,
    value=9
)

adx_min = st.sidebar.number_input(
    "Minimum ADX",
    min_value=0.0,
    max_value=100.0,
    value=20.0,
    step=1.0
)

adx_rising = st.sidebar.checkbox(
    "ADX Must Be Rising",
    value=False
)

atr_len = st.sidebar.number_input(
    "ATR Length",
    min_value=2,
    max_value=100,
    value=14
)


# ============================================================
# ORB ATR
# ============================================================

st.sidebar.subheader(
    "📏 ORB Range"
)

orb_min_atr = st.sidebar.number_input(
    "ORB Min ATR",
    min_value=0.0,
    max_value=20.0,
    value=1.0,
    step=0.1
)

orb_max_atr = st.sidebar.number_input(
    "ORB Max ATR",
    min_value=0.1,
    max_value=50.0,
    value=3.0,
    step=0.1
)


# ============================================================
# VOLUME
# ============================================================

st.sidebar.subheader(
    "📊 Volume"
)

volume_multiplier = st.sidebar.number_input(
    "Volume SMA Multiplier",
    min_value=0.0,
    max_value=20.0,
    value=1.0,
    step=0.1
)

recent_volume_multiplier = (
    st.sidebar.number_input(
        "Recent Volume Multiplier",
        min_value=0.0,
        max_value=20.0,
        value=1.2,
        step=0.1
    )
)

body_strength = st.sidebar.number_input(
    "Body Strength",
    min_value=0.0,
    max_value=1.0,
    value=0.60,
    step=0.05
)


# ============================================================
# RISK
# ============================================================

st.sidebar.subheader(
    "💰 Risk"
)

rr = st.sidebar.number_input(
    "Risk Reward",
    min_value=0.1,
    max_value=20.0,
    value=2.0,
    step=0.1
)

sl_atr = st.sidebar.number_input(
    "SL ATR Multiplier",
    min_value=0.1,
    max_value=20.0,
    value=1.5,
    step=0.1
)

qty = st.sidebar.number_input(
    "Quantity",
    min_value=1,
    max_value=100000,
    value=50
)

capital = st.sidebar.number_input(
    "Initial Capital",
    min_value=1000.0,
    max_value=100000000.0,
    value=75000.0,
    step=1000.0
)

brokerage = st.sidebar.number_input(
    "Brokerage / Trade",
    min_value=0.0,
    max_value=1000.0,
    value=40.0,
    step=5.0
)

daily_max_loss = st.sidebar.number_input(
    "Daily Max Loss",
    min_value=0.0,
    max_value=10000000.0,
    value=5000.0,
    step=500.0
)


# ============================================================
# TRADE MODE
# ============================================================

st.sidebar.subheader(
    "🔄 Trade Mode"
)

continuous = st.sidebar.checkbox(
    "Continuous Trade",
    value=False
)

max_trades_day = st.sidebar.number_input(
    "Max Trades / Day",
    min_value=1,
    max_value=100,
    value=10
)

allow_long = st.sidebar.checkbox(
    "Enable LONG",
    value=True
)

allow_short = st.sidebar.checkbox(
    "Enable SHORT",
    value=True
)


# ============================================================
# PARAMETERS
# ============================================================

params = {

    "orb_start": time(
        9,
        15
    ),

    "orb_end": orb_end,

    "entry_start": entry_start,

    "entry_end": entry_end,

    "squareoff_time": squareoff,

    "rsi_len": int(
        rsi_len
    ),

    "rsi_long": float(
        rsi_long
    ),

    "rsi_short": float(
        rsi_short
    ),

    "adx_len": int(
        adx_len
    ),

    "adx_min": float(
        adx_min
    ),

    "adx_rising": bool(
        adx_rising
    ),

    "atr_len": int(
        atr_len
    ),

    "orb_min_atr": float(
        orb_min_atr
    ),

    "orb_max_atr": float(
        orb_max_atr
    ),

    "volume_multiplier": float(
        volume_multiplier
    ),

    "recent_volume_multiplier": float(
        recent_volume_multiplier
    ),

    "body_strength": float(
        body_strength
    ),

    "rr": float(
        rr
    ),

    "sl_atr": float(
        sl_atr
    ),

    "qty": int(
        qty
    ),

    "initial_capital": float(
        capital
    ),

    "brokerage": float(
        brokerage
    ),

    "daily_max_loss": float(
        daily_max_loss
    ),

    "continuous": bool(
        continuous
    ),

    "max_trades_day": int(
        max_trades_day
    ),

    "allow_long": bool(
        allow_long
    ),

    "allow_short": bool(
        allow_short
    )
}


# ============================================================
# RUN BACKTEST BUTTON
# ============================================================

st.divider()

if st.button(
    "🚀 RUN BACKTEST",
    type="primary",
    use_container_width=True
):

    # ========================================================
    # ALL STOCKS
    # ========================================================

    if selected_stock == "ALL STOCKS":

        trades, summary = (
            backtest_all_stocks(
                market_data,
                params
            )
        )

    # ========================================================
    # ONE STOCK
    # ========================================================

    else:

        raw_df = (
            market_data[
                selected_stock
            ]
        )

        prepared_df = prepare(
            raw_df,
            params["rsi_len"],
            params["adx_len"],
            params["atr_len"]
        )

        trades = run_backtest(
            prepared_df,
            params
        )

        if not trades.empty:

            trades["Symbol"] = (
                selected_stock
            )

        m = calculate_metrics(
            trades
        )

        summary = pd.DataFrame(
            [
                {
                    "Symbol": selected_stock,
                    "Trades": m[
                        "trades"
                    ],
                    "Wins": m[
                        "wins"
                    ],
                    "Losses": m[
                        "losses"
                    ],
                    "Win Rate %": round(
                        m[
                            "win_rate"
                        ],
                        2
                    ),
                    "Net P&L": round(
                        m[
                            "net_pnl"
                        ],
                        2
                    ),
                    "Profit Factor": (
                        round(
                            m[
                                "profit_factor"
                            ],
                            2
                        )
                        if np.isfinite(
                            m[
                                "profit_factor"
                            ]
                        )
                        else np.inf
                    ),
                    "Max DD": round(
                        m[
                            "max_drawdown"
                        ],
                        2
                    )
                }
            ]
        )

    st.session_state.backtest_trades = (
        trades
    )

    st.session_state.summary_df = (
        summary
    )


# ============================================================
# SHOW RESULT
# ============================================================

trades = (
    st.session_state.backtest_trades
)

summary = (
    st.session_state.summary_df
)


if (
    trades is None
    or
    trades.empty
):

    st.info(
        "Click RUN BACKTEST."
    )

    st.stop()


# ============================================================
# METRICS
# ============================================================

metrics = calculate_metrics(
    trades
)

c1, c2, c3, c4, c5, c6 = (
    st.columns(6)
)

with c1:

    st.metric(
        "Trades",
        metrics["trades"]
    )

with c2:

    st.metric(
        "Wins",
        metrics["wins"]
    )

with c3:

    st.metric(
        "Losses",
        metrics["losses"]
    )

with c4:

    st.metric(
        "Win Rate",
        f"{metrics['win_rate']:.2f}%"
    )

with c5:

    st.metric(
        "Net P&L",
        f"₹{metrics['net_pnl']:,.2f}"
    )

with c6:

    pf = metrics[
        "profit_factor"
    ]

    st.metric(
        "Profit Factor",
        (
            f"{pf:.2f}"
            if np.isfinite(pf)
            else "∞"
        )
    )


st.metric(
    "Max Drawdown",
    f"₹{metrics['max_drawdown']:,.2f}"
)


# ============================================================
# STOCK SUMMARY
# ============================================================

if selected_stock == "ALL STOCKS":

    st.subheader(
        "📊 Stock-wise Results"
    )

    if not summary.empty:

        summary = (
            summary
            .sort_values(
                "Net P&L",
                ascending=False
            )
            .reset_index(
                drop=True
            )
        )

        st.dataframe(
            summary,
            use_container_width=True,
            hide_index=True
        )

        winners = int(
            (
                summary[
                    "Net P&L"
                ]
                > 0
            ).sum()
        )

        losers = int(
            (
                summary[
                    "Net P&L"
                ]
                < 0
            ).sum()
        )

        c1, c2, c3 = (
            st.columns(3)
        )

        with c1:

            st.metric(
                "Profitable Stocks",
                winners
            )

        with c2:

            st.metric(
                "Losing Stocks",
                losers
            )

        with c3:

            st.metric(
                "Stocks Tested",
                len(summary)
            )


# ============================================================
# EQUITY CURVE
# ============================================================

st.subheader(
    "📈 Equity Curve"
)

equity = (
    trades
    .sort_values(
        "Exit Time"
    )
    .copy()
)

equity[
    "Combined Equity"
] = (
    params["initial_capital"]
    +
    equity[
        "Net P&L"
    ].cumsum()
)

chart_df = (
    equity[
        [
            "Exit Time",
            "Combined Equity"
        ]
    ]
    .set_index(
        "Exit Time"
    )
)

st.line_chart(
    chart_df[
        "Combined Equity"
    ]
)


# ============================================================
# TRADE TABLE
# ============================================================

st.subheader(
    "📋 Trade Report"
)

display_trades = (
    trades
    .sort_values(
        "Exit Time",
        ascending=False
    )
)

st.dataframe(
    display_trades,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# DOWNLOAD TRADE REPORT
# ============================================================

csv_data = (
    display_trades
    .to_csv(
        index=False
    )
    .encode(
        "utf-8"
    )
)

st.download_button(
    "⬇️ Download Trade Report",
    data=csv_data,
    file_name="orb_trade_report.csv",
    mime="text/csv"
)


# ============================================================
# RAW 5-MIN DATA
# ============================================================

if selected_stock != "ALL STOCKS":

    st.subheader(
        f"📡 {selected_stock} "
        f"— TradingView 5-Min Data"
    )

    selected_df = (
        market_data[
            selected_stock
        ]
    )

    c1, c2, c3 = (
        st.columns(3)
    )

    with c1:

        st.metric(
            "Rows",
            f"{len(selected_df):,}"
        )

    with c2:

        st.metric(
            "First Candle",
            str(
                selected_df[
                    "datetime"
                ].min()
            )
        )

    with c3:

        st.metric(
            "Last Candle",
            str(
                selected_df[
                    "datetime"
                ].max()
            )
        )

    with st.expander(
        "View Raw 5-Min Data"
    ):

        st.dataframe(
            selected_df.tail(
                500
            ),
            use_container_width=True,
            hide_index=True
        )








AND 



import enum
import json
import logging
import random
import re
import string
import datetime

import pandas as pd
import pytz
import requests
import streamlit as st

from websocket import create_connection


# ============================================================
# INTERVAL
# ============================================================

class Interval(enum.Enum):
    in_30_minute = "30"
    in_1_minute = "1"
    in_3_minute = "3"
    in_5_minute = "5"
    in_15_minute = "15"
    in_45_minute = "45"

    in_1_hour = "1H"
    in_2_hour = "2H"
    in_3_hour = "3H"
    in_4_hour = "4H"

    in_daily = "1D"
    in_weekly = "1W"
    in_monthly = "1M"


# ============================================================
# TV DATAFEED
# ============================================================

class TvDatafeed:

    __sign_in_url = (
        "https://www.tradingview.com/accounts/signin/"
    )

    __search_url = (
        "https://symbol-search.tradingview.com/"
        "symbol_search/?text={}&hl=1&exchange={}"
        "&lang=en&type=&domain=production"
    )

    __ws_url = (
        "wss://data.tradingview.com/socket.io/websocket"
    )

    __ws_headers = {
        "Origin": "https://data.tradingview.com"
    }

    __signin_headers = {
        "Referer": "https://www.tradingview.com"
    }

    __ws_timeout = 10


    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        username: str = None,
        password: str = None,
        token: str = None
    ) -> None:

        self.ws_debug = False
        self.ws = None

        # ----------------------------------------------------
        # AUTH TOKEN
        # ----------------------------------------------------

        if token:
            self.token = token

        elif username and password:
            self.token = self.__auth(
                username,
                password
            )

        else:
            self.token = None

        # Anonymous TradingView token
        if not self.token:
            self.token = "unauthorized_user_token"

        # ----------------------------------------------------
        # SESSIONS
        # ----------------------------------------------------

        self.session = self.__generate_session()

        self.chart_session = (
            self.__generate_chart_session()
        )


    # ========================================================
    # LOGIN
    # ========================================================

    def __auth(self, username, password):

        data = {
            "username": username,
            "password": password,
            "remember": "on"
        }

        try:

            response = requests.post(
                url=self.__sign_in_url,
                data=data,
                headers=self.__signin_headers,
                timeout=15
            )

            response.raise_for_status()

            result = response.json()

            token = (
                result
                .get("user", {})
                .get("auth_token")
            )

            if token:
                logging.info(
                    "TradingView login successful"
                )

            else:
                logging.error(
                    "TradingView login response "
                    "does not contain auth_token"
                )

            return token

        except Exception as e:

            logging.error(
                "TradingView authentication failed: %s",
                e
            )

            return None


    # ========================================================
    # WEBSOCKET CONNECTION
    # ========================================================

    def __create_connection(self):

        logging.debug(
            "Creating TradingView websocket connection"
        )

        self.ws = create_connection(
            self.__ws_url,
            header=[
                "Origin: https://data.tradingview.com"
            ],
            timeout=self.__ws_timeout
        )


    # ========================================================
    # CLOSE CONNECTION
    # ========================================================

    def __close_connection(self):

        try:

            if self.ws:
                self.ws.close()

        except Exception:
            pass

        finally:
            self.ws = None


    # ========================================================
    # SESSION ID
    # ========================================================

    @staticmethod
    def __generate_session():

        string_length = 12

        letters = string.ascii_lowercase

        random_string = "".join(
            random.choice(letters)
            for _ in range(string_length)
        )

        return "qs_" + random_string


    @staticmethod
    def __generate_chart_session():

        string_length = 12

        letters = string.ascii_lowercase

        random_string = "".join(
            random.choice(letters)
            for _ in range(string_length)
        )

        return "cs_" + random_string


    # ========================================================
    # MESSAGE FORMAT
    # ========================================================

    @staticmethod
    def __prepend_header(message):

        return (
            "~m~"
            + str(len(message))
            + "~m~"
            + message
        )


    @staticmethod
    def __construct_message(
        func,
        param_list
    ):

        return json.dumps(
            {
                "m": func,
                "p": param_list
            },
            separators=(",", ":")
        )


    def __create_message(
        self,
        func,
        param_list
    ):

        message = self.__construct_message(
            func,
            param_list
        )

        return self.__prepend_header(message)


    def __send_message(
        self,
        func,
        args
    ):

        message = self.__create_message(
            func,
            args
        )

        if self.ws_debug:
            print(message)

        self.ws.send(message)


    # ========================================================
    # FORMAT SYMBOL
    # ========================================================

    @staticmethod
    def __format_symbol(
        symbol,
        exchange,
        contract=None
    ):

        symbol = str(symbol).upper().strip()
        exchange = str(exchange).upper().strip()

        # Already formatted
        if ":" in symbol:
            return symbol

        # Cash / Equity
        if contract is None:

            return f"{exchange}:{symbol}"

        # Futures
        if isinstance(contract, int):

            return (
                f"{exchange}:{symbol}{contract}!"
            )

        raise ValueError(
            "contract must be None or integer"
        )


    # ========================================================
    # PARSE TRADINGVIEW DATA
    # ========================================================

    @staticmethod
    def __create_df(
        raw_data,
        symbol
    ):

        try:

            # ------------------------------------------------
            # Locate series data
            # ------------------------------------------------

            match = re.search(
                r'"s":\[(.*?)\]',
                raw_data,
                re.DOTALL
            )

            if not match:

                logging.warning(
                    "No candle series found for %s",
                    symbol
                )

                return pd.DataFrame(
                    columns=[
                        "symbol",
                        "Datetime",
                        "Open",
                        "High",
                        "Low",
                        "Close",
                        "Volume"
                    ]
                )

            series_data = match.group(1)

            # ------------------------------------------------
            # Find each node
            # ------------------------------------------------

            nodes = re.findall(
                r'\{.*?"i":(.*?),"v":\[(.*?)\]\}',
                series_data,
                re.DOTALL
            )

            rows = []

            ist_tz = pytz.timezone(
                "Asia/Kolkata"
            )

            # ------------------------------------------------
            # Parse rows
            # ------------------------------------------------

            for node in nodes:

                values = node[1]

                try:

                    values = json.loads(
                        "[" + values + "]"
                    )

                except Exception:

                    continue

                if len(values) < 6:
                    continue

                try:

                    timestamp = float(
                        values[0]
                    )

                    dt_utc = (
                        datetime.datetime
                        .fromtimestamp(
                            timestamp,
                            tz=pytz.utc
                        )
                    )

                    dt_ist = (
                        dt_utc
                        .astimezone(ist_tz)
                    )

                    open_price = float(values[1])
                    high_price = float(values[2])
                    low_price = float(values[3])
                    close_price = float(values[4])

                    # TradingView sometimes gives volume
                    try:
                        volume = float(values[5])
                    except Exception:
                        volume = 0.0

                    rows.append(
                        [
                            dt_ist,
                            open_price,
                            high_price,
                            low_price,
                            close_price,
                            volume
                        ]
                    )

                except Exception:
                    continue

            # ------------------------------------------------
            # DataFrame
            # ------------------------------------------------

            if not rows:

                logging.warning(
                    "No parsed candle data for %s",
                    symbol
                )

                return pd.DataFrame(
                    columns=[
                        "symbol",
                        "Datetime",
                        "Open",
                        "High",
                        "Low",
                        "Close",
                        "Volume"
                    ]
                )

            df = pd.DataFrame(
                rows,
                columns=[
                    "Datetime",
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Volume"
                ]
            )

            df.insert(
                0,
                "symbol",
                symbol
            )

            # ------------------------------------------------
            # Clean
            # ------------------------------------------------

            df["Datetime"] = pd.to_datetime(
                df["Datetime"],
                errors="coerce"
            )

            df = df.dropna(
                subset=[
                    "Datetime",
                    "Open",
                    "High",
                    "Low",
                    "Close"
                ]
            )

            df = (
                df
                .drop_duplicates(
                    subset=["Datetime"]
                )
                .sort_values("Datetime")
                .reset_index(drop=True)
            )

            return df

        except Exception as e:

            logging.error(
                "TradingView dataframe error for %s: %s",
                symbol,
                e
            )

            return pd.DataFrame(
                columns=[
                    "symbol",
                    "Datetime",
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Volume"
                ]
            )


    # ========================================================
    # GET HISTORICAL DATA
    # ========================================================

    def get_hist(
        self,
        symbol: str,
        exchange: str = "NSE",
        interval: Interval = Interval.in_daily,
        n_bars: int = 10,
        fut_contract: int = None,
        extended_session: bool = False,
    ) -> pd.DataFrame:

        # ----------------------------------------------------
        # Validate interval
        # ----------------------------------------------------

        if not isinstance(
            interval,
            Interval
        ):

            raise ValueError(
                "interval must be an Interval enum"
            )

        # ----------------------------------------------------
        # Max TradingView bars
        # ----------------------------------------------------

        n_bars = min(
            int(n_bars),
            5000
        )

        if n_bars <= 0:

            raise ValueError(
                "n_bars must be greater than 0"
            )

        # ----------------------------------------------------
        # Format symbol
        # ----------------------------------------------------

        tv_symbol = self.__format_symbol(
            symbol=symbol,
            exchange=exchange,
            contract=fut_contract
        )

        interval_value = interval.value

        logging.info(
            "Fetching %s %s %s bars=%s",
            tv_symbol,
            interval_value,
            exchange,
            n_bars
        )

        raw_data = ""

        # ----------------------------------------------------
        # New websocket connection
        # ----------------------------------------------------

        self.__close_connection()
        self.__create_connection()

        try:

            # =================================================
            # AUTH
            # =================================================

            self.__send_message(
                "set_auth_token",
                [self.token]
            )

            # =================================================
            # CHART SESSION
            # =================================================

            self.chart_session = (
                self.__generate_chart_session()
            )

            self.__send_message(
                "chart_create_session",
                [
                    self.chart_session,
                    ""
                ]
            )

            # =================================================
            # RESOLVE SYMBOL
            # =================================================

            session_type = (
                "extended"
                if extended_session
                else "regular"
            )

            symbol_data = json.dumps(
                {
                    "symbol": tv_symbol,
                    "adjustment": "splits",
                    "session": session_type
                },
                separators=(",", ":")
            )

            self.__send_message(
                "resolve_symbol",
                [
                    self.chart_session,
                    "symbol_1",
                    "=" + symbol_data
                ]
            )

            # =================================================
            # CREATE SERIES
            # =================================================

            self.__send_message(
                "create_series",
                [
                    self.chart_session,
                    "s1",
                    "s1",
                    "symbol_1",
                    interval_value,
                    n_bars
                ]
            )

            # =================================================
            # TIMEZONE
            # =================================================

            self.__send_message(
                "switch_timezone",
                [
                    self.chart_session,
                    "exchange"
                ]
            )

            # =================================================
            # RECEIVE DATA
            # =================================================

            while True:

                try:

                    result = self.ws.recv()

                except Exception as e:

                    logging.error(
                        "TradingView websocket receive error: %s",
                        e
                    )

                    break

                if not result:
                    continue

                raw_data += (
                    result
                    + "\n"
                )

                # ------------------------------------------------
                # Important errors
                # ------------------------------------------------

                if (
                    "permission denied"
                    in result.lower()
                ):

                    logging.error(
                        "TradingView permission denied for %s",
                        tv_symbol
                    )

                    break

                if (
                    "symbol_error"
                    in result
                ):

                    logging.error(
                        "TradingView symbol error for %s",
                        tv_symbol
                    )

                    break

                if (
                    "critical_error"
                    in result
                ):

                    logging.error(
                        "TradingView critical error for %s",
                        tv_symbol
                    )

                    break

                if (
                    "series_error"
                    in result
                ):

                    logging.error(
                        "TradingView series error for %s",
                        tv_symbol
                    )

                    break

                # ------------------------------------------------
                # Completed
                # ------------------------------------------------

                if "series_completed" in result:

                    break

            # =================================================
            # CREATE DATAFRAME
            # =================================================

            df = self.__create_df(
                raw_data,
                symbol
            )

            if df.empty:

                logging.warning(
                    "No candle data found for %s",
                    symbol
                )

            return df

        finally:

            self.__close_connection()


    # ========================================================
    # SEARCH SYMBOL
    # ========================================================

    def search_symbol(
        self,
        text: str,
        exchange: str = ""
    ):

        url = self.__search_url.format(
            text,
            exchange
        )

        try:

            response = requests.get(
                url,
                timeout=15
            )

            response.raise_for_status()

            data = response.text

            data = (
                data
                .replace("</em>", "")
                .replace("<em>", "")
            )

            return json.loads(data)

        except Exception as e:

            logging.error(
                "Symbol search error: %s",
                e
            )

            return []


    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        self.__close_connection()
