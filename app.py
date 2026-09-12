# ============================================================
# STREAMLIT TEST
# ============================================================
from tvDatafeed import TvDatafeed, Interval

import streamlit as st


st.set_page_config(
    page_title="TradingView Test",
    page_icon="📈",
    layout="wide"
)


st.title("📈 TradingView Historical Data Test")

st.write(
    "Testing NSE cash symbol: **SBIN**"
)


# ============================================================
# CREATE TV OBJECT
# ============================================================

@st.cache_resource
def get_tv():

    return TvDatafeed()

@st.cache_resource
def Int():

    return Interval()



tv = get_tv()
intr = Int()


# ============================================================
# FETCH BUTTON
# ============================================================

if st.button(
    "🚀 Fetch SBIN 5-Minute Data",
    type="primary"
):

    with st.spinner(
        "Connecting to TradingView..."
    ):

        try:

            # ------------------------------------------------
            # NSE CASH TEST
            # ------------------------------------------------

            df = tv.get_hist(
                symbol="SBIN",
                exchange="NSE",
                interval=intr.in_5_minute,
                n_bars=500
            )

            # ------------------------------------------------
            # RESULT
            # ------------------------------------------------

            if df is None or df.empty:

                st.error(
                    "❌ NO DATA"
                )

                st.warning(
                    "TradingView did not return candle data."
                )

            else:

                st.success(
                    f"✅ Data received successfully — {len(df)} candles"
                )

                # ------------------------------------------------
                # INFO
                # ------------------------------------------------

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

                # ------------------------------------------------
                # DATE RANGE
                # ------------------------------------------------

                if "Datetime" in df.columns:

                    min_date = df["Datetime"].min()

                    max_date = df["Datetime"].max()

                    st.info(
                        f"📅 Data range: "
                        f"{min_date} → {max_date}"
                    )

                # ------------------------------------------------
                # COLUMN CHECK
                # ------------------------------------------------

                st.subheader(
                    "📋 Columns"
                )

                st.write(
                    list(df.columns)
                )

                # ------------------------------------------------
                # FIRST 10
                # ------------------------------------------------

                st.subheader(
                    "🔼 First 10 Candles"
                )

                st.dataframe(
                    df.head(10),
                    use_container_width=True
                )

                # ------------------------------------------------
                # LAST 10
                # ------------------------------------------------

                st.subheader(
                    "🔽 Last 10 Candles"
                )

                st.dataframe(
                    df.tail(10),
                    use_container_width=True
                )

                # ------------------------------------------------
                # FULL DATA
                # ------------------------------------------------

                with st.expander(
                    "📊 Show Full 500 Candles"
                ):

                    st.dataframe(
                        df,
                        use_container_width=True,
                        height=600
                    )

                # ------------------------------------------------
                # DOWNLOAD
                # ------------------------------------------------

                csv = df.to_csv(
                    index=False
                )

                st.download_button(
                    label="⬇️ Download CSV",
                    data=csv,
                    file_name="SBIN_5minute.csv",
                    mime="text/csv"
                )

        except Exception as e:

            st.error(
                "❌ TradingView Error"
            )

            st.exception(e)
