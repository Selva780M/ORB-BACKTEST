
# ============================================================
# app.py
# Streamlit TradingView Historical Data Test
# ============================================================
import os
import sys
import importlib
import inspect

import pandas as pd
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
    "TradingView historical-data diagnostic tool"
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("⚙️ Settings")

symbol_input = st.sidebar.text_input(
    "Symbol",
    value="SBIN"
).strip().upper()

exchange_input = st.sidebar.text_input(
    "Exchange",
    value="NSE"
).strip().upper()

interval_input = st.sidebar.selectbox(
    "Interval",
    options=[
        "1",
        "3",
        "5",
        "15",
        "30",
        "45",
        "1H",
        "2H",
        "3H",
        "4H",
        "1D"
    ],
    index=2,
    format_func=lambda x: {
        "1": "1 Minute",
        "3": "3 Minutes",
        "5": "5 Minutes",
        "15": "15 Minutes",
        "30": "30 Minutes",
        "45": "45 Minutes",
        "1H": "1 Hour",
        "2H": "2 Hours",
        "3H": "3 Hours",
        "4H": "4 Hours",
        "1D": "Daily"
    }.get(x, x)
)

n_bars_input = st.sidebar.number_input(
    "Number of Candles",
    min_value=10,
    max_value=5000,
    value=500,
    step=100
)

extended_session = st.sidebar.checkbox(
    "Extended Session",
    value=False
)


# ============================================================
# DEBUG / MODULE INFORMATION
# ============================================================

st.subheader("🔍 Module Debug")

module_path = getattr(
    tvDatafeed,
    "__file__",
    "Unknown"
)

st.info(
    f"**Loaded tvDatafeed.py:**\n\n"
    f"`{module_path}`"
)

with st.expander("🐍 Python / Module Details"):

    col1, col2 = st.columns(2)

    with col1:

        st.write("Python executable")

        st.code(
            sys.executable
        )

    with col2:

        st.write("tvDatafeed module")

        st.code(
            str(tvDatafeed)
        )

    st.write("TvDatafeed class")

    st.code(
        str(TvDatafeed)
    )

    st.write("TvDatafeed source location")

    try:

        st.code(
            inspect.getfile(TvDatafeed)
        )

    except Exception:

        st.code(
            "Unable to determine source file"
        )




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
def get_tv():

    token1 = get_secret("TV_TOKEN")
    username = get_secret("TV_USERNAME")
    password = get_secret("TV_PASSWORD")
    st.write(username,password,token1)
    # --------------------------------------------------------
    # TOKEN LOGIN
    # --------------------------------------------------------
    
    if username and password:

        st.sidebar.success("🔐 TradingView: USERNAME/PASSWORD")

        tv = TvDatafeed(username=username,password=password)
        tv.token = token1
        return tv, tv.token 


# ============================================================
# CLEAR CACHE
# ============================================================

if st.sidebar.button(
    "🧹 Clear TV Cache",
    use_container_width=True
):

    get_tv.clear()

    st.cache_data.clear()

    st.success(
        "✅ TradingView cache cleared. "
        "Run the test again."
    )

    st.stop()


# ============================================================
# CREATE TV OBJECT
# ============================================================

try:

    tv = get_tv()

    st.success(
        "✅ TvDatafeed object created successfully"
    )

except Exception as e:

    st.error(
        "❌ Failed to create TvDatafeed"
    )

    st.exception(e)

    st.stop()


# ============================================================
# SYMBOL INFORMATION
# ============================================================

st.divider()

st.subheader("📌 Test Configuration")

config_col1, config_col2, config_col3, config_col4 = (
    st.columns(4)
)

with config_col1:

    st.metric(
        "Symbol",
        symbol_input
    )

with config_col2:

    st.metric(
        "Exchange",
        exchange_input
    )

with config_col3:

    st.metric(
        "Interval",
        interval_input
    )

with config_col4:

    st.metric(
        "Candles",
        n_bars_input
    )


# ============================================================
# SEARCH SYMBOL
# ============================================================

st.divider()

st.subheader(
    "🔎 TradingView Symbol Search"
)

st.write(
    "Use this first if TradingView reports "
    "`symbol_error / invalid symbol`."
)

search_col1, search_col2 = st.columns(
    [1, 3]
)

with search_col1:

    search_button = st.button(
        "🔎 Search Symbol",
        use_container_width=True
    )

with search_col2:

    st.caption(
        f"Searching TradingView for "
        f"**{exchange_input}:{symbol_input}**"
    )


if search_button:

    try:

        with st.spinner(
            "Searching TradingView symbols..."
        ):

            search_results = tv.search_symbol(
                symbol_input,
                exchange_input
            )

        if not search_results:

            st.warning(
                "⚠️ No TradingView search results found."
            )

        else:

            st.success(
                f"✅ Found {len(search_results)} result(s)"
            )

            st.json(
                search_results
            )

            # ------------------------------------------------
            # Try to show useful symbol fields
            # ------------------------------------------------

            if isinstance(
                search_results,
                list
            ):

                rows = []

                for item in search_results:

                    if not isinstance(
                        item,
                        dict
                    ):
                        continue

                    rows.append({
                        "symbol": item.get(
                            "symbol",
                            ""
                        ),
                        "exchange": item.get(
                            "exchange",
                            ""
                        ),
                        "description": item.get(
                            "description",
                            ""
                        ),
                        "type": item.get(
                            "type",
                            ""
                        ),
                    })

                if rows:

                    st.subheader(
                        "📋 Search Results"
                    )

                    st.dataframe(
                        pd.DataFrame(rows),
                        use_container_width=True
                    )

    except Exception as e:

        st.error(
            "❌ Symbol search failed"
        )

        st.exception(e)


