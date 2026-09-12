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
# TV DATAFEED
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

    # KEEP EXACTLY LIKE YOUR WORKING REFERENCE
    __ws_headers = json.dumps({
        "Origin": "https://data.tradingview.com"
    })

    __signin_headers = {
        "Referer": "https://www.tradingview.com"
    }

    __ws_timeout = 5


    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        username: str = None,
        password: str = None,
        token: str = None
    ):

        self.ws_debug = False

        # ----------------------------------------------------
        # Token first
        # ----------------------------------------------------

        if token:

            self.token = token

        else:

            self.token = self.__auth(
                username,
                password
            )

        # ----------------------------------------------------
        # Anonymous fallback
        # ----------------------------------------------------

        if self.token is None:

            self.token = "unauthorized_user_token"

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
    # AUTH
    # ========================================================

    def __auth(
        self,
        username,
        password
    ):

        if username is None or password is None:

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
                timeout=10,
            )

            logging.info(
                "TradingView login HTTP status: %s",
                response.status_code
            )

            result = response.json()

            token = result["user"]["auth_token"]

            return token

        except Exception as e:

            logging.error(
                "TradingView authentication failed: %s",
                e
            )

            return None


    # ========================================================
    # WEBSOCKET CONNECTION
    # ========================================================

    def __create_connection(self):

        logging.info(
            "Creating TradingView websocket connection..."
        )

        self.ws = create_connection(
            "wss://data.tradingview.com/socket.io/websocket",
            headers=self.__ws_headers,
            timeout=self.__ws_timeout,
        )

        logging.info(
            "TradingView websocket connected"
        )


    # ========================================================
    # RAW MESSAGE FILTER
    # ========================================================

    @staticmethod
    def __filter_raw_message(text):

        try:

            found = re.search(
                r'"m":"(.+?)",',
                text
            ).group(1)

            found2 = re.search(
                r'"p":(.+?"}"])}',
                text
            ).group(1)

            return found, found2

        except AttributeError:

            return None, None


    # ========================================================
    # SESSION
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
    # MESSAGE
    # ========================================================

    @staticmethod
    def __prepend_header(st):

        return (
            "~m~"
            + str(len(st))
            + "~m~"
            + st
        )


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

        return self.__prepend_header(
            self.__construct_message(
                func,
                param_list
            )
        )


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

            print(message)

        self.ws.send(message)


    # ========================================================
    # CREATE DATAFRAME
    # ========================================================

    @staticmethod
    def __create_df(
        raw_data,
        symbol
    ):

        try:

            out = re.search(
                r'"s":\[(.+?)\}\]',
                raw_data
            ).group(1)

            x = out.split(
                ',{"'
            )

            data = []

            volume_data = True

            ist_tz = pytz.timezone(
                "Asia/Kolkata"
            )

            for xi in x:

                xi = re.split(
                    r"\[|:|,|\]",
                    xi
                )

                # ------------------------------------------------
                # Timestamp
                # ------------------------------------------------

                ts = datetime.datetime.fromtimestamp(
                    float(xi[4]),
                    tz=pytz.utc
                )

                ts_ist = ts.astimezone(
                    ist_tz
                )

                row = [ts_ist]

                # ------------------------------------------------
                # OHLCV
                # ------------------------------------------------

                for i in range(5, 10):

                    # No volume
                    if (
                        not volume_data
                        and i == 9
                    ):

                        row.append(0.0)

                        continue

                    try:

                        row.append(
                            float(xi[i])
                        )

                    except (
                        ValueError,
                        IndexError
                    ):

                        volume_data = False

                        row.append(0.0)

                data.append(row)

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
                    "Volume",
                ]
            )

            df.insert(
                0,
                "symbol",
                value=symbol
            )

            return df

        except AttributeError:

            logging.warning(
                "No candle data found for %s",
                symbol
            )

            return pd.DataFrame()

        except Exception as e:

            logging.error(
                "Candle parser error for %s: %s",
                symbol,
                e
            )

            return pd.DataFrame()


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

        # CASH / EQUITY
        elif contract is None:

            return (
                f"{exchange}:{symbol}"
            )

        # FUTURES
        elif isinstance(
            contract,
            int
        ):

            return (
                f"{exchange}:{symbol}{contract}!"
            )

        else:

            raise ValueError(
                "not a valid contract"
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
        # FORMAT SYMBOL
        # ----------------------------------------------------

        symbol = self.__format_symbol(
            symbol=symbol,
            exchange=exchange,
            contract=fut_contract
        )

        interval = interval.value

        logging.info(
            "TradingView request: %s | interval=%s | bars=%s",
            symbol,
            interval,
            n_bars
        )

        # ----------------------------------------------------
        # CONNECTION
        # ----------------------------------------------------

        self.__create_connection()

        # ----------------------------------------------------
        # AUTH
        # ----------------------------------------------------

        self.__send_message(
            "set_auth_token",
            [
                self.token
            ]
        )

        # ----------------------------------------------------
        # CHART SESSION
        # ----------------------------------------------------

        self.__send_message(
            "chart_create_session",
            [
                self.chart_session,
                ""
            ]
        )

        # ----------------------------------------------------
        # QUOTE SESSION
        # ----------------------------------------------------

        self.__send_message(
            "quote_create_session",
            [
                self.session
            ]
        )

        # ----------------------------------------------------
        # QUOTE FIELDS
        # ----------------------------------------------------

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
            ],
        )

        # ----------------------------------------------------
        # ADD SYMBOL
        #
        # IMPORTANT:
        # force_permission
        # ----------------------------------------------------

        self.__send_message(
            "quote_add_symbols",
            [
                self.session,
                symbol,
                {
                    "flags": [
                        "force_permission"
                    ]
                }
            ]
        )

        # ----------------------------------------------------
        # FAST SYMBOL
        # ----------------------------------------------------

        self.__send_message(
            "quote_fast_symbols",
            [
                self.session,
                symbol
            ]
        )

        # ----------------------------------------------------
        # RESOLVE SYMBOL
        #
        # KEEP SAME FORMAT AS WORKING CODE
        # ----------------------------------------------------

        self.__send_message(
            "resolve_symbol",
            [
                self.chart_session,
                "symbol_1",

                '={"symbol":"'
                + symbol
                + '","adjustment":"splits","session":'
                + (
                    '"regular"'
                    if not extended_session
                    else '"extended"'
                )
                + "}",
            ],
        )

        # ----------------------------------------------------
        # CREATE SERIES
        # ----------------------------------------------------

        self.__send_message(
            "create_series",
            [
                self.chart_session,
                "s1",
                "s1",
                "symbol_1",
                interval,
                n_bars
            ]
        )

        # ----------------------------------------------------
        # TIMEZONE
        # ----------------------------------------------------

        self.__send_message(
            "switch_timezone",
            [
                self.chart_session,
                "exchange"
            ]
        )

        # ----------------------------------------------------
        # RECEIVE DATA
        # ----------------------------------------------------

        raw_data = ""

        while True:

            try:

                result = self.ws.recv()

                if not result:

                    continue

                raw_data += (
                    result
                    + "\n"
                )

                # ------------------------------------------------
                # Debug important responses only
                # ------------------------------------------------

                if (
                    "critical_error" in result
                    or "protocol_error" in result
                    or "series_error" in result
                ):

                    logging.error(
                        "TradingView response: %s",
                        result[:3000]
                    )

                # ------------------------------------------------
                # Finished
                # ------------------------------------------------

                if "series_completed" in result:

                    break

            except Exception as e:

                logging.error(
                    "TradingView websocket receive error: %s",
                    e
                )

                break

        # ----------------------------------------------------
        # PARSE
        # ----------------------------------------------------

        df = self.__create_df(
            raw_data,
            symbol
        )

        # ----------------------------------------------------
        # CLOSE
        # ----------------------------------------------------

        try:

            self.ws.close()

        except Exception:

            pass

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        if df is None or df.empty:

            logging.warning(
                "No parsed candle data for %s",
                symbol
            )

        else:

            logging.info(
                "Received %s candles for %s",
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

        symbols_list = []

        try:

            resp = requests.get(
                url,
                timeout=10
            )

            symbols_list = json.loads(
                resp.text
                .replace("</em>", "")
                .replace("<em>", "")
            )

        except Exception as e:

            logging.error(
                "Symbol search error: %s",
                e
            )

        return symbols_list
