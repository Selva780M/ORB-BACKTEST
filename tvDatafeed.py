# ============================================================
# tvDatafeed.py
# TradingView Historical Data Feed
# Updated based on working reference protocol
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

from websocket import create_connection


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(level=logging.INFO)


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

    # ========================================================
    # TRADINGVIEW URLs
    # ========================================================

    __sign_in_url = (
        "https://www.tradingview.com/accounts/signin/"
    )

    __search_url = (
        "https://symbol-search.tradingview.com/"
        "symbol_search/?text={}&hl=1&exchange={}"
        "&lang=en&type=&domain=production"
    )

    # Same as working reference
    __ws_headers = json.dumps({
        "Origin": "https://data.tradingview.com"
    })

    __signin_headers = {
        "Referer": "https://www.tradingview.com"
    }

    __ws_timeout = 15


    # ========================================================
    # INITIALIZE
    # ========================================================

    def __init__(
        self,
        username=None,
        password=None,
        token=None
    ):

        self.ws_debug = False

        # ----------------------------------------------------
        # Authentication
        # ----------------------------------------------------

        if token:

            self.token = token

            logging.info(
                "TradingView authentication: token"
            )

        else:

            self.token = self.__auth(
                username,
                password
            )

            if self.token:

                logging.info(
                    "TradingView authentication: username/password"
                )

        # ----------------------------------------------------
        # Unauthorized mode
        # ----------------------------------------------------

        if self.token is None:

            self.token = "unauthorized_user_token"

            logging.warning(
                "TradingView running with unauthorized_user_token"
            )

        # ----------------------------------------------------
        # Sessions
        # ----------------------------------------------------

        self.ws = None

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

        if username is None or password is None:

            logging.warning(
                "TradingView username/password not supplied"
            )

            return None

        try:

            response = requests.post(
                self.__sign_in_url,
                data={
                    "username": username,
                    "password": password,
                    "remember": "on"
                },
                headers=self.__signin_headers,
                timeout=15
            )

            response.raise_for_status()

            result = response.json()

            token = result.get(
                "user",
                {}
            ).get(
                "auth_token"
            )

            if token:

                logging.info(
                    "TradingView login successful"
                )

                return token

            logging.warning(
                "TradingView login response did not contain auth_token"
            )

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
            "Creating TradingView websocket..."
        )

        self.ws = create_connection(
            "wss://data.tradingview.com/socket.io/websocket",
            header=[
                "Origin: https://data.tradingview.com"
            ],
            timeout=self.__ws_timeout
        )

        logging.info(
            "TradingView websocket connected"
        )


    # ========================================================
    # GENERATE QUOTE SESSION
    # ========================================================

    @staticmethod
    def __generate_session():

        letters = string.ascii_lowercase

        value = "".join(
            random.choice(letters)
            for _ in range(12)
        )

        return "qs_" + value


    # ========================================================
    # GENERATE CHART SESSION
    # ========================================================

    @staticmethod
    def __generate_chart_session():

        letters = string.ascii_lowercase

        value = "".join(
            random.choice(letters)
            for _ in range(12)
        )

        return "cs_" + value


    # ========================================================
    # MESSAGE HEADER
    # ========================================================

    @staticmethod
    def __prepend_header(
        message
    ):

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
        ).strip()

        exchange = str(
            exchange
        ).strip()

        # Already formatted
        #
        # Example:
        # NSE:RELIANCE
        #
        if ":" in symbol:

            return symbol

        # Cash
        #
        # NSE:RELIANCE
        #
        if contract is None:

            return (
                f"{exchange}:{symbol}"
            )

        # Futures
        #
        # MCX:SILVERMIC1!
        #
        if isinstance(
            contract,
            int
        ):

            return (
                f"{exchange}:{symbol}{contract}!"
            )

        raise ValueError(
            "not a valid contract"
        )


    # ========================================================
    # PARSE MODERN DATA
    # ========================================================

    @staticmethod
    def __parse_modern_data(
        raw_data,
        symbol
    ):

        data = []

        ist = pytz.timezone(
            "Asia/Kolkata"
        )

        # ----------------------------------------------------
        # Modern TradingView messages
        #
        # Example:
        #
        # ~m~...~m~{"m":"du","p":[...]}
        # ----------------------------------------------------

        for match in re.finditer(
            r'"m":"du","p":(\[.*?\])(?=~m~|$)',
            raw_data,
            re.DOTALL
        ):

            try:

                payload = json.loads(
                    match.group(1)
                )

            except Exception:

                continue

            if len(payload) < 2:

                continue

            payload_data = payload[1]

            if not isinstance(
                payload_data,
                dict
            ):

                continue

            # ------------------------------------------------
            # Find candle vectors recursively
            # ------------------------------------------------

            def find_values(obj):

                found = []

                if isinstance(
                    obj,
                    dict
                ):

                    for value in obj.values():

                        found.extend(
                            find_values(value)
                        )

                elif isinstance(
                    obj,
                    list
                ):

                    # Candle:
                    #
                    # [timestamp, open, high,
                    #  low, close, volume]
                    #
                    if (
                        len(obj) >= 5
                        and isinstance(
                            obj[0],
                            (int, float)
                        )
                        and isinstance(
                            obj[1],
                            (int, float)
                        )
                    ):

                        found.append(
                            obj
                        )

                    else:

                        for value in obj:

                            found.extend(
                                find_values(value)
                            )

                return found

            values = find_values(
                payload_data
            )

            # ------------------------------------------------
            # Process candles
            # ------------------------------------------------

            for value in values:

                if len(value) < 5:

                    continue

                try:

                    timestamp = float(
                        value[0]
                    )

                    # Ignore invalid timestamp
                    if timestamp < 100000000:

                        continue

                    dt = (
                        datetime.datetime
                        .fromtimestamp(
                            timestamp,
                            tz=pytz.utc
                        )
                        .astimezone(ist)
                    )

                    open_price = float(
                        value[1]
                    )

                    high_price = float(
                        value[2]
                    )

                    low_price = float(
                        value[3]
                    )

                    close_price = float(
                        value[4]
                    )

                    if (
                        len(value) > 5
                        and value[5] is not None
                    ):

                        volume = float(
                            value[5]
                        )

                    else:

                        volume = 0.0

                    data.append(
                        [
                            dt,
                            open_price,
                            high_price,
                            low_price,
                            close_price,
                            volume
                        ]
                    )

                except (
                    ValueError,
                    TypeError,
                    IndexError
                ):

                    continue


        # ----------------------------------------------------
        # No data
        # ----------------------------------------------------

        if not data:

            return pd.DataFrame()


        # ----------------------------------------------------
        # DataFrame
        # ----------------------------------------------------

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


        # ----------------------------------------------------
        # Remove duplicate candles
        # ----------------------------------------------------

        df = df.drop_duplicates(
            subset=[
                "Datetime"
            ]
        )


        # ----------------------------------------------------
        # Sort
        # ----------------------------------------------------

        df = (
            df
            .sort_values(
                "Datetime"
            )
            .reset_index(
                drop=True
            )
        )


        # ----------------------------------------------------
        # Symbol
        # ----------------------------------------------------

        df.insert(
            0,
            "symbol",
            symbol
        )


        return df


    # ========================================================
    # PARSE OLD DATA
    # ========================================================

    @staticmethod
    def __parse_old_data(
        raw_data,
        symbol
    ):

        try:

            match = re.search(
                r'"s":\[(.+?)\}\]',
                raw_data,
                re.DOTALL
            )

            if not match:

                return pd.DataFrame()


            rows = match.group(
                1
            ).split(
                ',{"'
            )


            data = []

            ist = pytz.timezone(
                "Asia/Kolkata"
            )


            for row in rows:

                try:

                    parts = re.split(
                        r"\[|:|,|\]",
                        row
                    )

                    timestamp = float(
                        parts[4]
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

                    try:

                        volume = float(
                            parts[9]
                        )

                    except Exception:

                        volume = 0.0


                    data.append(
                        [
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


            if not data:

                return pd.DataFrame()


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


            df = df.drop_duplicates(
                subset=[
                    "Datetime"
                ]
            )


            df = (
                df
                .sort_values(
                    "Datetime"
                )
                .reset_index(
                    drop=True
                )
            )


            df.insert(
                0,
                "symbol",
                symbol
            )


            return df


        except Exception:

            return pd.DataFrame()


    # ========================================================
    # CREATE DATAFRAME
    # ========================================================

    @classmethod
    def __create_df(
        cls,
        raw_data,
        symbol
    ):

        # ----------------------------------------------------
        # Modern parser
        # ----------------------------------------------------

        df = cls.__parse_modern_data(
            raw_data,
            symbol
        )

        if not df.empty:

            logging.info(
                "Parsed %s candles using modern format",
                len(df)
            )

            return df


        # ----------------------------------------------------
        # Old parser
        # ----------------------------------------------------

        df = cls.__parse_old_data(
            raw_data,
            symbol
        )

        if not df.empty:

            logging.info(
                "Parsed %s candles using old format",
                len(df)
            )

            return df


        logging.warning(
            "No candle data found for %s",
            symbol
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
    ):

        # ====================================================
        # FORMAT SYMBOL
        # ====================================================

        symbol = self.__format_symbol(
            symbol=symbol,
            exchange=exchange,
            contract=fut_contract
        )


        # ====================================================
        # INTERVAL
        # ====================================================

        if isinstance(
            interval,
            Interval
        ):

            interval_value = interval.value

        else:

            interval_value = str(
                interval
            )


        n_bars = int(
            n_bars
        )


        logging.info(
            "=============================================="
        )

        logging.info(
            "TradingView Historical Request"
        )

        logging.info(
            "Symbol   : %s",
            symbol
        )

        logging.info(
            "Interval : %s",
            interval_value
        )

        logging.info(
            "Bars     : %s",
            n_bars
        )

        logging.info(
            "Contract : %s",
            fut_contract
        )

        logging.info(
            "Session  : %s",
            (
                "extended"
                if extended_session
                else "regular"
            )
        )

        logging.info(
            "=============================================="
        )


        # ====================================================
        # CREATE WEBSOCKET
        # ====================================================

        try:

            self.__create_connection()

        except Exception as e:

            logging.exception(
                "TradingView websocket connection failed: %s",
                e
            )

            return pd.DataFrame()


        # ====================================================
        # AUTH TOKEN
        # ====================================================
        #
        # SAME AS WORKING REFERENCE
        #
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
        #
        # SAME AS WORKING REFERENCE
        #
        # ====================================================

        self.__send_message(
            "chart_create_session",
            [
                self.chart_session,
                ""
            ]
        )


        # ====================================================
        # QUOTE SESSION
        # ====================================================
        
        self.__send_message(
            "quote_create_session",
            [self.session]
        )
        
        # ====================================================
        # QUOTE FIELDS
        # ====================================================
        
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
        
        # ====================================================
        # QUOTE ADD SYMBOL
        # ====================================================
        
        self.__send_message(
            "quote_add_symbols",
            [
                self.session,
                symbol,
                {
                    "flags": ["force_permission"]
                }
            ]
        )
        
        self.__send_message(
            "quote_fast_symbols",
            [
                self.session,
                symbol
            ]
        )
        
        # ====================================================
        # RESOLVE SYMBOL
        # ====================================================
        
        symbol_id = "symbol_1"
        
        symbol_payload = (
            '={"symbol":"'
            + symbol
            + '","adjustment":"splits","session":'
            + (
                '"regular"'
                if not extended_session
                else '"extended"'
            )
            + "}"
        )
        
        self.__send_message(
            "resolve_symbol",
            [
                self.chart_session,
                "symbol_1",
                symbol_payload
            ]
        )
        
        # ====================================================
        # CREATE SERIES
        # ====================================================
        
        self.__send_message(
            "create_series",
            [
                self.chart_session,
                "s1",
                "s1",
                "symbol_1",
                interval_value,
                int(n_bars)
            ]
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

        series_completed = False

        symbol_error = False

        series_error = False


        while True:

            try:

                result = self.ws.recv()

            except Exception as e:

                logging.exception(
                    "TradingView websocket receive error: %s",
                    e
                )

                break


            if not result:

                continue


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


            # =================================================
            # HEARTBEAT
            # =================================================

            heartbeat = re.search(
                r"~m~\d+~m~~h~(\d+)",
                result
            )


            if heartbeat:

                heartbeat_value = (
                    heartbeat.group(1)
                )


                heartbeat_payload = (
                    "~h~"
                    + heartbeat_value
                )


                heartbeat_message = (
                    "~m~"
                    + str(
                        len(
                            heartbeat_payload
                        )
                    )
                    + "~m~"
                    + heartbeat_payload
                )


                try:

                    self.ws.send(
                        heartbeat_message
                    )

                except Exception:

                    pass


                continue


            # =================================================
            # SYMBOL ERROR
            # =================================================

            if (
                '"m":"symbol_error"'
                in result
            ):

                symbol_error = True

                logging.error(
                    "=============================================="
                )

                logging.error(
                    "TRADINGVIEW SYMBOL ERROR"
                )

                logging.error(
                    "%s",
                    result
                )

                logging.error(
                    "=============================================="
                )

                break


            # =================================================
            # SERIES ERROR
            # =================================================

            if (
                '"m":"series_error"'
                in result
            ):

                series_error = True

                logging.error(
                    "=============================================="
                )

                logging.error(
                    "TRADINGVIEW SERIES ERROR"
                )

                logging.error(
                    "%s",
                    result
                )

                logging.error(
                    "=============================================="
                )

                break


            # =================================================
            # CRITICAL ERROR
            # =================================================

            if (
                '"m":"critical_error"'
                in result
            ):

                logging.error(
                    "=============================================="
                )

                logging.error(
                    "TRADINGVIEW CRITICAL ERROR"
                )

                logging.error(
                    "%s",
                    result
                )

                logging.error(
                    "=============================================="
                )

                break


            # =================================================
            # SERIES COMPLETED
            # =================================================

            if (
                '"m":"series_completed"'
                in result
            ):

                logging.info(
                    "TradingView series completed"
                )

                series_completed = True

                break


        # ====================================================
        # CLOSE WEBSOCKET
        # ====================================================

        try:

            if self.ws:

                self.ws.close()

                self.ws = None

        except Exception:

            pass


        # ====================================================
        # STATUS
        # ====================================================

        if symbol_error:

            logging.warning(
                "TradingView rejected symbol: %s",
                symbol
            )

        elif series_error:

            logging.warning(
                "TradingView rejected series: %s",
                symbol
            )

        elif not series_completed:

            logging.warning(
                "TradingView series was not completed for %s",
                symbol
            )


        # ====================================================
        # PARSE DATA
        # ====================================================

        df = self.__create_df(
            raw_data,
            symbol
        )


        # ====================================================
        # FINAL STATUS
        # ====================================================

        if df.empty:

            logging.warning(
                "No candle data found for %s",
                symbol
            )

        else:

            logging.info(
                "SUCCESS: %s candles received for %s",
                len(df),
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
                .replace(
                    "</em>",
                    ""
                )
                .replace(
                    "<em>",
                    ""
                )
            )


        except Exception as e:

            logging.exception(
                "Symbol search error: %s",
                e
            )

            return []