# ============================================================
# FETCH HISTORICAL DATA
# ============================================================

st.divider()

st.subheader(
    "📊 Historical Data"
)

fetch_button = st.button(
    f"🚀 Fetch {exchange_input}:{symbol_input} "
    f"{interval_input} Data",
    type="primary",
    use_container_width=True
)


if fetch_button:

    # ========================================================
    # VALIDATION
    # ========================================================

    if not symbol_input:

        st.error(
            "❌ Symbol cannot be empty."
        )

        st.stop()

    if not exchange_input:

        st.error(
            "❌ Exchange cannot be empty."
        )

        st.stop()


    # ========================================================
    # REQUEST DETAILS
    # ========================================================

    st.info(
        f"Requesting:\n\n"
        f"**Symbol:** `{exchange_input}:{symbol_input}`  \n"
        f"**Interval:** `{interval_input}`  \n"
        f"**Bars:** `{n_bars_input}`  \n"
        f"**Extended:** `{extended_session}`"
    )


    # ========================================================
    # FETCH
    # ========================================================

    try:

        with st.spinner(
            "Connecting to TradingView and fetching data..."
        ):

            # IMPORTANT:
            #
            # interval is intentionally sent as STRING.
            #
            # Example:
            # "5"
            #
            # NOT:
            # Interval.in_5_minute
            #
            df = tv.get_hist(
                symbol=symbol_input,
                exchange=exchange_input,
                interval=str(interval_input),
                n_bars=int(n_bars_input),
                extended_session=extended_session
            )


        # ====================================================
        # NO DATA
        # ====================================================

        if df is None or df.empty:

            st.error(
                "❌ NO DATA"
            )

            st.warning(
                "TradingView did not return candle data."
            )

            st.markdown(
                """
                ### Check these items:

                1. Search the symbol above.
                2. Confirm the TradingView exchange.
                3. Confirm the symbol name.
                4. Check the terminal/log output.
                5. Make sure the loaded `tvDatafeed.py`
                   is the latest file.
                """
            )

            st.stop()


        # ====================================================
        # SUCCESS
        # ====================================================

        st.success(
            f"✅ Data received successfully — "
            f"{len(df):,} candles"
        )


        # ====================================================
        # NORMALIZE COLUMN NAMES
        # ========================================================

        expected_columns = [
            "Datetime",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]

        missing_columns = [
            col
            for col in expected_columns
            if col not in df.columns
        ]

        if missing_columns:

            st.warning(
                "⚠️ Missing expected columns: "
                + ", ".join(missing_columns)
            )

        # ====================================================
        # METRICS
        # ====================================================

        col1, col2, col3, col4 = st.columns(4)

        with col1:

            st.metric(
                "Rows",
                f"{len(df):,}"
            )

        with col2:

            st.metric(
                "Symbol",
                symbol_input
            )

        with col3:

            st.metric(
                "Interval",
                f"{interval_input}"
            )

        with col4:

            st.metric(
                "Exchange",
                exchange_input
            )


        # ====================================================
        # DATE RANGE
        # ====================================================

        if "Datetime" in df.columns:

            try:

                min_dt = df["Datetime"].min()

                max_dt = df["Datetime"].max()

                st.info(
                    f"📅 **Data range:** "
                    f"{min_dt} → {max_dt}"
                )

            except Exception:

                pass


        # ====================================================
        # DATA TYPES
        # ====================================================

        with st.expander(
            "🔧 DataFrame Information"
        ):

            info_col1, info_col2 = st.columns(2)

            with info_col1:

                st.write(
                    "Columns"
                )

                st.write(
                    list(df.columns)
                )

            with info_col2:

                st.write(
                    "Data Types"
                )

                st.dataframe(
                    pd.DataFrame({
                        "Column": df.columns,
                        "dtype": [
                            str(dtype)
                            for dtype in df.dtypes
                        ]
                    }),
                    use_container_width=True
                )


        # ====================================================
        # FIRST 10
        # ====================================================

        st.subheader(
            "🔼 First 10 Candles"
        )

        st.dataframe(
            df.head(10),
            use_container_width=True,
            hide_index=True
        )


        # ====================================================
        # LAST 10
        # ====================================================

        st.subheader(
            "🔽 Last 10 Candles"
        )

        st.dataframe(
            df.tail(10),
            use_container_width=True,
            hide_index=True
        )


        # ====================================================
        # PRICE CHART
        # ====================================================

        if all(
            col in df.columns
            for col in [
                "Datetime",
                "Close"
            ]
        ):

            st.subheader(
                "📈 Close Price"
            )

            chart_df = df[
                ["Datetime", "Close"]
            ].copy()

            chart_df = chart_df.set_index(
                "Datetime"
            )

            st.line_chart(
                chart_df
            )


        # ====================================================
        # FULL DATA
        # ====================================================

        with st.expander(
            f"📊 Show All {len(df):,} Candles"
        ):

            st.dataframe(
                df,
                use_container_width=True,
                height=600,
                hide_index=True
            )


        # ====================================================
        # DOWNLOAD CSV
        # ====================================================

        csv = df.to_csv(
            index=False
        )

        filename = (
            f"{exchange_input}_"
            f"{symbol_input}_"
            f"{interval_input}_"
            f"minute.csv"
        )

        st.download_button(
            label="⬇️ Download CSV",
            data=csv,
            file_name=filename,
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

        st.markdown(
            """
            ### Debug information

            Check the terminal/Streamlit log for:

            - `TradingView symbol`
            - `TradingView interval`
            - `symbol_id`
            - `CREATE_SERIES`
            - `symbol_error`
            - `series_error`
            - `series_completed`
            """
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "TradingView historical data diagnostic test"
)

