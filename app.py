
# ============================================================
# STREAMLIT - TRADINGVIEW HISTORICAL DATA TEST
# ============================================================

import streamlit as st
import tvDatafeed

from tvDatafeed import TvDatafeed, Interval


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="TradingView Historical Data Test",
    page_icon="📈",
    layout="wide"
)


# ============================================================
# TITLE
# ============================================================

st.title("📈 TradingView Historical Data Test")

st.write(
    "Testing NSE cash symbol: **SBIN**"
)


# ============================================================
# SHOW LOADED FILE
# ============================================================

st.info(
    f"**tvDatafeed loaded from:**\n\n"
    f"`{tvDatafeed.__file__}`"
)


# ============================================================
# INTERVAL TEST
# ============================================================

st.write(
    "**Interval test:**",
    Interval.in_5_minute,
    "→",
    Interval.in_5_minute.value
)


# ============================================================
# CREATE TV OBJECT
# ============================================================

@st.cache_resource
def get_tv():

    return TvDatafeed()


# Create TradingView object
tv = get_tv()


# ============================================================
# TV CONNECTION STATUS
# ============================================================

st.success("✅ TvDatafeed object created")


# ============================================================
# FETCH BUTTON
# ============================================================

if st.button(
    "🚀 Fetch SBIN 5-Minute Data",
    type="primary",
    use_container_width=True
):

    st.write("### 🔄 Fetching data...")

    try:

        # ====================================================
        # IMPORTANT
        # ====================================================

        interval = Interval.in_5_minute

        st.write(
            "Sending:",
            f"`{interval}`",
            "→",
            f"`{interval.value}`"
        )


        # ====================================================
        # GET HISTORICAL DATA
        # ====================================================

        with st.spinner(
            "Connecting to TradingView and downloading candles..."
        ):

            df = tv.get_hist(
                symbol="SBIN",
                exchange="NSE",
                interval=interval,
                n_bars=500
            )


        # ====================================================
        # CHECK RESULT
        # ====================================================

        if df is None:

            st.error(
                "❌ TradingView returned None"
            )

            st.stop()


        if df.empty:

            st.error(
                "❌ TradingView returned EMPTY data"
            )

            st.stop()


        # ====================================================
        # SUCCESS
        # ====================================================

        st.success(
            f"✅ Historical data received successfully — "
            f"{len(df)} candles"
        )


        # ====================================================
        # DATA INFO
        # ====================================================

        col1, col2, col3, col4 = st.columns(4)


        with col1:

            st.metric(
                "Rows",
                len(df)
            )


        with col2:

            st.metric(
                "Symbol",
                "SBIN"
            )


        with col3:

            st.metric(
                "Interval",
                "5 Minute"
            )


        with col4:

            st.metric(
                "Exchange",
                "NSE"
            )


        # ====================================================
        # COLUMN INFORMATION
        # ====================================================

        st.subheader("📋 Columns")

        st.write(
            list(df.columns)
        )


        # ====================================================
        # DATE RANGE
        # ====================================================

        if "Datetime" in df.columns:

            min_date = df["Datetime"].min()

            max_date = df["Datetime"].max()

            st.info(
                f"📅 **Data range:** "
                f"{min_date} → {max_date}"
            )


        # ====================================================
        # DATA TYPES
        # ====================================================

        with st.expander("🔎 Data Information"):

            st.write(
                df.dtypes
            )


        # ====================================================
        # FIRST 10
        # ====================================================

        st.subheader(
            "🔼 First 10 Candles"
        )

        st.dataframe(
            df.head(10),
            use_container_width=True
        )


        # ====================================================
        # LAST 10
        # ====================================================

        st.subheader(
            "🔽 Last 10 Candles"
        )

        st.dataframe(
            df.tail(10),
            use_container_width=True
        )


        # ====================================================
        # FULL DATA
        # ====================================================

        with st.expander(
            f"📊 Show All {len(df)} Candles"
        ):

            st.dataframe(
                df,
                use_container_width=True,
                height=600
            )


        # ====================================================
        # DOWNLOAD CSV
        # ====================================================

        csv = df.to_csv(
            index=False
        )


        st.download_button(
            label="⬇️ Download SBIN 5-Minute CSV",
            data=csv,
            file_name="SBIN_5minute.csv",
            mime="text/csv",
            use_container_width=True
        )


    # ========================================================
    # ERROR
    # ========================================================

    except Exception as e:

        st.error(
            "❌ TradingView Error"
        )

        st.exception(e)
