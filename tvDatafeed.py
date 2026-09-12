```python
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

    __ws_url = (
        "wss://data.tradingview.com/socket.io/websocket"
    )

    __ws_headers = {
        "Origin": "https://data.tradingview.com"
    }

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
        # AUTH TOKEN
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

        # Anonymous TradingView token
        if not self.token:
            self.token = "unauthorized_user_token"

        # ----------------------------------------------------
        # SESSIONS
        # ----------------------------------------------------

        self.session = self.__generate_session()

        self.chart_session = (
            self.__generate_chart_session()
        )


    # ========================================================
    # LOGIN
    # ========================================================

    def __auth(self, username, password):

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

            else:
                logging.error(
                    "TradingView login response "
                    "does not contain auth_token"
                )

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
    # CLOSE CONNECTION
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
    # MESSAGE FORMAT
    # ========================================================

    @staticmethod
    def __prepend_header(message):

        return (
            "~m~"
            + str(len(message))
            + "~m~"
            + message
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

        message = self.__construct_message(
            func,
            param_list
        )

        return self.__prepend_header(message)


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
    # FORMAT SYMBOL
    # ========================================================

    @staticmethod
    def __format_symbol(
        symbol,
        exchange,
        contract=None
    ):

        symbol = str(symbol).upper().strip()
        exchange = str(exchange).upper().strip()

        # Already formatted
        if ":" in symbol:
            return symbol

        # Cash / Equity
        if contract is None:

            return f"{exchange}:{symbol}"

        # Futures
        if isinstance(contract, int):

            return (
                f"{exchange}:{symbol}{contract}!"
            )

        raise ValueError(
            "contract must be None or integer"
        )


    # ========================================================
    # PARSE TRADINGVIEW DATA
    # ========================================================

    @staticmethod
    def __create_df(
        raw_data,
        symbol
    ):

        try:

            # ------------------------------------------------
            # Locate series data
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
                    columns=[
                        "symbol",
                        "Datetime",
                        "Open",
                        "High",
                        "Low",
                        "Close",
                        "Volume"
                    ]
                )

            series_data = match.group(1)

            # ------------------------------------------------
            # Find each node
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
            # Parse rows
            # ------------------------------------------------

            for node in nodes:

                values = node[1]

                try:

                    values = json.loads(
                        "[" + values + "]"
                    )

                except Exception:

                    continue

                if len(values) < 6:
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
                        .astimezone(ist_tz)
                    )

                    open_price = float(values[1])
                    high_price = float(values[2])
                    low_price = float(values[3])
                    close_price = float(values[4])

                    # TradingView sometimes gives volume
                    try:
                        volume = float(values[5])
                    except Exception:
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
            # DataFrame
            # ------------------------------------------------

            if not rows:

                logging.warning(
                    "No parsed candle data for %s",
                    symbol
                )

                return pd.DataFrame(
                    columns=[
                        "symbol",
                        "Datetime",
                        "Open",
                        "High",
                        "Low",
                        "Close",
                        "Volume"
                    ]
                )

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

            df["Datetime"] = pd.to_datetime(
                df["Datetime"],
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
                    subset=["Datetime"]
                )
                .sort_values("Datetime")
                .reset_index(drop=True)
            )

            return df

        except Exception as e:

            logging.error(
                "TradingView dataframe error for %s: %s",
                symbol,
                e
            )

            return pd.DataFrame(
                columns=[
                    "symbol",
                    "Datetime",
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Volume"
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
        # Max TradingView bars
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

        tv_symbol = self.__format_symbol(
            symbol=symbol,
            exchange=exchange,
            contract=fut_contract
        )

        interval_value = interval.value

        logging.info(
            "Fetching %s %s %s bars=%s",
            tv_symbol,
            interval_value,
            exchange,
            n_bars
        )

        raw_data = ""

        # ----------------------------------------------------
        # New websocket connection
        # ----------------------------------------------------

        self.__close_connection()
        self.__create_connection()

        try:

            # =================================================
            # AUTH
            # =================================================

            self.__send_message(
                "set_auth_token",
                [self.token]
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
                # Important errors
                # ------------------------------------------------

                if (
                    "permission denied"
                    in result.lower()
                ):

                    logging.error(
                        "TradingView permission denied for %s",
                        tv_symbol
                    )

                    break

                if (
                    "symbol_error"
                    in result
                ):

                    logging.error(
                        "TradingView symbol error for %s",
                        tv_symbol
                    )

                    break

                if (
                    "critical_error"
                    in result
                ):

                    logging.error(
                        "TradingView critical error for %s",
                        tv_symbol
                    )

                    break

                if (
                    "series_error"
                    in result
                ):

                    logging.error(
                        "TradingView series error for %s",
                        tv_symbol
                    )

                    break

                # ------------------------------------------------
                # Completed
                # ------------------------------------------------

                if "series_completed" in result:

                    break

            # =================================================
            # CREATE DATAFRAME
            # =================================================

            df = self.__create_df(
                raw_data,
                symbol
            )

            if df.empty:

                logging.warning(
                    "No candle data found for %s",
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
                timeout=15
            )

            response.raise_for_status()

            data = response.text

            data = (
                data
                .replace("</em>", "")
                .replace("<em>", "")
            )

            return json.loads(data)

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


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO
    )

    TV_TOKEN = None

    tv = TvDatafeed(
        token=TV_TOKEN
    )

    df = tv.get_hist(
        symbol="RELIANCE",
        exchange="NSE",
        interval=Interval.in_5_minute,
        n_bars=500
    )

    print("\n========== RESULT ==========\n")

    print(df.tail(20))

    print("\nRows:", len(df))

    tv.close()
```
