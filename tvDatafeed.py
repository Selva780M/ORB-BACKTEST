# tvDatafeed.py

import enum
import json
import logging
import random
import re
import string
import time
from datetime import datetime, timezone

import pandas as pd
import pytz
import requests

from websocket import create_connection


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO
)

logger = logging.getLogger(__name__)


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

    in_1_hour = "60"
    in_2_hour = "120"
    in_3_hour = "180"
    in_4_hour = "240"

    in_daily = "D"
    in_weekly = "W"
    in_monthly = "M"


# ============================================================
# TV DATAFEED
# ============================================================

class TvDatafeed:

    # --------------------------------------------------------
    # URLs
    # --------------------------------------------------------

    SIGNIN_URL = (
        "https://www.tradingview.com/accounts/signin/"
    )

    QUOTE_TOKEN_URL = (
        "https://www.tradingview.com/quote_token/"
    )

    SEARCH_URL = (
        "https://symbol-search.tradingview.com/"
        "symbol_search/?text={}&hl=1&exchange={}"
        "&lang=en&type=&domain=production"
    )

    WS_URL = (
        "wss://data.tradingview.com/socket.io/websocket"
    )

    WS_TIMEOUT = 20


    # ========================================================
    # INIT
    # ========================================================

    def __init__(
        self,
        username=None,
        password=None,
        token=None,
        sessionid=None,
        sessionid_sign=None,
    ):

        self.ws = None

        self.ws_debug = False

        self.http = requests.Session()

        # ----------------------------------------------------
        # Browser headers
        # ----------------------------------------------------

        self.http.headers.update({

            "User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36",

            "Accept":
                "application/json,text/plain,*/*",

            "Referer":
                "https://www.tradingview.com/",

            "Origin":
                "https://www.tradingview.com",
        })


        # ----------------------------------------------------
        # Authentication state
        # ----------------------------------------------------

        self.token = None

        self.authenticated = False

        self.auth_method = "anonymous"


        # ====================================================
        # 1. DIRECT AUTH TOKEN
        # ====================================================

        if token:

            self.token = token

            self.authenticated = True

            self.auth_method = "auth_token"

            logger.info(
                "TradingView authentication: auth_token"
            )


        # ====================================================
        # 2. SESSIONID AUTH
        # ====================================================

        elif sessionid:

            self.sessionid = sessionid

            self.sessionid_sign = (
                sessionid_sign
            )

            # ------------------------------------------------
            # sessionid cookie
            # ------------------------------------------------

            self.http.cookies.set(
                "sessionid",
                sessionid,
                domain=".tradingview.com"
            )

            # ------------------------------------------------
            # sessionid_sign cookie
            # ------------------------------------------------

            if sessionid_sign:

                self.http.cookies.set(
                    "sessionid_sign",
                    sessionid_sign,
                    domain=".tradingview.com"
                )

            # ------------------------------------------------
            # Get temporary auth token
            # ------------------------------------------------

            self.token = (
                self._get_quote_token()
            )

            if self.token:

                self.authenticated = True

                self.auth_method = "sessionid"

                logger.info(
                    "TradingView authentication: sessionid"
                )


        # ====================================================
        # 3. LEGACY USERNAME / PASSWORD
        # ====================================================

        elif username and password:

            self.token = (
                self._legacy_login(
                    username,
                    password
                )
            )

            if self.token:

                self.authenticated = True

                self.auth_method = (
                    "username/password"
                )


        # ====================================================
        # 4. ANONYMOUS
        # ====================================================

        if not self.token:

            self.token = (
                "unauthorized_user_token"
            )

            self.authenticated = False

            self.auth_method = "anonymous"

            logger.warning(
                "TradingView running with "
                "unauthorized_user_token"
            )


        # ====================================================
        # SESSION IDS
        # ====================================================

        self.session = (
            self._generate_session()
        )

        self.chart_session = (
            self._generate_chart_session()
        )


    # ========================================================
    # GET QUOTE TOKEN
    # ========================================================

    def _get_quote_token(self):

        try:

            response = self.http.post(
                self.QUOTE_TOKEN_URL,
                timeout=15
            )

            logger.info(
                "quote_token status=%s",
                response.status_code
            )

            # ------------------------------------------------
            # HTTP ERROR
            # ------------------------------------------------

            if response.status_code != 200:

                logger.warning(
                    "quote_token failed: %s",
                    response.text[:500]
                )

                return None


            # ------------------------------------------------
            # JSON
            # ------------------------------------------------

            try:

                data = response.json()

                if isinstance(data, dict):

                    token = (
                        data.get("token")
                        or
                        data.get("auth_token")
                    )

                    if token:

                        return token


                if isinstance(data, str):

                    if len(data) > 20:

                        return data

            except Exception:

                pass


            # ------------------------------------------------
            # TEXT
            # ------------------------------------------------

            text = (
                response.text
                .strip()
            )

            if text:

                # JSON string
                if text.startswith('"'):

                    try:

                        token = json.loads(
                            text
                        )

                        if token:

                            return token

                    except Exception:

                        pass


                # Plain token
                if len(text) > 20:

                    return text


        except Exception as e:

            logger.warning(
                "quote_token error: %s",
                e
            )


        return None


    # ========================================================
    # LEGACY LOGIN
    # ========================================================

    def _legacy_login(
        self,
        username,
        password
    ):

        try:

            response = self.http.post(

                self.SIGNIN_URL,

                data={

                    "username":
                        username,

                    "password":
                        password,

                    "remember":
                        "on",
                },

                headers={

                    "Referer":
                        "https://www.tradingview.com/",
                },

                timeout=15,
            )


            logger.info(
                "TradingView login status=%s",
                response.status_code
            )


            result = response.json()


            token = (
                result
                .get("user", {})
                .get("auth_token")
            )


            if token:

                logger.info(
                    "TradingView login successful"
                )

                return token


            logger.warning(
                "TradingView login did not return "
                "auth_token: %s",
                str(result)[:500]
            )


        except Exception as e:

            logger.warning(
                "TradingView username/password "
                "login failed: %s",
                e
            )


        return None


    # ========================================================
    # GENERATE QUERY SESSION
    # ========================================================

    def _generate_session(self):

        letters = (
            string.ascii_lowercase
        )

        return (
            "qs_"
            +
            "".join(
                random.choice(letters)
                for _ in range(12)
            )
        )


    # ========================================================
    # GENERATE CHART SESSION
    # ========================================================

    def _generate_chart_session(self):

        letters = (
            string.ascii_lowercase
        )

        return (
            "cs_"
            +
            "".join(
                random.choice(letters)
                for _ in range(12)
            )
        )


    # ========================================================
    # CREATE WEBSOCKET
    # ========================================================

    def _create_connection(self):

        self.ws = create_connection(

            self.WS_URL,

            timeout=self.WS_TIMEOUT,

            origin=(
                "https://data.tradingview.com"
            ),
        )

        logger.info(
            "TradingView WebSocket connected"
        )


    # ========================================================
    # PREPEND MESSAGE HEADER
    # ========================================================

    def _prepend_header(
        self,
        message
    ):

        return (
            "~m~"
            +
            str(len(message))
            +
            "~m~"
            +
            message
        )


    # ========================================================
    # CONSTRUCT MESSAGE
    # ========================================================

    def _construct_message(
        self,
        func,
        params
    ):

        message = json.dumps({

            "m":
                func,

            "p":
                params,

            "t":
                int(time.time()),

            "t_ms":
                int(
                    time.time() * 1000
                ),
        })

        return (
            self._prepend_header(
                message
            )
        )


    # ========================================================
    # SEND MESSAGE
    # ========================================================

    def _send_message(
        self,
        func,
        params
    ):

        message = (
            self._construct_message(
                func,
                params
            )
        )

        if self.ws_debug:

            logger.info(
                "SEND: %s",
                message
            )

        self.ws.send(
            message
        )


    # ========================================================
    # FORMAT SYMBOL
    # ========================================================

    def _format_symbol(
        self,
        symbol,
        exchange,
        fut_contract=None
    ):

        symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        exchange = (
            str(exchange)
            .strip()
            .upper()
        )


        # ----------------------------------------------------
        # Already qualified
        # ----------------------------------------------------

        if ":" in symbol:

            return symbol


        # ----------------------------------------------------
        # Continuous futures
        # ----------------------------------------------------

        if fut_contract is not None:

            return (
                f"{exchange}:"
                f"{symbol}"
                f"{int(fut_contract)}!"
            )


        # ----------------------------------------------------
        # Normal symbol
        # ----------------------------------------------------

        return (
            f"{exchange}:"
            f"{symbol}"
        )


    # ========================================================
    # INTERVAL
    # ========================================================

    def _interval_value(
        self,
        interval
    ):

        if isinstance(
            interval,
            Interval
        ):

            return interval.value


        value = str(
            interval
        ).strip()


        aliases = {

            "1m": "1",
            "3m": "3",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "45m": "45",

            "1h": "60",
            "2h": "120",
            "3h": "180",
            "4h": "240",

            "1H": "60",
            "2H": "120",
            "3H": "180",
            "4H": "240",

            "1D": "D",
            "1W": "W",
            "1M": "M",
        }


        return aliases.get(
            value,
            value
        )


    # ========================================================
    # EXTRACT TV MESSAGES
    # ========================================================

    def _extract_messages(
        self,
        raw
    ):

        messages = []

        pattern = re.compile(
            r"~m~(\d+)~m~"
        )

        position = 0


        while position < len(raw):

            match = pattern.search(
                raw,
                position
            )

            if not match:

                break


            try:

                length = int(
                    match.group(1)
                )

            except Exception:

                break


            start = (
                match.end()
            )

            end = (
                start
                +
                length
            )


            if end > len(raw):

                break


            payload = raw[
                start:end
            ]


            messages.append(
                payload
            )


            position = end


        return messages


    # ========================================================
    # PARSE BAR
    # ========================================================

    def _parse_bar_value(
        self,
        value
    ):

        if not isinstance(
            value,
            list
        ):

            return None


        if len(value) < 6:

            return None


        try:

            timestamp = float(
                value[0]
            )


            # ------------------------------------------------
            # Milliseconds
            # ------------------------------------------------

            if timestamp > 10_000_000_000:

                timestamp /= 1000


            dt = datetime.fromtimestamp(

                timestamp,

                tz=timezone.utc
            )


            return {

                "Datetime":
                    dt,

                "Open":
                    float(value[1]),

                "High":
                    float(value[2]),

                "Low":
                    float(value[3]),

                "Close":
                    float(value[4]),

                "Volume":
                    float(value[5]),
            }


        except Exception:

            return None


    # ========================================================
    # RECURSIVE BAR SEARCH
    # ========================================================

    def _find_bars_recursive(
        self,
        obj,
        bars
    ):

        # ----------------------------------------------------
        # List
        # ----------------------------------------------------

        if isinstance(
            obj,
            list
        ):

            # A candle is normally:
            #
            # [timestamp, open, high, low, close, volume]

            bar = (
                self._parse_bar_value(
                    obj
                )
            )

            if bar:

                bars.append(
                    bar
                )

                return


            # Search children

            for item in obj:

                self._find_bars_recursive(
                    item,
                    bars
                )

            return


        # ----------------------------------------------------
        # Dictionary
        # ----------------------------------------------------

        if isinstance(
            obj,
            dict
        ):

            # Common TradingView candle keys

            for key in (
                "v",
                "value",
                "values",
                "i",
                "node",
            ):

                if key in obj:

                    self._find_bars_recursive(
                        obj[key],
                        bars
                    )


            # Search all dictionary values

            for value in obj.values():

                if isinstance(
                    value,
                    (dict, list)
                ):

                    self._find_bars_recursive(
                        value,
                        bars
                    )


    # ========================================================
    # PARSE DU
    # ========================================================

    def _parse_du(
        self,
        obj,
        bars
    ):

        try:

            self._find_bars_recursive(
                obj,
                bars
            )

        except Exception as e:

            logger.debug(
                "DU parse error: %s",
                e
            )


    # ========================================================
    # PARSE TIMESCALE UPDATE
    # ========================================================

    def _parse_timescale_update(
        self,
        obj,
        bars
    ):

        try:

            self._find_bars_recursive(
                obj,
                bars
            )

        except Exception as e:

            logger.debug(
                "timescale_update parse error: %s",
                e
            )


    # ========================================================
    # GET HISTORICAL DATA
    # ========================================================

    def get_hist(
        self,
        symbol,
        exchange="NSE",
        interval=Interval.in_daily,
        n_bars=10,
        fut_contract=None,
        extended_session=False,
    ):

        # ----------------------------------------------------
        # Format symbol
        # ----------------------------------------------------

        symbol = (
            self._format_symbol(
                symbol,
                exchange,
                fut_contract
            )
        )
        print(symbol)

        # ----------------------------------------------------
        # Resolution
        # ----------------------------------------------------

        interval_value = (
            self._interval_value(
                interval
            )
        )


        logger.info(
            "GET HIST | Symbol=%s | "
            "Interval=%s | Bars=%s | Auth=%s",
            symbol,
            interval_value,
            n_bars,
            self.auth_method,
        )


        # ----------------------------------------------------
        # New WebSocket
        # ----------------------------------------------------

        self._create_connection()


        bars = []


        try:

            # =================================================
            # AUTH
            # =================================================

            self._send_message(

                "set_auth_token",

                [
                    self.token
                ]
            )


            # =================================================
            # CHART SESSION
            # =================================================

            self._send_message(

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


            symbol_payload = json.dumps({

                "symbol":
                    symbol,

                "adjustment":
                    "splits",

                "session":
                    session_type,
            })


            self._send_message(

                "resolve_symbol",

                [

                    self.chart_session,

                    "symbol_1",
                    "=" +
                    symbol_payload,
                ]
            )


            # =================================================
            # CREATE SERIES
            # =================================================

            self._send_message(

                "create_series",

                [

                    self.chart_session,

                    "s1",

                    "s1",

                    "symbol_1",

                    str(interval_value),

                    int(n_bars),
                ]
            )


            # =================================================
            # TIMEZONE
            # =================================================

            self._send_message(

                "switch_timezone",

                [

                    self.chart_session,

                    "exchange"
                ]
            )


            # =================================================
            # RECEIVE
            # =================================================

            start_time = time.time()

            series_completed = False


            while (

                time.time()
                -
                start_time
                <
                self.WS_TIMEOUT

            ):

                try:

                    raw = self.ws.recv()

                except Exception as e:

                    logger.warning(
                        "WebSocket receive error: %s",
                        e
                    )

                    break


                if not raw:

                    continue
                    
                logger.info("TV RAW MESSAGE: %s", raw[:1000])

                # ------------------------------------------------
                # Debug
                # ------------------------------------------------

                if self.ws_debug:

                    logger.info(
                        "RECV: %s",
                        raw[:5000]
                    )


                # ------------------------------------------------
                # Heartbeat
                # ------------------------------------------------

                if "~m~" in raw:

                    heartbeat_matches = re.findall(
                        r"~m~(\d+)~m~(~h~\d+)",
                        raw
                    )

                    for _, heartbeat in (
                        heartbeat_matches
                    ):

                        try:

                            self.ws.send(
                                self._prepend_header(
                                    heartbeat
                                )
                            )

                        except Exception:

                            pass


                # ------------------------------------------------
                # Extract messages
                # ------------------------------------------------

                messages = (
                    self._extract_messages(
                        raw
                    )
                )


                for message in messages:

                    try:

                        obj = json.loads(
                            message
                        )

                    except Exception:

                        continue


                    method = obj.get(
                        "m"
                    )


                    # =========================================
                    # SERIES LOADING
                    # =========================================

                    if method == "series_loading":

                        logger.info(
                            "TradingView series loading"
                        )

                        continue


                    # =========================================
                    # DATA
                    # =========================================

                    if method == "du":

                        self._parse_du(
                            obj,
                            bars
                        )

                        continue


                    if method == "timescale_update":

                        self._parse_timescale_update(
                            obj,
                            bars
                        )

                        continue


                    # =========================================
                    # SYMBOL ERROR
                    # =========================================

                    if method == "symbol_error":

                        params = obj.get(
                            "p",
                            []
                        )


                        reason = (

                            params[2]

                            if len(params) > 2

                            else
                            "Unknown symbol error"
                        )


                        raise RuntimeError(

                            "TradingView symbol error: "
                            +
                            str(reason)
                            +
                            " | "
                            +
                            symbol
                        )


                    # =========================================
                    # SERIES ERROR
                    # =========================================

                    if method == "series_error":

                        raise RuntimeError(

                            "TradingView series error: "
                            +
                            str(
                                obj.get("p")
                            )
                        )


                    # =========================================
                    # CRITICAL ERROR
                    # =========================================

                    if method == "critical_error":

                        raise RuntimeError(

                            "TradingView critical error: "
                            +
                            str(
                                obj.get("p")
                            )
                        )


                    # =========================================
                    # COMPLETED
                    # =========================================

                    if method == "series_completed":

                        series_completed = True

                        logger.info(
                            "TradingView series completed"
                        )


                # ------------------------------------------------
                # Stop when data complete
                # ------------------------------------------------

                if (
                    series_completed
                    and
                    bars
                ):

                    break


            # =================================================
            # NO DATA
            # =================================================

            if not bars:

                logger.warning(
                    "No historical candles received: %s",
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

                        "Volume",
                    ]
                )


            # =================================================
            # DATAFRAME
            # =================================================

            df = pd.DataFrame(
                bars
            )


            # ------------------------------------------------
            # Remove invalid values
            # ------------------------------------------------

            numeric_columns = [

                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
            ]


            for column in numeric_columns:

                if column in df.columns:

                    df[column] = pd.to_numeric(

                        df[column],

                        errors="coerce"
                    )


            df = df.dropna(
                subset=[
                    "Datetime",
                    "Open",
                    "High",
                    "Low",
                    "Close",
                ]
            )


            # ------------------------------------------------
            # Remove duplicates
            # ------------------------------------------------

            df = (

                df
                .drop_duplicates(
                    subset=["Datetime"]
                )
                .sort_values(
                    "Datetime"
                )
                .reset_index(
                    drop=True
                )
            )


            # =================================================
            # TIMEZONE
            # =================================================

            india = pytz.timezone(
                "Asia/Kolkata"
            )


            if (
                hasattr(
                    df["Datetime"].dt,
                    "tz"
                )
                and
                df["Datetime"].dt.tz is None
            ):

                df["Datetime"] = (

                    df["Datetime"]

                    .dt
                    .tz_localize(
                        "UTC"
                    )
                )


            df["Datetime"] = (

                df["Datetime"]

                .dt
                .tz_convert(
                    india
                )

                .dt
                .tz_localize(
                    None
                )
            )


            # =================================================
            # SYMBOL
            # =================================================

            df.insert(
                0,
                "symbol",
                symbol
            )


            # =================================================
            # FINAL COLUMN ORDER
            # =================================================

            df = df[

                [

                    "symbol",

                    "Datetime",

                    "Open",

                    "High",

                    "Low",

                    "Close",

                    "Volume",
                ]
            ]


            logger.info(

                "SUCCESS | %s candles | %s",

                len(df),

                symbol
            )


            return df


        finally:

            # ------------------------------------------------
            # Close websocket
            # ------------------------------------------------

            try:

                if self.ws:

                    self.ws.close()

            except Exception:

                pass


            self.ws = None


    # ========================================================
    # SEARCH SYMBOL
    # ========================================================

    def search_symbol(
        self,
        text,
        exchange=""
    ):

        try:

            url = (
                self.SEARCH_URL.format(
                    text,
                    exchange
                )
            )


            response = self.http.get(

                url,

                timeout=15
            )


            response.raise_for_status()


            clean_text = re.sub(

                r"</?em>",

                "",

                response.text
            )


            return json.loads(
                clean_text
            )


        except Exception as e:

            logger.warning(
                "search_symbol failed: %s",
                e
            )

            return []
