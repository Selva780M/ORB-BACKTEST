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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
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

    # ========================================================
    # URLS
    # ========================================================

    __sign_in_url = (
        "https://www.tradingview.com/accounts/signin/"
    )

    __search_url = (
        "https://symbol-search.tradingview.com/"
        "symbol_search/?text={}&hl=1&exchange={}"
        "&lang=en&type=&domain=production"
    )

    # ========================================================
    # HEADERS
    # ========================================================

    __ws_origin = (
        "https://data.tradingview.com"
    )

    __signin_headers = {
        "Referer": "https://www.tradingview.com/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/153.0.0.0 Safari/537.36"
        )
    }

    # ========================================================
    # TIMEOUT
    # ========================================================

    __ws_timeout = 15


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
        # Anonymous token
        # ----------------------------------------------------

        if self.token is None:

            self.token = (
                "unauthorized_user_token"
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

        if (
            username is None
            or password is None
        ):

            logging.info(
                "TradingView anonymous mode"
            )

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

            logging.info(
                "TradingView login HTTP status: %s",
                response.status_code
            )

            result = response.json()

            if (
                "user" in result
                and "auth_token" in result["user"]
            ):

                token = (
                    result["user"]["auth_token"]
                )

                logging.info(
                    "TradingView authentication successful"
                )

                return token

            logging.error(
                "TradingView authentication response invalid: %s",
                result
            )

            return None

        except Exception as e:

            logging.error(
                "TradingView authentication failed: %s",
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

        try:

            self.ws = create_connection(
                "wss://data.tradingview.com/socket.io/websocket",
                origin=self.__ws_origin,
                timeout=self.__ws_timeout,
                host="data.tradingview.com"
            )

            logging.info(
                "TradingView websocket connected"
            )

            return True

        except Exception as e:

            logging.error(
                "TradingView websocket connection failed: %s",
                e
            )

            self.ws = None

            return False


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

        if self.ws is None:

            raise ConnectionError(
                "TradingView websocket is not connected"
            )

        message = (
            self.__create_message(
                func,
                args
            )
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
        ).strip()

        exchange = str(
            exchange
        ).strip().upper()

        # ----------------------------------------------------
        # Already formatted
        # ----------------------------------------------------

        if ":" in symbol:

            return symbol

        # ----------------------------------------------------
        # CASH / EQUITY
        # ----------------------------------------------------

        if contract is None:

            return (
                f"{exchange}:{symbol}"
            )

        # ----------------------------------------------------
        # FUTURES
        # ----------------------------------------------------

        if isinstance(
            contract,
            int
        ):

            return (
                f"{exchange}:{symbol}{contract}!"
            )

        raise ValueError(
            "contract must be an integer or None"
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
            # Find series data
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
            # Split individual bars
            # ------------------------------------------------

            x = out.split(
                ',{"'
            )

            data = []

            ist_tz = pytz.timezone(
                "Asia/Kolkata"
            )

            # ------------------------------------------------
            # Parse each bar
            # ------------------------------------------------

            for xi in x:

                try:

                    values = re.split(
                        r"\[|:|,|\]",
                        xi
                    )

                    # Need at least timestamp + OHLC
                    if len(values) < 9:

                        continue

                    # ------------------------------------------------
                    # Timestamp
                    # ------------------------------------------------

                    timestamp = float(
                        values[4]
                    )

                    ts = datetime.datetime.fromtimestamp(
                        timestamp,
                        tz=pytz.utc
                    )

                    ts_ist = (
                        ts.astimezone(
                            ist_tz
                        )
                    )

                    # ------------------------------------------------
                    # OHLC
                    # ------------------------------------------------

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

                    # ------------------------------------------------
                    # Volume
                    # ------------------------------------------------

                    volume = 0.0

                    if len(values) > 9:

                        try:

                            volume = float(
                                values[9]
                            )

                        except (
                            ValueError,
                            TypeError
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
                    TypeError,
                    IndexError
                ):

                    continue

            # ------------------------------------------------
            # Nothing parsed
            # ------------------------------------------------

            if not data:

                logging.warning(
                    "No parsed candle rows for %s",
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
            # Datetime
            # ------------------------------------------------

            df["Datetime"] = pd.to_datetime(
                df["Datetime"],
                errors="coerce"
            )

            # ------------------------------------------------
            # Remove invalid rows
            # ------------------------------------------------

            df = df.dropna(
                subset=[
                    "Datetime",
                    "Open",
                    "High",
                    "Low",
                    "Close"
                ]
            )

            # ------------------------------------------------
            # Sort
            # ------------------------------------------------

            df = df.sort_values(
                "Datetime"
            )

            # ------------------------------------------------
            # Remove duplicates
            # ------------------------------------------------

            df = df.drop_duplicates(
                subset=[
                    "Datetime"
                ]
            )

            # ------------------------------------------------
            # Reset index
            # ------------------------------------------------

            df = df.reset_index(
                drop=True
            )

            return df

        except Exception as e:

            logging.error(
                "Candle parser error for %s: %s",
                symbol,
                e
            )

            return pd.DataFrame()


    # ========================================================
    # GET HISTORICAL DATA
    # ========================================================

    def get_hist(
        self,
        symbol,
        exchange,
        interval=Interval.in_5_minute,
        n_bars=500,
        extended_session=False
    ):
    
        formatted_symbol = self.__format_symbol(symbol, exchange)
    
        # Resolve symbol
        session_type = "extended" if extended_session else "regular"
    
        symbol_payload = (
            '={"symbol":"'
            + formatted_symbol
            + '","adjustment":"splits","session":"'
            + session_type
            + '"}'
        )
    
        self.__send_message(
            "resolve_symbol",
            [
                self.session,
                "symbol_1",
                symbol_payload
            ]
        )
    
        # ==========================================
        # IMPORTANT FIX
        # ==========================================
        if isinstance(interval, Interval):
            interval = interval.value
        else:
            interval = str(interval)
    
        print("TradingView interval =", interval)
    
        # ==========================================
        # CREATE SERIES
        # ==========================================
        self.__send_message(
            "create_series",
            [
                self.session,
                "s1",
                "s1",
                "symbol_1",
                interval,
                n_bars
            ]
        )
    
        # Timezone
        self.__send_message(
            "switch_timezone",
            [
                self.session,
                "Asia/Kolkata"
            ]
        )
    
        # Receive response
        raw_data = ""
    
        while True:
            try:
                result = self.ws.recv()
                raw_data += result
    
                if "series_completed" in result:
                    break
    
                if "series_error" in result:
                    logging.error(
                        "TradingView series error: %s",
                        result
                    )
                    break
    
                if "critical_error" in result:
                    logging.error(
                        "TradingView critical error: %s",
                        result
                    )
                    break
    
            except Exception as e:
                logging.error(
                    "TradingView websocket receive error: %s",
                    e
                )
                break
    
        return self.__create_df(
            raw_data,
            formatted_symbol
        )
 
        # ====================================================
        # CLOSE
        # ====================================================

        try:

            if self.ws:

                self.ws.close()

        except Exception:

            pass

        # ====================================================
        # NOT COMPLETED
        # ====================================================

        if not completed:

            logging.warning(
                "TradingView series was not completed for %s",
                formatted_symbol
            )

        # ====================================================
        # PARSE
        # ====================================================

        df = self.__create_df(
            raw_data,
            original_symbol
        )

        # ====================================================
        # EMPTY
        # ====================================================

        if df is None or df.empty:

            logging.warning(
                "No parsed candle data for %s",
                formatted_symbol
            )

            return pd.DataFrame()

        # ====================================================
        # FINAL CLEANUP
        # ====================================================

        df["Datetime"] = pd.to_datetime(
            df["Datetime"],
            errors="coerce"
        )

        df = df.dropna(
            subset=[
                "Datetime"
            ]
        )

        df = df.sort_values(
            "Datetime"
        )

        df = df.drop_duplicates(
            subset=[
                "Datetime"
            ]
        )

        df = df.reset_index(
            drop=True
        )

        # ====================================================
        # RESULT
        # ====================================================

        logging.info(
            "Received %s candles for %s",
            len(df),
            formatted_symbol
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

            response = requests.get(
                url,
                headers=self.__signin_headers,
                timeout=15
            )

            response.raise_for_status()

            symbols_list = json.loads(
                response.text
                .replace("</em>", "")
                .replace("<em>", "")
            )

        except Exception as e:

            logging.error(
                "Symbol search error: %s",
                e
            )

        return symbols_list


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    logging.info(
        "Starting TradingView test..."
    )

    tv = TvDatafeed()

