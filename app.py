# ============================================================
# STREAMLIT TEST
# ============================================================

import streamlit as st
import tvDatafeed

from tvDatafeed import TvDatafeed


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

st.title(
    "📈 TradingView Historical Data Test"
)

st.write(
    "Testing NSE cash symbol: **SBIN**"
)


# ============================================================
# DEBUG
# ============================================================

st.info(
    f"tvDatafeed loaded from:\n\n"
    f"`{tvDatafeed.__file__}`"
)


# ============================================================
# CREATE TV OBJECT
# ============================================================

@st.cache_resource
def get_tv():

    return TvDatafeed()


tv = get_tv()


st.success(
    "✅ TvDatafeed loaded successfully"
)


# ============================================================
# FETCH BUTTON
# ============================================================

if st.button(
    "🚀 Fetch SBIN 5-Minute Data",
    type="primary",
    use_container_width=True
):

    try:

        with st.spinner(
            "Connecting to TradingView..."
        ):

            # IMPORTANT:
            # Send TradingView interval directly as string.
            df = tv.get_hist(
                symbol="SBIN",
                exchange="NSE",
                interval="5",
                n_bars=500
            )


        # ====================================================
        # RESULT
        # ====================================================

        if df is None or df.empty:

            st.error(
                "❌ NO DATA"
            )

            st.warning(
                "TradingView did not return candle data."
            )

        else:

            st.success(
                f"✅ Data received successfully — "
                f"{len(df)} candles"
            )


            # =================================================
            # METRICS
            # =================================================

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


            # =================================================
            # DATE RANGE
            # =================================================

            if "Datetime" in df.columns:

                st.info(
                    f"📅 **Data range:** "
                    f"{df['Datetime'].min()} "
                    f"→ "
                    f"{df['Datetime'].max()}"
                )


            # =================================================
            # COLUMNS
            # =================================================

            st.subheader(
                "📋 Columns"
            )

            st.write(
                list(df.columns)
            )


            # =================================================
            # FIRST 10
            # =================================================

            st.subheader(
                "🔼 First 10 Candles"
            )

            st.dataframe(
                df.head(10),
                use_container_width=True
            )


            # =================================================
            # LAST 10
            # =================================================

            st.subheader(
                "🔽 Last 10 Candles"
            )

            st.dataframe(
                df.tail(10),
                use_container_width=True
            )


            # =================================================
            # FULL DATA
            # =================================================

            with st.expander(
                f"📊 Show All {len(df)} Candles"
            ):

                st.dataframe(
                    df,
                    use_container_width=True,
                    height=600
                )


            # =================================================
            # DOWNLOAD
            # =================================================

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


    except Exception as e:

        st.error(
            "❌ TradingView Error"
        )

        st.exception(e)
