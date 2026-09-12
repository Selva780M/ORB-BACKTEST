import os
import streamlit as st
import pandas as pd

from tvDatafeed import TvDatafeed, Interval


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="TradingView Historical Data",
    page_icon="📈",
    layout="wide"
)


# ============================================================
# TV CONNECTION
# ============================================================

@st.cache_resource
def get_tv():

    sessionid = st.secrets.get(
        "TV_SESSIONID",
        os.getenv("TV_SESSIONID")
    )

    sessionid_sign = st.secrets.get(
        "TV_SESSIONID_SIGN",
        os.getenv("TV_SESSIONID_SIGN")
    )

    auth_token = st.secrets.get(
        "TV_AUTH_TOKEN",
        os.getenv("TV_AUTH_TOKEN")
    )

    username = st.secrets.get(
        "TV_USERNAME",
        os.getenv("TV_USERNAME")
    )

    password = st.secrets.get(
        "TV_PASSWORD",
        os.getenv("TV_PASSWORD")
    )

    tv = TvDatafeed(

        username=username,
        password=password,

        token=auth_token,

        sessionid=sessionid,
        sessionid_sign=sessionid_sign,
    )

    return tv


# ============================================================
# HEADER
# ============================================================

st.title(
    "📈 TradingView Historical Data"
)

st.caption(
    "Direct TradingView WebSocket historical candle downloader"
)


# ============================================================
# CONNECTION
# ============================================================

try:

    tv = get_tv()

    if tv.authenticated:

        st.success(
            f"TradingView Connected — "
            f"Auth: {tv.auth_method}"
        )

    else:

        st.warning(
            "TradingView is running in anonymous mode. "
            "Some NSE symbols/data may be restricted."
        )

except Exception as e:

    st.error(
        f"TradingView connection failed: {e}"
    )

    st.stop()


# ============================================================
# INPUTS
# ============================================================

col1, col2, col3, col4 = st.columns(4)


with col1:

    symbol = st.text_input(
        "Symbol",
        value="NIFTY"
    ).strip().upper()


with col2:

    exchange = st.selectbox(
        "Exchange",
        [
            "NSE",
            "BSE",
            "MCX",
            "NFO",
            "BFO",
            "FOREXCOM",
            "FX_IDC",
            "BINANCE",
        ]
    )


with col3:

    timeframe = st.selectbox(
        "Timeframe",
        [
            "1 Minute",
            "3 Minute",
            "5 Minute",
            "15 Minute",
            "30 Minute",
            "45 Minute",
            "1 Hour",
            "2 Hour",
            "3 Hour",
            "4 Hour",
            "Daily",
        ]
    )


with col4:

    n_bars = st.number_input(
        "Number of candles",
        min_value=10,
        max_value=5000,
        value=500,
        step=100,
    )


# ============================================================
# FUTURES
# ============================================================

use_future = st.checkbox(
    "Use Continuous Futures"
)

fut_contract = None

if use_future:

    fut_contract = st.selectbox(
        "Futures Contract",
        [
            1,
            2,
            3,
            4,
            5,
        ],
        index=0
    )


# ============================================================
# TIMEFRAME MAP
# ============================================================

interval_map = {

    "1 Minute":
        Interval.in_1_minute,

    "3 Minute":
        Interval.in_3_minute,

    "5 Minute":
        Interval.in_5_minute,

    "15 Minute":
        Interval.in_15_minute,

    "30 Minute":
        Interval.in_30_minute,

    "45 Minute":
        Interval.in_45_minute,

    "1 Hour":
        Interval.in_1_hour,

    "2 Hour":
        Interval.in_2_hour,

    "3 Hour":
        Interval.in_3_hour,

    "4 Hour":
        Interval.in_4_hour,

    "Daily":
        Interval.in_daily,
}


# ============================================================
# FETCH
# ============================================================

if st.button(
    "🚀 Fetch Historical Data",
    type="primary",
    use_container_width=True,
):

    if not symbol:

        st.error(
            "Please enter symbol"
        )

        st.stop()

    interval = interval_map[
        timeframe
    ]

    full_symbol = (
        f"{exchange}:{symbol}"
    )

    if fut_contract is not None:

        full_symbol += (
            f"{int(fut_contract)}!"
        )

    st.info(
        f"Requesting: `{full_symbol}` | "
        f"TF: `{interval.value}` | "
        f"Bars: `{n_bars}`"
    )

    try:

        with st.spinner(
            "Fetching TradingView candles..."
        ):

            df = tv.get_hist(

                symbol=symbol,

                exchange=exchange,

                interval=interval,

                n_bars=int(n_bars),

                fut_contract=fut_contract,

                extended_session=False,
            )

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        if df is None or df.empty:

            st.error(
                "No historical data received."
            )

            st.write(
                "Possible reasons:"
            )

            st.write(
                [
                    "TradingView authentication is not valid",
                    "Symbol/exchange combination is wrong",
                    "Feed permission is restricted",
                    "Continuous futures contract is unavailable",
                ]
            )

        else:

            st.success(
                f"Received {len(df):,} candles"
            )

            # ------------------------------------------------
            # METRICS
            # ------------------------------------------------

            c1, c2, c3, c4 = st.columns(4)

            with c1:

                st.metric(
                    "Rows",
                    len(df)
                )

            with c2:

                st.metric(
                    "First",
                    str(
                        df["Datetime"].iloc[0]
                    )
                )

            with c3:

                st.metric(
                    "Last",
                    str(
                        df["Datetime"].iloc[-1]
                    )
                )

            with c4:

                st.metric(
                    "Last Close",
                    f"{df['Close'].iloc[-1]:,.2f}"
                )

            # ------------------------------------------------
            # CHART
            # ------------------------------------------------

            st.subheader(
                "Close Price"
            )

            chart_df = df.set_index(
                "Datetime"
            )

            st.line_chart(
                chart_df["Close"]
            )

            # ------------------------------------------------
            # DATA
            # ------------------------------------------------

            st.subheader(
                "Historical Candles"
            )

            st.dataframe(
                df,
                use_container_width=True,
                height=500
            )

            # ------------------------------------------------
            # CSV
            # ------------------------------------------------

            csv = df.to_csv(
                index=False
            ).encode(
                "utf-8"
            )

            st.download_button(
                "⬇️ Download CSV",
                data=csv,
                file_name=(
                    f"{exchange}_"
                    f"{symbol}_"
                    f"{interval.value}.csv"
                ),
                mime="text/csv",
                use_container_width=True,
            )

    except Exception as e:

        st.error(
            "TradingView request failed"
        )

        st.exception(e)


# ============================================================
# SYMBOL SEARCH
# ============================================================

st.divider()

st.subheader(
    "🔎 TradingView Symbol Search"
)

search_col1, search_col2 = st.columns(
    [3, 1]
)

with search_col1:

    search_text = st.text_input(
        "Search",
        placeholder="NIFTY / RELIANCE / SILVER..."
    )

with search_col2:

    search_exchange = st.text_input(
        "Exchange",
        value="NSE"
    )


if st.button(
    "Search Symbol",
    use_container_width=True
):

    if search_text:

        try:

            results = tv.search_symbol(
                search_text,
                search_exchange
            )

            if results:

                st.dataframe(
                    pd.DataFrame(
                        results
                    ),
                    use_container_width=True
                )

            else:

                st.warning(
                    "No symbols found."
                )

        except Exception as e:

            st.error(
                str(e)
            )
