import os
import json
import logging
import pandas as pd

from tvDatafeed import TvDatafeed, Interval


# ============================================================
# SETTINGS
# ============================================================

USERNAME = os.getenv("TV_USERNAME")
PASSWORD = os.getenv("TV_PASSWORD")

# If using Streamlit secrets, don't use this file directly.
# Put your credentials in environment variables.


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# ============================================================
# TEST
# ============================================================

def main():

    print("\n========================================")
    print(" TradingView Historical Data Test")
    print("========================================\n")

    if not USERNAME:
        print("❌ TV_USERNAME not found")
        return

    if not PASSWORD:
        print("❌ TV_PASSWORD not found")
        return

    print("✅ Username found")
    print("✅ Password found")
    print()

    try:

        print("Connecting to TradingView...")

        tv = TvDatafeed(
            username=USERNAME,
            password=PASSWORD
        )

        print("✅ TradingView connection created")
        print()

    except Exception as e:

        print("❌ TradingView connection failed")
        print(type(e).__name__)
        print(str(e))

        return


    # ========================================================
    # TEST SBIN
    # ========================================================

    symbol = "SBIN"
    exchange = "NSE"

    print("----------------------------------------")
    print("Testing:")
    print(f"Symbol   : {symbol}")
    print(f"Exchange : {exchange}")
    print("Interval : 5 minute")
    print("Contract : None")
    print("----------------------------------------")

    try:

        df = tv.get_hist(
            symbol=symbol,
            exchange=exchange,
            interval=Interval.in_5_minute,
            n_bars=100,
            fut_contract=None,
            extended_session=False,
        )

    except Exception as e:

        print("\n❌ get_hist() FAILED")
        print()
        print("Error type:")
        print(type(e).__name__)
        print()
        print("Error:")
        print(str(e))

        return


    # ========================================================
    # RESULT
    # ========================================================

    print("\n========================================")

    if df is None:

        print("❌ RESULT: None")
        print("TradingView returned no dataframe.")

        return

    if df.empty:

        print("❌ RESULT: EMPTY DATAFRAME")
        print("TradingView returned an empty dataframe.")

        return


    print("✅ HISTORICAL DATA RECEIVED")
    print("========================================")

    print()
    print("Rows:", len(df))
    print("Columns:", list(df.columns))

    print("\nLast 10 candles:")
    print(df.tail(10))

    print("\nData types:")
    print(df.dtypes)

    print("\n========================================")
    print("TEST PASSED ✅")
    print("========================================")


if __name__ == "__main__":
    main()
