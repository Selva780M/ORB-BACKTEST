import os
import streamlit as st

from tvDatafeed import TvDatafeed, Interval


@st.cache_resource
def create_tv_connection():

    token = st.secrets.get(
        "TV_TOKEN",
        None
    )

    username = st.secrets.get(
        "TV_USERNAME",
        None
    )

    password = st.secrets.get(
        "TV_PASSWORD",
        None
    )

    # Environment fallback
    if not token:
        token = os.getenv("TV_TOKEN")

    if not username:
        username = os.getenv("TV_USERNAME")

    if not password:
        password = os.getenv("TV_PASSWORD")

    # --------------------------------------------------------
    # TOKEN
    # --------------------------------------------------------

    if token:

        return TvDatafeed(
            token=token
        )

    # --------------------------------------------------------
    # USERNAME + PASSWORD
    # --------------------------------------------------------

    if username and password:

        return TvDatafeed(
            username=username,
            password=password
        )

    raise RuntimeError(
        "TradingView credentials not found"
    )




st.title("📈 TradingView Test")

symbol = st.sidebar.text_input(
    "Symbol",
    "SBIN"
).strip().upper()

exchange = st.sidebar.text_input(
    "Exchange",
    "NSE"
).strip().upper()

interval_text = st.sidebar.selectbox(
    "Interval",
    [
        "1",
        "3",
        "5",
        "15",
        "30",
        "1H",
        "1D"
    ],
    index=2
)

n_bars = st.sidebar.number_input(
    "No of Bars",
    min_value=1,
    max_value=5000,
    value=100
)


if st.sidebar.button(
    "🚀 Fetch Data",
    type="primary"
):

    try:

        tv = create_tv_connection()

        st.info(
            f"Requesting {exchange}:{symbol}"
        )

        data = tv.get_hist(

            symbol=symbol,

            exchange=exchange,

            interval=Interval(
                interval_text
            ),

            n_bars=int(n_bars),

            # CASH STOCK
            fut_contract=None,

            extended_session=False
        )

        if data is None or data.empty:

            st.error(
                f"❌ No data returned for "
                f"{exchange}:{symbol}"
            )

        else:

            st.success(
                f"✅ Received {len(data)} candles"
            )

            st.write(
                "Columns:",
                list(data.columns)
            )

            st.dataframe(
                data,
                use_container_width=True,
                height=500
            )

            st.write(
                "Latest candle:"
            )

            st.write(
                data.iloc[-1]
            )

    except Exception as e:

        st.error(
            "TradingView error"
        )

        st.exception(e)
