import enum
import json
import logging
import random
import re
import string
import datetime

import pandas as pd
import pytz
import requests
import streamlit as st

from websocket import create_connection


# ============================================================
# INTERVAL
# ============================================================

class Interval(enum.Enum):

    in_30_minute = "30"
    in_1_minute = "1"
    in_3_minute = "3"
    in_5_minute = "5"
    in_15_minute = "15"
    in_45_minute = "45"

    in_1_hour = "1H"
    in_2_hour = "2H"
    in_3_hour = "3H"
    in_4_hour = "4H"

    in_daily = "1D"
    in_weekly = "1W"
    in_monthly = "1M"


# ============================================================
# TRADINGVIEW DATAFEED
# ============================================================

class TvDatafeed:

    __sign_in_url = (
        "https://www.tradingview.com/accounts/signin/"
    )

    __search_url = (
        "https://symbol-search.tradingview.com/"
        "symbol_search/?text={}&hl=1&exchange={}"
        "&lang=en&type=&domain=production"
    )

    __ws_url = (
        "wss://data.tradingview.com/socket.io/websocket"
    )

    __signin_headers = {
        "Referer": "https://www.tradingview.com"
    }

    __ws_timeout = 10


    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        username: str = None,
        password: str = None,
        token: str = None
    ) -> None:

        self.ws_debug = False

        self.ws = None

        # ----------------------------------------------------
        # AUTH
        # ----------------------------------------------------

        if token:

            self.token = token

        elif username and password:

            self.token = self.__auth(
                username,
                password
            )

        else:

            self.token = None

        # Anonymous token
        if not self.token:

            self.token = (
                "unauthorized_user_token"
            )

        # ----------------------------------------------------
        # SESSIONS
        # ----------------------------------------------------

        self.session = (
            self.__generate_session()
        )

        self.chart_session = (
            self.__generate_chart_session()
        )


    # ========================================================
    # AUTHENTICATION
    # ========================================================

    def __auth(
        self,
        username,
        password
    ):

        data = {
            "username": username,
            "password": password,
            "remember": "on"
        }

        try:

            response = requests.post(
                url=self.__sign_in_url,
                data=data,
                headers=self.__signin_headers,
                timeout=15
            )

            response.raise_for_status()

            result = response.json()

            token = (
                result
                .get("user", {})
                .get("auth_token")
            )

            if token:

                logging.info(
                    "TradingView login successful"
                )

            return token

        except Exception as e:

            logging.error(
                "TradingView authentication failed: %s",
                e
            )

            return None


    # ========================================================
    # CREATE WEBSOCKET
    # ========================================================

    def __create_connection(self):

        logging.debug(
            "Creating TradingView websocket"
        )

        self.ws = create_connection(
            self.__ws_url,
            header=[
                "Origin: https://data.tradingview.com"
            ],
            timeout=self.__ws_timeout
        )


    # ========================================================
    # CLOSE WEBSOCKET
    # ========================================================

    def __close_connection(self):

        try:

            if self.ws:

                self.ws.close()

        except Exception:

            pass

        finally:

            self.ws = None


    # ========================================================
    # GENERATE SESSION
    # ========================================================

    @staticmethod
    def __generate_session():

        string_length = 12

        letters = (
            string.ascii_lowercase
        )

        random_string = "".join(
            random.choice(letters)
            for _ in range(string_length)
        )

        return "qs_" + random_string


    @staticmethod
    def __generate_chart_session():

        string_length = 12

        letters = (
            string.ascii_lowercase
        )

        random_string = "".join(
            random.choice(letters)
            for _ in range(string_length)
        )

        return "cs_" + random_string


    # ========================================================
    # MESSAGE HEADER
    # ========================================================

    @staticmethod
    def __prepend_header(message):

        return (
            "~m~"
            + str(len(message))
            + "~m~"
            + message
        )


    # ========================================================
    # CREATE MESSAGE
    # ========================================================

    @staticmethod
    def __construct_message(
        func,
        param_list
    ):

        return json.dumps(
            {
                "m": func,
                "p": param_list
            },
            separators=(",", ":")
        )


    def __create_message(
        self,
        func,
        param_list
    ):

        message = (
            self.__construct_message(
                func,
                param_list
            )
        )

        return (
            self.__prepend_header(
                message
            )
        )


    # ========================================================
    # SEND MESSAGE
    # ========================================================

    def __send_message(
        self,
        func,
        args
    ):

        message = (
            self.__create_message(
                func,
                args
            )
        )

        if self.ws_debug:

            print(message)

        self.ws.send(message)


    # ========================================================
    # FORMAT SYMBOL
    # ========================================================

    @staticmethod
    def __format_symbol(
        symbol,
        exchange,
        contract=None
    ):

        symbol = (
            str(symbol)
            .upper()
            .strip()
        )

        exchange = (
            str(exchange)
            .upper()
            .strip()
        )

        # Already formatted
        if ":" in symbol:

            return symbol

        # Cash / Equity
        if contract is None:

            return (
                f"{exchange}:{symbol}"
            )

        # Futures
        if isinstance(
            contract,
            int
        ):

            return (
                f"{exchange}:{symbol}{contract}!"
            )

        raise ValueError(
            "contract must be None or integer"
        )


    # ========================================================
    # CREATE DATAFRAME
    # ========================================================

    @staticmethod
    def __create_df(
        raw_data,
        symbol
    ):

        empty_columns = [
            "symbol",
            "Datetime",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume"
        ]

        try:

            # ------------------------------------------------
            # Find candle series
            # ------------------------------------------------

            match = re.search(
                r'"s":\[(.*?)\]',
                raw_data,
                re.DOTALL
            )

            if not match:

                logging.warning(
                    "No candle series found for %s",
                    symbol
                )

                return pd.DataFrame(
                    columns=empty_columns
                )

            series_data = (
                match.group(1)
            )

            # ------------------------------------------------
            # Find candle nodes
            # ------------------------------------------------

            nodes = re.findall(
                r'\{.*?"i":(.*?),"v":\[(.*?)\]\}',
                series_data,
                re.DOTALL
            )

            rows = []

            ist_tz = pytz.timezone(
                "Asia/Kolkata"
            )

            # ------------------------------------------------
            # Parse candles
            # ------------------------------------------------

            for node in nodes:

                values_text = node[1]

                try:

                    values = json.loads(
                        "["
                        + values_text
                        + "]"
                    )

                except Exception:

                    continue

                if len(values) < 5:

                    continue

                try:

                    timestamp = float(
                        values[0]
                    )

                    dt_utc = (
                        datetime.datetime
                        .fromtimestamp(
                            timestamp,
                            tz=pytz.utc
                        )
                    )

                    dt_ist = (
                        dt_utc
                        .astimezone(
                            ist_tz
                        )
                    )

                    open_price = float(
                        values[1]
                    )

                    high_price = float(
                        values[2]
                    )

                    low_price = float(
                        values[3]
                    )

                    close_price = float(
                        values[4]
                    )

                    if (
                        len(values)
                        > 5
                    ):

                        try:

                            volume = float(
                                values[5]
                            )

                        except Exception:

                            volume = 0.0

                    else:

                        volume = 0.0

                    rows.append(
                        [
                            dt_ist,
                            open_price,
                            high_price,
                            low_price,
                            close_price,
                            volume
                        ]
                    )

                except Exception:

                    continue

            # ------------------------------------------------
            # No rows
            # ------------------------------------------------

            if not rows:

                logging.warning(
                    "No parsed candle data for %s",
                    symbol
                )

                return pd.DataFrame(
                    columns=empty_columns
                )

            # ------------------------------------------------
            # DataFrame
            # ------------------------------------------------

            df = pd.DataFrame(
                rows,
                columns=[
                    "Datetime",
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Volume"
                ]
            )

            df.insert(
                0,
                "symbol",
                symbol
            )

            # ------------------------------------------------
            # Clean
            # ------------------------------------------------

            df["Datetime"] = (
                pd.to_datetime(
                    df["Datetime"],
                    errors="coerce"
                )
            )

            for col in [
                "Open",
                "High",
                "Low",
                "Close",
                "Volume"
            ]:

                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce"
                )

            df = df.dropna(
                subset=[
                    "Datetime",
                    "Open",
                    "High",
                    "Low",
                    "Close"
                ]
            )

            df = (
                df
                .drop_duplicates(
                    subset=[
                        "Datetime"
                    ]
                )
                .sort_values(
                    "Datetime"
                )
                .reset_index(
                    drop=True
                )
            )

            return df

        except Exception as e:

            logging.error(
                "TradingView dataframe error "
                "for %s: %s",
                symbol,
                e
            )

            return pd.DataFrame(
                columns=empty_columns
            )


    # ========================================================
    # GET HISTORICAL DATA
    # ========================================================

    def get_hist(
        self,
        symbol: str,
        exchange: str = "NSE",
        interval: Interval = Interval.in_daily,
        n_bars: int = 10,
        fut_contract: int = None,
        extended_session: bool = False,
    ) -> pd.DataFrame:

        # ----------------------------------------------------
        # Validate interval
        # ----------------------------------------------------

        if not isinstance(
            interval,
            Interval
        ):

            raise ValueError(
                "interval must be an Interval enum"
            )

        # ----------------------------------------------------
        # Limit bars
        # ----------------------------------------------------

        n_bars = min(
            int(n_bars),
            5000
        )

        if n_bars <= 0:

            raise ValueError(
                "n_bars must be greater than 0"
            )

        # ----------------------------------------------------
        # Format symbol
        # ----------------------------------------------------

        tv_symbol = (
            self.__format_symbol(
                symbol=symbol,
                exchange=exchange,
                contract=fut_contract
            )
        )

        interval_value = (
            interval.value
        )

        logging.info(
            "Fetching %s | interval=%s | bars=%s",
            tv_symbol,
            interval_value,
            n_bars
        )

        raw_data = ""

        # ----------------------------------------------------
        # New websocket
        # ----------------------------------------------------

        self.__close_connection()

        self.__create_connection()

        try:

            # =================================================
            # AUTH
            # =================================================

            self.__send_message(
                "set_auth_token",
                [
                    self.token
                ]
            )

            # =================================================
            # CHART SESSION
            # =================================================

            self.chart_session = (
                self.__generate_chart_session()
            )

            self.__send_message(
                "chart_create_session",
                [
                    self.chart_session,
                    ""
                ]
            )

            # =================================================
            # QUOTE SESSION
            #
            # IMPORTANT:
            # This was present in your old working code.
            # =================================================

            self.session = (
                self.__generate_session()
            )

            self.__send_message(
                "quote_create_session",
                [
                    self.session
                ]
            )

            # =================================================
            # QUOTE FIELDS
            # =================================================

            self.__send_message(
                "quote_set_fields",
                [
                    self.session,
                    "ch",
                    "chp",
                    "current_session",
                    "description",
                    "local_description",
                    "language",
                    "exchange",
                    "fractional",
                    "is_tradable",
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
                    "rchp",
                    "rtc",
                ]
            )

            # =================================================
            # ADD SYMBOL
            #
            # IMPORTANT:
            # force_permission is the key part from your
            # previously working code.
            # =================================================

            self.__send_message(
                "quote_add_symbols",
                [
                    self.session,
                    tv_symbol,
                    {
                        "flags": [
                            "force_permission"
                        ]
                    }
                ]
            )

            # =================================================
            # FAST SYMBOL
            # =================================================

            self.__send_message(
                "quote_fast_symbols",
                [
                    self.session,
                    tv_symbol
                ]
            )

            # =================================================
            # RESOLVE SYMBOL
            # =================================================

            session_type = (
                "extended"
                if extended_session
                else "regular"
            )

            symbol_data = json.dumps(
                {
                    "symbol": tv_symbol,
                    "adjustment": "splits",
                    "session": session_type
                },
                separators=(",", ":")
            )

            self.__send_message(
                "resolve_symbol",
                [
                    self.chart_session,
                    "symbol_1",
                    "=" + symbol_data
                ]
            )

            # =================================================
            # CREATE SERIES
            # =================================================

            self.__send_message(
                "create_series",
                [
                    self.chart_session,
                    "s1",
                    "s1",
                    "symbol_1",
                    interval_value,
                    n_bars
                ]
            )

            # =================================================
            # TIMEZONE
            # =================================================

            self.__send_message(
                "switch_timezone",
                [
                    self.chart_session,
                    "exchange"
                ]
            )

            # =================================================
            # RECEIVE DATA
            # =================================================

            while True:

                try:

                    result = self.ws.recv()

                except Exception as e:

                    logging.error(
                        "TradingView websocket "
                        "receive error: %s",
                        e
                    )

                    break

                if not result:

                    continue

                raw_data += (
                    result
                    + "\n"
                )

                result_lower = (
                    result.lower()
                )

                # ------------------------------------------------
                # TradingView errors
                # ------------------------------------------------

                if (
                    "permission denied"
                    in result_lower
                ):

                    logging.error(
                        "TradingView permission denied "
                        "for %s",
                        tv_symbol
                    )

                    break

                if (
                    "symbol_error"
                    in result_lower
                ):

                    logging.error(
                        "TradingView symbol error "
                        "for %s",
                        tv_symbol
                    )

                    break

                if (
                    "critical_error"
                    in result_lower
                ):

                    logging.error(
                        "TradingView critical error "
                        "for %s",
                        tv_symbol
                    )

                    break

                if (
                    "series_error"
                    in result_lower
                ):

                    logging.error(
                        "TradingView series error "
                        "for %s",
                        tv_symbol
                    )

                    break

                # ------------------------------------------------
                # Finished
                # ------------------------------------------------

                if (
                    "series_completed"
                    in result
                ):

                    break

            # =================================================
            # PARSE
            # =================================================

            df = self.__create_df(
                raw_data,
                tv_symbol
            )

            if df.empty:

                logging.warning(
                    "No candle data found for %s",
                    tv_symbol
                )

            return df

        finally:

            self.__close_connection()


    # ========================================================
    # SEARCH SYMBOL
    # ========================================================

    def search_symbol(
        self,
        text: str,
        exchange: str = ""
    ):

        url = (
            self.__search_url.format(
                text,
                exchange
            )
        )

        try:

            response = requests.get(
                url,
                timeout=15
            )

            response.raise_for_status()

            data = (
                response.text
                .replace("</em>", "")
                .replace("<em>", "")
            )

            return json.loads(
                data
            )

        except Exception as e:

            logging.error(
                "Symbol search error: %s",
                e
            )

            return []


    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        self.__close_connection()
