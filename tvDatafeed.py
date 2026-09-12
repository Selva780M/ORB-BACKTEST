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

    __sign_in_url = "https://www.tradingview.com/accounts/signin/"

    __search_url = (
        "https://symbol-search.tradingview.com/"
        "symbol_search/?text={}&hl=1&exchange={}"
        "&lang=en&type=&domain=production"
    )

    __ws_url = "wss://data.tradingview.com/socket.io/websocket"

    __ws_headers = json.dumps({
        "Origin": "https://data.tradingview.com"
    })

    __signin_headers = {
        "Referer": "https://www.tradingview.com",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
        )
    }

    __ws_timeout = 10

    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        username: str = None,
        password: str = None,
        token: str = None,
        timeout: int = 10
    ):

        self.ws_debug = False
        self.ws = None

        self.__ws_timeout = timeout

        # ----------------------------------------------------
        # TOKEN FIRST
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
        # SESSION
        # ----------------------------------------------------

        self.session = self.__generate_session()

        self.chart_session = self.__generate_chart_session()

    # ========================================================
    # AUTH
    # ========================================================

    def __auth(self, username, password):

        if not username or not password:
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

            result = response.json()

            token = (
                result
                .get("user", {})
                .get("auth_token")
            )

            if token:
                logging.info("TradingView authentication successful")

            else:
                logging.error(
                    "TradingView authentication failed: %s",
                    result
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
            "Creating TradingView websocket connection"
        )

        self.ws = create_connection(
            self.__ws_url,
            header=[
                "Origin: https://data.tradingview.com"
            ],
            timeout=self.__ws_timeout
        )

    # ========================================================
    # CLOSE
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
    # SESSION ID
    # ========================================================

    @staticmethod
    def __generate_session():

        string_length = 12

        letters = string.ascii_lowercase

        random_string = "".join(
            random.choice(letters)
            for _ in range(string_length)
        )

        return "qs_" + random_string

    # ========================================================

    @staticmethod
    def __generate_chart_session():

        string_length = 12

        letters = string.ascii_lowercase

        random_string = "".join(
            random.choice(letters)
            for _ in range(string_length)
        )

        return "cs_" + random_string

    # ========================================================
    # MESSAGE HELPERS
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

    @staticmethod
    def __construct_message(func, params):

        return json.dumps(
            {
                "m": func,
                "p": params
            },
            separators=(",", ":")
        )

    # ========================================================

    def __create_message(self, func, params):

        message = self.__construct_message(
            func,
            params
        )

        return self.__prepend_header(message)

    # ========================================================

    def __send_message(self, func, params):

        message = self.__create_message(
            func,
            params
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

        symbol = str(symbol).strip().upper()

        # Already EXCHANGE:SYMBOL
        if ":" in symbol:

            return symbol

        # Futures
        if contract is not None:

            if not isinstance(contract, int):

                raise ValueError(
                    "fut_contract must be an integer"
                )

            return (
                f"{exchange}:{symbol}{contract}!"
            )

        # Cash / Equity
        return f"{exchange}:{symbol}"

    # ========================================================
    # PARSE TRADINGVIEW DATA
    # ========================================================

    @staticmethod
    def __create_df(raw_data, symbol):

        try:

            # ------------------------------------------------
            # Find series data
            # ------------------------------------------------

            match = re.search(
                r'"s":\[(.+?)\}\]',
                raw_data,
                re.DOTALL
            )

            if not match:

                logging.warning(
                    "No candle data found for %s",
                    symbol
                )

                return pd.DataFrame(
                    columns=[
                        "symbol",
                        "datetime",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume"
                    ]
                )

            out = match.group(1)

            rows = out.split(',{"')

            data = []

            ist_tz = pytz.timezone(
                "Asia/Kolkata"
            )

            # ------------------------------------------------
            # Parse rows
            # ------------------------------------------------

            for row in rows:

                try:

                    values = re.split(
                        r"\[|:|,|\]",
                        row
                    )

                    # Need at least timestamp + OHLC
                    if len(values) < 9:
                        continue

                    timestamp = float(
                        values[4]
                    )

                    ts_utc = datetime.datetime.fromtimestamp(
                        timestamp,
                        tz=pytz.utc
                    )

                    ts_ist = ts_utc.astimezone(
                        ist_tz
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

                    # Volume
                    volume = 0.0

                    if len(values) > 9:

                        try:

                            volume = float(
                                values[9]
                            )

                        except Exception:

                            volume = 0.0

                    data.append(
                        [
                            symbol,
                            ts_ist,
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
            # DataFrame
            # ------------------------------------------------

            df = pd.DataFrame(
                data,
                columns=[
                    "symbol",
                    "datetime",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume"
                ]
            )

            if df.empty:

                return df

            # ------------------------------------------------
            # Datetime
            # ------------------------------------------------

            df["datetime"] = pd.to_datetime(
                df["datetime"],
                errors="coerce"
            )

            # ------------------------------------------------
            # Numeric columns
            # ------------------------------------------------

            numeric_columns = [
                "open",
                "high",
                "low",
                "close",
                "volume"
            ]

            for column in numeric_columns:

                df[column] = pd.to_numeric(
                    df[column],
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
            # Sort
            # ------------------------------------------------

            df = df.sort_values(
                "datetime"
            )

            # ------------------------------------------------
            # Duplicate removal
            # ------------------------------------------------

            df = df.drop_duplicates(
                subset=["datetime"],
                keep="last"
            )

            # ------------------------------------------------
            # Reset
            # ------------------------------------------------

            df = df.reset_index(
                drop=True
            )

            return df

        except Exception as e:

            logging.error(
                "Data parsing error for %s: %s",
                symbol,
                e
            )

            return pd.DataFrame(
                columns=[
                    "symbol",
                    "datetime",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume"
                ]
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
    ):

        # ----------------------------------------------------
        # Validate
        # ----------------------------------------------------

        if not isinstance(
            interval,
            Interval
        ):

            raise ValueError(
                "interval must be an Interval enum"
            )

        if n_bars <= 0:

            raise ValueError(
                "n_bars must be greater than 0"
            )

        # TradingView normal maximum
        n_bars = min(
            int(n_bars),
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

        interval_value = interval.value

        logging.info(
            "Fetching %s | %s | %s bars",
            tv_symbol,
            interval_value,
            n_bars
        )

        # ----------------------------------------------------
        # New connection
        # ----------------------------------------------------

        self.__close_connection()

        self.__create_connection()

        try:

            # ------------------------------------------------
            # Auth
            # ------------------------------------------------

            self.__send_message(
                "set_auth_token",
                [self.token]
            )

            # ------------------------------------------------
            # Chart session
            # ------------------------------------------------

            self.__send_message(
                "chart_create_session",
                [
                    self.chart_session,
                    ""
                ]
            )

            # ------------------------------------------------
            # Quote session
            # ------------------------------------------------

            self.__send_message(
                "quote_create_session",
                [
                    self.session
                ]
            )

            # ------------------------------------------------
            # Quote fields
            # ------------------------------------------------

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
                    "rtc"
                ]
            )

            # ------------------------------------------------
            # Add symbol
            # ------------------------------------------------

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

            # ------------------------------------------------
            # Fast symbol
            # ------------------------------------------------

            self.__send_message(
                "quote_fast_symbols",
                [
                    self.session,
                    tv_symbol
                ]
            )

            # ------------------------------------------------
            # Resolve symbol
            # ------------------------------------------------

            session_type = (
                "extended"
                if extended_session
                else "regular"
            )

            symbol_config = (
                '{"symbol":"'
                + tv_symbol
                + '","adjustment":"splits","session":"'
                + session_type
                + '"}'
            )

            self.__send_message(
                "resolve_symbol",
                [
                    self.chart_session,
                    "symbol_1",
                    "=" + symbol_config
                ]
            )

            # ------------------------------------------------
            # Create series
            # ------------------------------------------------

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

            # ------------------------------------------------
            # Timezone
            # ------------------------------------------------

            self.__send_message(
                "switch_timezone",
                [
                    self.chart_session,
                    "exchange"
                ]
            )

            # ------------------------------------------------
            # Receive
            # ------------------------------------------------

            raw_data = ""

            while True:

                try:

                    result = self.ws.recv()

                    if not result:
                        continue

                    raw_data += result + "\n"

                    if self.ws_debug:

                        print(result)

                    # ----------------------------------------
                    # Completed
                    # ----------------------------------------

                    if "series_completed" in result:

                        break

                    # ----------------------------------------
                    # Critical errors
                    # ----------------------------------------

                    if (
                        "critical_error" in result
                        or "series_error" in result
                    ):

                        logging.error(
                            "TradingView returned error: %s",
                            result
                        )

                        break

                except Exception as e:

                    logging.error(
                        "Websocket receive error: %s",
                        e
                    )

                    break

            # ------------------------------------------------
            # Parse
            # ------------------------------------------------

            df = self.__create_df(
                raw_data,
                symbol
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

            text_data = (
                response.text
                .replace("</em>", "")
                .replace("<em>", "")
            )

            return json.loads(
                text_data
            )

        except Exception as e:

            logging.error(
                "Symbol search error: %s",
                e
            )

            return []

    # ========================================================
    # CONTEXT MANAGER
    # ========================================================

    def close(self):

        self.__close_connection()

    def __enter__(self):

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback
    ):

        self.close()
