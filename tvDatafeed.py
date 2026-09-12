
# ============================================================
# tvDatafeed.py
# TradingView Historical Data Feed
# ============================================================

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
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO
)


# ============================================================
# INTERVAL ENUM
# ============================================================

class Interval(enum.Enum):

    in_1_minute = "1"
    in_3_minute = "3"
    in_5_minute = "5"
    in_15_minute = "15"
    in_30_minute = "30"
    in_45_minute = "45"

    in_1_hour = "1H"
    in_2_hour = "2H"
    in_3_hour = "3H"
    in_4_hour = "4H"

    in_daily = "1D"
    in_weekly = "1W"
    in_monthly = "1M"


# ============================================================
# TV DATAFEED
# ============================================================

class TvDatafeed:

    # --------------------------------------------------------
    # URLs
    # --------------------------------------------------------

    __sign_in_url = (
        "https://www.tradingview.com/accounts/signin/"
    )

    __search_url = (
        "https://symbol-search.tradingview.com/"
        "symbol_search/?text={}&hl=1&exchange={}"
        "&lang=en&type=&domain=production"
    )

    # --------------------------------------------------------
    # Headers
    # --------------------------------------------------------

    __ws_headers = json.dumps(
        {
            "Origin": "https://data.tradingview.com"
        }
    )

    __signin_headers = {
        "Referer": "https://www.tradingview.com"
    }

    # --------------------------------------------------------
    # Websocket timeout
    # --------------------------------------------------------

    __ws_timeout = 15


    # ========================================================
    # INITIALIZE
    # ========================================================

    def __init__(
        self,
        username: str = None,
        password: str = None,
        token: str = None
    ) -> None:

        self.ws_debug = False

        # ----------------------------------------------------
        # Authentication
        # ----------------------------------------------------

        if token:

            self.token = token

        else:

            self.token = self.__auth(
                username,
                password
            )

        # ----------------------------------------------------
        # Anonymous TradingView token
        # ----------------------------------------------------

        if self.token is None:

            self.token = (
                "unauthorized_user_token"
            )

        # ----------------------------------------------------
        # Websocket
        # ----------------------------------------------------

        self.ws = None

        # ----------------------------------------------------
        # Sessions
        # ----------------------------------------------------

        self.session = (
            self.__generate_session()
        )

        self.chart_session = (
            self.__generate_chart_session()
        )


    # ========================================================
    # AUTH
    # ========================================================

    def __auth(
        self,
        username,
        password
    ):

        if (
            username is None
            or password is None
        ):

            return None

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

            token = response.json()["user"]["auth_token"]

            return token

        except Exception as e:

            logging.warning(
                "TradingView login failed: %s",
                e
            )

            return None


    # ========================================================
    # CREATE WEBSOCKET CONNECTION
    # ========================================================

    def __create_connection(self):

        logging.info(
            "Creating TradingView websocket connection..."
        )

        self.ws = create_connection(
            "wss://data.tradingview.com/socket.io/websocket",
            headers=self.__ws_headers,
            timeout=self.__ws_timeout
        )

        logging.info(
            "TradingView websocket connected"
        )


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
    # CONSTRUCT MESSAGE
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


    # ========================================================
    # CREATE MESSAGE
    # ========================================================

    def __create_message(
        self,
        func,
        param_list
    ):

        message = self.__construct_message(
            func,
            param_list
        )

        return self.__prepend_header(
            message
        )


    # ========================================================
    # SEND MESSAGE
    # ========================================================

    def __send_message(
        self,
        func,
        args
    ):

        message = self.__create_message(
            func,
            args
        )

        if self.ws_debug:

            logging.info(
                "TV SEND: %s",
                message
            )

        self.ws.send(message)


    # ========================================================
    # GENERATE SESSION
    # ========================================================

    @staticmethod
    def __generate_session():

        length = 12

        letters = string.ascii_lowercase

        random_string = "".join(
            random.choice(letters)
            for _ in range(length)
        )

        return "qs_" + random_string


    # ========================================================
    # GENERATE CHART SESSION
    # ========================================================

    @staticmethod
    def __generate_chart_session():

        length = 12

        letters = string.ascii_lowercase

        random_string = "".join(
            random.choice(letters)
            for _ in range(length)
        )

        return "cs_" + random_string


    # ========================================================
    # FORMAT SYMBOL
    # ========================================================

    @staticmethod
    def __format_symbol(
        symbol,
        exchange,
        contract=None
    ):

        # Already formatted
        if ":" in symbol:

            return symbol

        # Cash / normal symbol
        if contract is None:

            return (
                f"{exchange}:{symbol}"
            )

        # Futures
        if isinstance(contract, int):

            return (
                f"{exchange}:{symbol}{contract}!"
            )

        raise ValueError(
            "not a valid contract"
        )


    # ========================================================
    # CREATE DATAFRAME
    # ========================================================

    @staticmethod
    def __create_df(
        raw_data,
        symbol
    ):

        try:

            # ------------------------------------------------
            # Find candle series
            # ------------------------------------------------

            match = re.search(
                r'"s":\[(.+?)\}\]',
                raw_data,
                re.DOTALL
            )

            if not match:

                logging.warning(
                    "No candle series found for %s",
                    symbol
                )

                return pd.DataFrame()

            out = match.group(1)

            # ------------------------------------------------
            # Split candles
            # ------------------------------------------------

            rows = out.split(
                ',{"'
            )

            data = []

            ist_tz = pytz.timezone(
                "Asia/Kolkata"
            )

            # ------------------------------------------------
            # Parse candles
            # ------------------------------------------------

            for row in rows:

                try:

                    parts = re.split(
                        r"\[|:|,|\]",
                        row
                    )

                    # Timestamp
                    timestamp = float(
                        parts[4]
                    )

                    ts = datetime.datetime.fromtimestamp(
                        timestamp,
                        tz=pytz.utc
                    )

                    ts_ist = (
                        ts.astimezone(ist_tz)
                    )

                    # OHLC
                    open_price = float(
                        parts[5]
                    )

                    high_price = float(
                        parts[6]
                    )

                    low_price = float(
                        parts[7]
                    )

                    close_price = float(
                        parts[8]
                    )

                    # Volume
                    try:

                        volume = float(
                            parts[9]
                        )

                    except (
                        ValueError,
                        IndexError
                    ):

                        volume = 0.0

                    data.append(
                        [
                            ts_ist,
                            open_price,
                            high_price,
                            low_price,
                            close_price,
                            volume
                        ]
                    )

                except (
                    ValueError,
                    IndexError,
                    TypeError
                ):

                    continue

            # ------------------------------------------------
            # No parsed rows
            # ------------------------------------------------

            if not data:

                logging.warning(
                    "No parsed candle data for %s",
                    symbol
                )

                return pd.DataFrame()

            # ------------------------------------------------
            # DataFrame
            # ------------------------------------------------

            df = pd.DataFrame(
                data,
                columns=[
                    "Datetime",
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Volume"
                ]
            )

            # ------------------------------------------------
            # Symbol
            # ------------------------------------------------

            df.insert(
                0,
                "symbol",
                symbol
            )

            # ------------------------------------------------
            # Sort
            # ------------------------------------------------

            df = df.sort_values(
                "Datetime"
            ).reset_index(
                drop=True
            )

            return df

        except Exception as e:

            logging.exception(
                "DataFrame parsing error: %s",
                e
            )

            return pd.DataFrame()


    # ========================================================
    # GET HISTORICAL DATA
    # ========================================================

    def get_hist(
        self,
        symbol: str,
        exchange: str = "NSE",
        interval=Interval.in_daily,
        n_bars: int = 10,
        fut_contract: int = None,
        extended_session: bool = False
    ) -> pd.DataFrame:

        # ====================================================
        # FORMAT SYMBOL
        # ====================================================

        symbol = self.__format_symbol(
            symbol=symbol,
            exchange=exchange,
            contract=fut_contract
        )

        logging.info(
            "TradingView symbol = %s",
            symbol
        )

        # ====================================================
        # INTERVAL CONVERSION
        # ====================================================

        logging.info(
            "INPUT interval = %r | type = %s",
            interval,
            type(interval)
        )

        if isinstance(
            interval,
            Interval
        ):

            interval_value = interval.value

        else:

            interval_value = interval

        # ----------------------------------------------------
        # FINAL STRING
        # ----------------------------------------------------

        interval_value = str(
            interval_value
        )

        logging.info(
            "FINAL interval_value = %r | type = %s",
            interval_value,
            type(interval_value)
        )

        # ====================================================
        # VALID INTERVALS
        # ====================================================

        valid_intervals = {
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
            "1D",
            "1W",
            "1M"
        }

        if interval_value not in valid_intervals:

            raise ValueError(
                "Invalid TradingView interval: "
                f"{interval_value!r}"
            )

        # ====================================================
        # CREATE CONNECTION
        # ====================================================

        self.__create_connection()

        # ====================================================
        # AUTH TOKEN
        # ====================================================

        self.__send_message(
            "set_auth_token",
            [
                self.token
            ]
        )

        # ====================================================
        # CHART SESSION
        # ====================================================

        self.__send_message(
            "chart_create_session",
            [
                self.chart_session,
                ""
            ]
        )

        # ============================================================
        # RESOLVE SYMBOL 
        # ============================================================ 
        session_type = ( "extended" if extended_session else "regular" ) 
        symbol_id = "sds_sym_1" 
        symbol_payload = ( '={"symbol":"' + symbol + '","adjustment":"splits","session":"' + session_type + '"}' )
        logging.info( "TradingView resolving symbol = %s", symbol ) 
        logging.info( "TradingView symbol payload = %s", symbol_payload ) 
        self.__send_message( "resolve_symbol", [ self.chart_session, symbol_id, symbol_payload ] )
        
        # ====================================================
        # CREATE SERIES
        # ====================================================

        logging.info(
            "CREATE_SERIES interval = %r",
            interval_value
        )

        # IMPORTANT:
        # interval_value is explicitly used.
        # Original Enum is NEVER sent.

        create_series_args = [
            self.chart_session,
            "sds_1",
            "s1",
            symbol_id,
            interval_value,
            int(n_bars)
        ]

        logging.info(
            "CREATE_SERIES args = %r",
            create_series_args
        )

        self.__send_message(
            "create_series",
            create_series_args
        )

        # ====================================================
        # TIMEZONE
        # ====================================================

        self.__send_message(
            "switch_timezone",
            [
                self.chart_session,
                "exchange"
            ]
        )

        # ====================================================
        # RECEIVE DATA
        # ====================================================

        raw_data = ""

        while True:

            try:

                result = self.ws.recv()

            except Exception as e:

                logging.exception(
                    "TradingView websocket receive error"
                )

                break

            raw_data += (
                result
                + "\n"
            )

            # ------------------------------------------------
            # DEBUG
            # ------------------------------------------------

            if self.ws_debug:

                logging.info(
                    "TV RECEIVE: %s",
                    result
                )

            # ------------------------------------------------
            # Critical error
            # ------------------------------------------------

            if "critical_error" in result:

                logging.error(
                    "TradingView critical error: %s",
                    result
                )

                break

            # ------------------------------------------------
            # Series error
            # ------------------------------------------------

            if "series_error" in result:

                logging.error(
                    "TradingView series error: %s",
                    result
                )

                break

            # ------------------------------------------------
            # Completed
            # ------------------------------------------------

            if "series_completed" in result:

                logging.info(
                    "TradingView series completed"
                )

                break

        # ====================================================
        # CLOSE SOCKET
        # ====================================================

        try:

            if self.ws:

                self.ws.close()

        except Exception:

            pass

        # ====================================================
        # CREATE DATAFRAME
        # ====================================================

        df = self.__create_df(
            raw_data,
            symbol
        )

        return df


    # ========================================================
    # SEARCH SYMBOL
    # ========================================================

    def search_symbol(
        self,
        text: str,
        exchange: str = ""
    ):

        url = self.__search_url.format(
            text,
            exchange
        )

        try:

            response = requests.get(
                url,
                timeout=15
            )

            response.raise_for_status()

            return json.loads(
                response.text
                .replace("</em>", "")
                .replace("<em>", "")
            )

        except Exception as e:

            logging.exception(
                "Symbol search error: %s",
                e
            )

            return []



