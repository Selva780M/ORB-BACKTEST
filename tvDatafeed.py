# ============================================================
# tvDatafeed.py
# TradingView WebSocket Historical Data
# NSE / BSE / Futures
# ============================================================

import enum
import json
import logging
import random
import re
import string
import datetime

import requests
import pandas as pd
import pytz

from websocket import create_connection


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(message)s"
)


# ============================================================
# INTERVAL
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

    __ws_url = (
        "wss://data.tradingview.com/socket.io/websocket"
    )

    # --------------------------------------------------------
    # Headers
    # --------------------------------------------------------

    __signin_headers = {
        "Referer": "https://www.tradingview.com/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/153.0.0.0 Safari/537.36"
        )
    }

    # --------------------------------------------------------
    # Default timeout
    # --------------------------------------------------------

    __ws_timeout = 15

    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        username: str = None,
        password: str = None,
        token: str = None,
        timeout: int = 15
    ):

        self.ws_debug = False

        self.ws = None

        self.__ws_timeout = timeout

        # ----------------------------------------------------
        # Authentication
        # ----------------------------------------------------

        if token:

            self.token = token

        elif username and password:

            self.token = self.__auth(
                username,
                password
            )

        else:

            self.token = "unauthorized_user_token"

        # ----------------------------------------------------
        # Sessions
        # ----------------------------------------------------

        self.session = self.__generate_session()

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

        if not username or not password:

            return None

        data = {
            "username": username,
            "password": password,
            "remember": "on"
        }

        try:

            response = requests.post(
                self.__sign_in_url,
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
                    "TradingView authentication successful"
                )

            else:

                logging.error(
                    "TradingView authentication failed"
                )

            return token

        except Exception as e:

            logging.error(
                "TradingView authentication error: %s",
                e
            )

            return None

    # ========================================================
    # CREATE WEBSOCKET
    # ========================================================

    def __create_connection(self):

        logging.debug(
            "Creating TradingView WebSocket"
        )

        self.ws = create_connection(
            self.__ws_url,
            origin="https://data.tradingview.com",
            timeout=self.__ws_timeout
        )

    # ========================================================
    # CLOSE WEBSOCKET
    # ========================================================

    def __close_connection(self):

        try:

            if self.ws is not None:

                self.ws.close()

        except Exception:

            pass

        finally:

            self.ws = None

    # ========================================================
    # GENERATE QUOTE SESSION
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
        params
    ):

        return json.dumps(
            {
                "m": func,
                "p": params
            },
            separators=(",", ":")
        )

    # ========================================================
    # CREATE FINAL MESSAGE
    # ========================================================

    def __create_message(
        self,
        func,
        params
    ):

        message = self.__construct_message(
            func,
            params
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
        params
    ):

        message = self.__create_message(
            func,
            params
        )

        if self.ws_debug:

            print(
                "\nSEND:",
                message
            )

        self.ws.send(
            message
        )

    # ========================================================
    # FORMAT SYMBOL
    # ========================================================

    @staticmethod
    def __format_symbol(
        symbol,
        exchange,
        contract=None
    ):

        symbol = str(
            symbol
        ).strip().upper()

        exchange = str(
            exchange
        ).strip().upper()

        # ----------------------------------------------------
        # Already formatted
        # ----------------------------------------------------

        if ":" in symbol:

            return symbol

        # ----------------------------------------------------
        # Futures
        # ----------------------------------------------------

        if contract is not None:

            if not isinstance(
                contract,
                int
            ):

                raise ValueError(
                    "fut_contract must be an integer"
                )

            return (
                f"{exchange}:{symbol}{contract}!"
            )

        # ----------------------------------------------------
        # Equity
        # ----------------------------------------------------

        return (
            f"{exchange}:{symbol}"
        )

    # ========================================================
    # PARSE TRADINGVIEW RAW DATA
    # ========================================================

    @staticmethod
    def __create_df(
        raw_data,
        symbol
    ):

        columns = [
            "symbol",
            "datetime",
            "open",
            "high",
            "low",
            "close",
            "volume"
        ]

        # ----------------------------------------------------
        # Empty response
        # ----------------------------------------------------

        if not raw_data:

            logging.warning(
                "Empty TradingView response for %s",
                symbol
            )

            return pd.DataFrame(
                columns=columns
            )

        try:

            rows = []

            ist = pytz.timezone(
                "Asia/Kolkata"
            )

            # ------------------------------------------------
            # TradingView response contains:
            #
            # "node":{...}
            # "s":[
            #     {
            #         "i":0,
            #         "v":[timestamp,open,high,low,close,volume]
            #     }
            # ]
            # ------------------------------------------------

            matches = re.findall(
                r'"s":\[(.*?)\]',
                raw_data,
                re.DOTALL
            )

            # ------------------------------------------------
            # Parse every series block
            # ------------------------------------------------

            for block in matches:

                node_matches = re.findall(
                    r'"i":(\d+),"v":(\[.*?\])',
                    block,
                    re.DOTALL
                )

                for _, values_text in node_matches:

                    try:

                        values = json.loads(
                            values_text
                        )

                    except Exception:

                        continue

                    if not values:
                        continue

                    if len(values) < 5:
                        continue

                    # ----------------------------------------
                    # Timestamp
                    # ----------------------------------------

                    timestamp = values[0]

                    if timestamp is None:
                        continue

                    try:

                        timestamp = float(
                            timestamp
                        )

                    except Exception:

                        continue

                    # ----------------------------------------
                    # Datetime
                    # ----------------------------------------

                    dt = (
                        datetime.datetime
                        .fromtimestamp(
                            timestamp,
                            tz=pytz.utc
                        )
                        .astimezone(ist)
                    )

                    # ----------------------------------------
                    # OHLC
                    # ----------------------------------------

                    try:

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

                    except Exception:

                        continue

                    # ----------------------------------------
                    # Volume
                    # ----------------------------------------

                    volume = 0.0

                    if len(values) >= 6:

                        try:

                            if values[5] is not None:

                                volume = float(
                                    values[5]
                                )

                        except Exception:

                            volume = 0.0

                    rows.append(
                        [
                            symbol,
                            dt,
                            open_price,
                            high_price,
                            low_price,
                            close_price,
                            volume
                        ]
                    )

            # ------------------------------------------------
            # Fallback parser
            # ------------------------------------------------

            if not rows:

                # Older TradingView format
                match = re.search(
                    r'"s":\[(.+?)\}\]',
                    raw_data,
                    re.DOTALL
                )

                if match:

                    data_string = (
                        match.group(1)
                    )

                    raw_rows = data_string.split(
                        ',{"'
                    )

                    for raw_row in raw_rows:

                        try:

                            values = re.split(
                                r"\[|:|,|\]",
                                raw_row
                            )

                            if len(values) < 9:
                                continue

                            timestamp = float(
                                values[4]
                            )

                            dt = (
                                datetime.datetime
                                .fromtimestamp(
                                    timestamp,
                                    tz=pytz.utc
                                )
                                .astimezone(ist)
                            )

                            open_price = float(
                                values[5]
                            )

                            high_price = float(
                                values[6]
                            )

                            low_price = float(
                                values[7]
                            )

                            close_price = float(
                                values[8]
                            )

                            volume = 0.0

                            if len(values) > 9:

                                try:

                                    volume = float(
                                        values[9]
                                    )

                                except Exception:

                                    volume = 0.0

                            rows.append(
                                [
                                    symbol,
                                    dt,
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
            # No data
            # ------------------------------------------------

            if not rows:

                logging.warning(
                    "No candle data found for %s",
                    symbol
                )

                return pd.DataFrame(
                    columns=columns
                )

            # ------------------------------------------------
            # DataFrame
            # ------------------------------------------------

            df = pd.DataFrame(
                rows,
                columns=columns
            )

            # ------------------------------------------------
            # Datetime
            # ------------------------------------------------

            df["datetime"] = pd.to_datetime(
                df["datetime"],
                errors="coerce"
            )

            # ------------------------------------------------
            # Numeric
            # ------------------------------------------------

            numeric_columns = [
                "open",
                "high",
                "low",
                "close",
                "volume"
            ]

            for col in numeric_columns:

                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce"
                )

            # ------------------------------------------------
            # Remove invalid
            # ------------------------------------------------

            df = df.dropna(
                subset=[
                    "datetime",
                    "open",
                    "high",
                    "low",
                    "close"
                ]
            )

            # ------------------------------------------------
            # Remove duplicates
            # ------------------------------------------------

            df = df.drop_duplicates(
                subset=[
                    "datetime"
                ],
                keep="last"
            )

            # ------------------------------------------------
            # Sort
            # ------------------------------------------------

            df = (
                df
                .sort_values(
                    "datetime"
                )
                .reset_index(
                    drop=True
                )
            )

            logging.info(
                "Parsed %s candles for %s",
                len(df),
                symbol
            )

            return df

        except Exception as e:

            logging.error(
                "Data parsing error for %s: %s",
                symbol,
                e
            )

            return pd.DataFrame(
                columns=columns
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
        extended_session: bool = False
    ):

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
        # Validate bars
        # ----------------------------------------------------

        n_bars = int(
            n_bars
        )

        if n_bars <= 0:

            raise ValueError(
                "n_bars must be greater than 0"
            )

        # TradingView limit
        n_bars = min(
            n_bars,
            5000
        )

        # ----------------------------------------------------
        # Format symbol
        # ----------------------------------------------------

        tv_symbol = self.__format_symbol(
            symbol=symbol,
            exchange=exchange,
            contract=fut_contract
        )

        interval_value = (
            interval.value
        )

        logging.info(
            "TradingView request: "
            "%s | interval=%s | bars=%s",
            tv_symbol,
            interval_value,
            n_bars
        )

        # ----------------------------------------------------
        # New connection
        # ----------------------------------------------------

        self.__close_connection()

        self.__create_connection()

        raw_data = ""

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

            self.__send_message(
                "chart_create_session",
                [
                    self.chart_session,
                    ""
                ]
            )

            # =================================================
            # SYMBOL
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
            # RECEIVE
            # =================================================

            completed = False

            while True:

                try:

                    result = self.ws.recv()

                except Exception as e:

                    logging.error(
                        "TradingView WebSocket receive error: %s",
                        e
                    )

                    break

                if not result:

                    continue

                raw_data += (
                    result + "\n"
                )

                if self.ws_debug:

                    print(
                        "\nRECV:",
                        result
                    )

                # --------------------------------------------
                # SUCCESS
                # --------------------------------------------

                if "series_completed" in result:

                    completed = True

                    logging.info(
                        "Series completed: %s",
                        tv_symbol
                    )

                    break

                # --------------------------------------------
                # Critical error
                # --------------------------------------------

                if "critical_error" in result:

                    logging.error(
                        "TradingView critical error: %s",
                        result
                    )

                    break

                # --------------------------------------------
                # Symbol error
                # --------------------------------------------

                if "symbol_error" in result:

                    logging.error(
                        "TradingView symbol error: %s",
                        result
                    )

                    break

                # --------------------------------------------
                # Series error
                # --------------------------------------------

                if "series_error" in result:

                    logging.error(
                        "TradingView series error: %s",
                        result
                    )

                    break

            # =================================================
            # ERROR DIAGNOSTIC
            # =================================================

            if not completed:

                if (
                    "permission denied"
                    in raw_data.lower()
                ):

                    logging.error(
                        "TradingView denied access "
                        "to %s. This is a TradingView "
                        "session/data-permission issue.",
                        tv_symbol
                    )

                elif (
                    "symbol_error"
                    in raw_data
                ):

                    logging.error(
                        "TradingView rejected symbol: %s",
                        tv_symbol
                    )

            # =================================================
            # PARSE
            # =================================================

            return self.__create_df(
                raw_data,
                symbol
            )

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

        url = self.__search_url.format(
            text,
            exchange
        )

        try:

            response = requests.get(
                url,
                headers=self.__signin_headers,
                timeout=15
            )

            response.raise_for_status()

            response_text = (
                response.text
                .replace("</em>", "")
                .replace("<em>", "")
            )

            return json.loads(
                response_text
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

    # ========================================================
    # CONTEXT MANAGER
    # ========================================================

    def __enter__(self):

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback
    ):

        self.close()
