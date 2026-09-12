def get_hist(
    self,
    symbol,
    exchange="NSE",
    interval=Interval.in_5_minute,
    n_bars=100,
    fut_contract=None,
    extended_session=False,
):
    symbol = self.__format_symbol(
        symbol=symbol,
        exchange=exchange,
        contract=fut_contract,
    )

    logging.warning("======================================")
    logging.warning("TV REQUEST SYMBOL: %s", symbol)
    logging.warning("TV REQUEST INTERVAL: %s", interval)
    logging.warning("TV FUT CONTRACT: %s", fut_contract)
    logging.warning("======================================")

    self.session = self.__generate_session()
    self.chart_session = self.__generate_chart_session()

    self.ws = create_connection(
        "wss://data.tradingview.com/socket.io/websocket",
        headers=[
            "Origin: https://www.tradingview.com",
            "User-Agent: Mozilla/5.0",
        ],
        timeout=10,
    )

    # Authentication
    self.__send_message(
        "set_auth_token",
        [self.token],
    )

    # Chart session
    self.__send_message(
        "chart_create_session",
        [self.chart_session, ""],
    )

    # Quote session
    self.__send_message(
        "quote_create_session",
        [self.session],
    )

    self.__send_message(
        "quote_set_fields",
        [
            self.session,
            "ch",
            "chp",
            "current_session",
            "description",
            "exchange",
            "fractional",
            "is_tradable",
            "language",
            "local_timezone",
            "lp",
            "lp_time",
            "minmov",
            "minmove2",
            "original_name",
            "pricescale",
            "pro_name",
            "short_name",
            "type",
            "update_mode",
            "volume",
            "currency_code",
        ],
    )

    # IMPORTANT
    self.__send_message(
        "quote_add_symbols",
        [
            self.session,
            symbol,
            {
                "flags": [
                    "force_permission"
                ]
            },
        ],
    )

    self.__send_message(
        "quote_fast_symbols",
        [
            self.session,
            symbol,
        ],
    )

    # Resolve symbol
    symbol_data = {
        "symbol": symbol,
        "adjustment": "splits",
        "session": "extended"
        if extended_session
        else "regular",
    }

    self.__send_message(
        "resolve_symbol",
        [
            self.chart_session,
            "symbol_1",
            "={}".format(json.dumps(symbol_data)),
        ],
    )

    # Create series
    self.__send_message(
        "create_series",
        [
            self.chart_session,
            "s1",
            "s1",
            "symbol_1",
            interval,
            n_bars,
        ],
    )

    self.__send_message(
        "switch_timezone",
        [
            self.chart_session,
            "exchange",
        ],
    )

    # Receive
    raw_data = ""

    try:
        while True:

            response = self.ws.recv()

            if not response:
                continue

            raw_data += response

            logging.warning(
                "TV RESPONSE: %s",
                response[:2000],
            )

            # Critical TradingView errors
            if "critical_error" in response:
                logging.error(
                    "TRADINGVIEW CRITICAL RESPONSE: %s",
                    response,
                )

                # DON'T immediately return.
                # We need to see the complete response.
                continue

            if "series_completed" in response:
                break

            if "protocol_error" in response:
                logging.error(
                    "TRADINGVIEW PROTOCOL ERROR: %s",
                    response,
                )

            if "series_error" in response:
                logging.error(
                    "TRADINGVIEW SERIES ERROR: %s",
                    response,
                )

    except Exception as e:
        logging.error(
            "TradingView receive error: %s",
            e,
        )

    # Parse candles
    try:
        return self.__create_df(raw_data)

    except Exception as e:
        logging.error(
            "Candle parser error: %s",
            e,
        )
        return None
