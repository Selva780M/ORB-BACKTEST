# ============================================================
# STREAMLIT TEST
# ============================================================

import streamlit as st
import tvDatafeed

from tvDatafeed import TvDatafeed, Interval


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
# DEBUG - SHOW IMPORTED FILE
# ============================================================

st.info(
    f"tvDatafeed loaded from:\n\n"
    f"`{tvDatafeed.__file__}`"
)

st.write(
    "Interval test:",
    Interval.in_5_minute,
    "→",
    Interval.in_5_minute.value
)
