import os
import logging
import streamlit as st

from tvDatafeed import TvDatafeed, Interval


# ============================================================
# STREAMLIT CONFIG
# ============================================================

st.set_page_config(
    page_title="TradingView Data Test",
    page_icon="📈",
    layout="wide",
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# ============================================================
# CREATE TRADINGVIEW CONNECTION
# ============================================================

@st.cache_resource
def create_tv_connection():

    # Streamlit Secrets
    username = st.secrets.get("TV_USERNAME", None)
    password = st.secrets.get("TV_PASSWORD", None)
    token = st.secrets.get("TV_TOKEN", None)

    # Environment fallback
    if not username:
        username = os.getenv("TV_USERNAME")

    if not password:
        password = os.getenv("TV_PASSWORD")

    if not token:
        token = os.getenv("TV_TOKEN")

    if token:

        st.info("Using TradingView token")

        return TvDatafeed(
            token=token
        )

    if username and password:

        st.info("Using TradingView username/password")

        return TvDatafeed(
            username=username,
            password=password
        )

    raise RuntimeError(
        "TradingView credentials not found. "
        "Set TV_USERNAME + TV_PASSWORD or TV_TOKEN."
    )


# ============================================================
# PAGE
# ============================================================

st.title("📈 TradingView Historical Data Test")

st.write(
    "This page tests TradingView historical candle data "
    "before adding the ORB strategy."
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("TradingView Test")

symbol = st.sidebar.text_input(
    "Symbol",
    value="SBIN"
).strip().upper()

exchange = st.sidebar.text_input(
    "Exchange",
    value="NSE"
).strip().upper()

interval_name = st.sidebar.selectbox(
    "Interval",
    [
        "1 Minute",
        "5 Minute",
        "15 Minute",
        "30 Minute",
        "1 Hour",
        "1 Day",
    ],
    index=1,
)

n_bars = st.sidebar.number_input(
    "Number of candles",
    min_value=10,
    max_value=5000,
    value=100,
    step=10,
)

extended_session = st.sidebar.checkbox(
    "Extended Session",
    value=False,
)

test_button = st.sidebar.button(
    "🚀 Test TradingView",
    type="primary",
    use_container_width=True,
)


# ============================================================
# INTERVAL
# ============================================================

interval_map = {

    "1 Minute": Interval.in_1_minute,

    "5 Minute": Interval.in_5_minute,

    "15 Minute": Interval.in_15_minute,

    "30 Minute": Interval.in_30_minute,

    "1 Hour": Interval.in_1_hour,

    "1 Day": Interval.in_daily,
}


# ============================================================
# TEST
# ============================================================

if test_button:

    if not symbol:

        st.error("Enter a symbol.")

    else:

        # ----------------------------------------------------
        # Connection
        # ----------------------------------------------------

        try:

            with st.spinner("Connecting to TradingView..."):

                tv = create_tv_connection()

            st.success("✅ TradingView connection created")

        except Exception as e:

            st.error("❌ TradingView connection failed")

            st.code(
                f"{type(e).__name__}: {e}"
            )

            st.stop()


        # ----------------------------------------------------
        # Request details
        # ----------------------------------------------------

        st.subheader("📡 Request")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Symbol",
                f"{exchange}:{symbol}"
            )

        with col2:
            st.metric(
                "Interval",
                interval_name
            )

        with col3:
            st.metric(
                "Candles",
                n_bars
            )

        with col4:
            st.metric(
                "Futures Contract",
                "None"
            )


        # ----------------------------------------------------
        # IMPORTANT:
        # NSE CASH STOCK = fut_contract=None
        # ----------------------------------------------------

        try:

            with st.spinner(
                f"Fetching {exchange}:{symbol}..."
            ):

                df = tv.get_hist(

                    symbol=symbol,

                    exchange=exchange,

                    interval=interval_map[
                        interval_name
                    ],

                    n_bars=int(n_bars),

                    # IMPORTANT
                    fut_contract=None,

                    extended_session=extended_session,
                )


        except Exception as e:

            st.error(
                "❌ TradingView get_hist() failed"
            )

            st.code(
                f"{type(e).__name__}: {e}"
            )

            st.stop()


        # ----------------------------------------------------
        # Result
        # ----------------------------------------------------

        if df is None:

            st.error(
                "❌ TradingView returned None"
            )

            st.stop()


        if df.empty:

            st.error(
                "❌ TradingView returned EMPTY DATA"
            )

            st.warning(
                f"No candles returned for "
                f"{exchange}:{symbol}"
            )

            st.stop()


        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        st.success(
            f"✅ Historical data received: "
            f"{exchange}:{symbol}"
        )

        st.subheader("📊 Data Information")

        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric(
                "Rows",
                len(df)
            )

        with c2:
            st.metric(
                "Columns",
                len(df.columns)
            )

        with c3:
            st.metric(
                "Latest Close",
                f"{float(df['close'].iloc[-1]):.2f}"
                if "close" in df.columns
                else "N/A"
            )


        # ----------------------------------------------------
        # DATA
        # ----------------------------------------------------

        st.subheader("🕯️ Historical Candles")

        st.dataframe(
            df.tail(100),
            use_container_width=True,
            height=500,
        )


        # ----------------------------------------------------
        # COLUMNS
        # ----------------------------------------------------

        st.subheader("🔎 Columns")

        st.write(
            list(df.columns)
        )


        # ----------------------------------------------------
        # DOWNLOAD
        # ----------------------------------------------------

        csv_data = df.to_csv()

        st.download_button(
            "⬇️ Download CSV",
            data=csv_data,
            file_name=f"{symbol}_{interval_name}.csv",
            mime="text/csv",
            use_container_width=True,
        )


# ============================================================
# DEFAULT SCREEN
# ============================================================

else:

    st.info(
        "Select a symbol and click "
        "**🚀 Test TradingView**."
    )

    st.markdown(
        """
### Recommended first test

**Symbol:** `SBIN`

**Exchange:** `NSE`

**Interval:** `5 Minute`

**Futures Contract:** `None`

This should request:

```text
NSE:SBIN
