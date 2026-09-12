


for symbol in ["SBIN", "ADANIPORTS", "APOLLOHOSP"]:
    print("TEST:", symbol)

    df = tv.get_hist(
        symbol=symbol,
        exchange="NSE",
        interval="5",
        n_bars=500,
        extended_session=False
    )

st.write(df.head() if df is not None else "NO DATA")

