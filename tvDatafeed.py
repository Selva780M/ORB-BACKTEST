import enum
import json
import logging
import random
import re
import string
import time
from datetime import datetime, timezone

import pandas as pd
import requests
import pytz
from websocket import create_connection


logging.basicConfig(level=logging.INFO)
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

    SIGNIN_URL = "https://www.tradingview.com/accounts/signin/"
    QUOTE_TOKEN_URL = "https://www.tradingview.com/quote_token/"

    SEARCH_URL = (
        "https://symbol-search.tradingview.com/"
        "symbol_search/?text={}&hl=1&exchange={}"
        "&lang=en&type=&domain=production"
    )

    WS_URL = "wss://data.tradingview.com/socket.io/websocket"

    WS_TIMEOUT = 20

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

        self.http.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.tradingview.com/",
            "Origin": "https://www.tradingview.com",
        })

        self.token = None
        self.authenticated = False
        self.auth_method = "anonymous"

        # ----------------------------------------------------
        # 1. Direct auth token
        # ----------------------------------------------------

        if token:

            self.token = token
            self.authenticated = True
            self.auth_method = "auth_token"

            logger.info(
                "TradingView authentication: auth_token"
            )

        # ----------------------------------------------------
        # 2. Browser session authentication
        # ----------------------------------------------------

        elif sessionid:

            self.sessionid = sessionid
            self.sessionid_sign = sessionid_sign

            self.http.cookies.set(
                "sessionid",
                sessionid,
                domain=".tradingview.com"
            )

            if sessionid_sign:

                self.http.cookies.set(
                    "sessionid_sign",
                    sessionid_sign,
                    domain=".tradingview.com"
                )

            self.token = self._get_quote_token()

            if self.token:

                self.authenticated = True
                self.auth_method = "sessionid"

                logger.info(
                    "TradingView authentication: sessionid"
                )

        # ----------------------------------------------------
        # 3. Legacy username/password
        # ----------------------------------------------------

        elif username and password:

            self.token = self._legacy_login(
                username,
                password
            )

            if self.token:

                self.authenticated = True
                self.auth_method = "username/password"

        # ----------------------------------------------------
        # 4. Anonymous fallback
        # ----------------------------------------------------

        if not self.token:

            self.token = "unauthorized_user_token"

            self.authenticated = False
            self.auth_method = "anonymous"

            logger.warning(
                "TradingView running with unauthorized_user_token"
            )

        self.session = self._generate_session()
        self.chart_session = self._generate_chart_session()

    # ========================================================
    # AUTH
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

            if response.status_code != 200:
                logger.warning(
                    "quote_token failed: %s",
                    response.text[:300]
                )
                return None

            # Usually JSON/string depending on response version
            try:
                data = response.json()

                if isinstance(data, dict):

                    token = (
                        data.get("token")
                        or data.get("auth_token")
                    )

                    if token:
                        return token

            except Exception:
                pass

            text = response.text.strip()

            if text:

                # JSON string response
                if text.startswith('"'):

                    try:
                        return json.loads(text)
                    except Exception:
                        pass

                # plain token
                if len(text) > 30:
                    return text

        except Exception as e:

            logger.exception(
                "quote_token error: %s",
                e
            )

        return None

    # ========================================================
    # LEGACY LOGIN
    # ========================================================

    def _legacy_login(self, username, password):

        try:

            response = self.http.post(
                self.SIGNIN_URL,
                data={
                    "username": username,
                    "password": password,
                    "remember": "on",
                },
                headers={
                    "Referer": "https://www.tradingview.com/"
                },
                timeout=15,
            )

            logger.info(
                "TradingView login status=%s",
                response.status_code
            )

            result = response.json()

            token = (
                result.get("user", {})
                .get("auth_token")
            )

            if token:

                logger.info(
                    "TradingView username/password login successful"
                )

                return token

            logger.warning(
                "TradingView login did not return auth_token: %s",
                str(result)[:500]
            )

        except Exception as e:

            logger.warning(
                "TradingView username/password login failed: %s",
                e
            )

        return None

    # ========================================================
    # SESSION IDS
    # ========================================================

    def _generate_session(self):

        letters = string.ascii_lowercase

        return (
            "qs_"
            + "".join(
                random.choice(letters)
                for _ in range(12)
            )
        )

    def _generate_chart_session(self):

        letters = string.ascii_lowercase

        return (
            "cs_"
            + "".join(
                random.choice(letters)
                for _ in range(12)
            )
        )

    # ========================================================
    # CONNECTION
    # ========================================================

    def _create_connection(self):

        self.ws = create_connection(
            self.WS_URL,
            timeout=self.WS_TIMEOUT,
            origin="https://data.tradingview.com",
            host="data.tradingview.com",
        )

    # ========================================================
    # MESSAGE
    # ========================================================

    def _prepend_header(self, message):

        return (
            "~m~"
            + str(len(message))
            + "~m~"
            + message
        )

    def _construct_message(self, func, params):

        message = json.dumps({
            "m": func,
            "p": params,
            "t": int(time.time()),
            "t_ms": int(time.time() * 1000),
        })

        return self._prepend_header(message)

    def _send_message(self, func, params):

        msg = self._construct_message(
            func,
            params
        )

        if self.ws_debug:
            logger.info(
                "SEND: %s",
                msg
            )

        self.ws.send(msg)

    # ========================================================
    # SYMBOL
    # ========================================================

    def _format_symbol(
        self,
        symbol,
        exchange,
        fut_contract=None
    ):

        # Already fully qualified
        if ":" in symbol:

            return symbol

        # Futures continuous contract
        if fut_contract is not None:

            return (
                f"{exchange}:"
                f"{symbol}"
                f"{int(fut_contract)}!"
            )

        return (
            f"{exchange}:"
            f"{symbol}"
        )

    # ========================================================
    # INTERVAL
    # ========================================================

    def _interval_value(self, interval):

        if isinstance(interval, Interval):

            return interval.value

        value = str(interval)

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
    # HEARTBEAT
    # ========================================================

    def _handle_heartbeat(self, raw):

        if raw.startswith("~m~"):

            matches = re.findall(
                r"~m~\d+~m~(.+)",
                raw
            )

            for payload in matches:

                if payload.startswith("~m~"):

                    try:
                        self.ws.send(
                            payload
                        )
                    except Exception:
                        pass

        elif raw.startswith("~m~5~m~~h~"):

            try:
                self.ws.send(raw)
            except Exception:
                pass

    # ========================================================
    # PARSER
    # ========================================================

    def _extract_messages(self, raw):

        messages = []

        pattern = re.compile(
            r"~m~(\d+)~m~"
        )

        pos = 0

        while pos < len(raw):

            match = pattern.search(
                raw,
                pos
            )

            if not match:
                break

            length = int(
                match.group(1)
            )

            start = match.end()
            end = start + length

            if end > len(raw):
                break

            payload = raw[
                start:end
            ]

            messages.append(
                payload
            )

            pos = end

        return messages

    def _parse_bar_value(self, value):

        if not isinstance(value, list):
            return None

        if len(value) < 6:
            return None

        try:

            timestamp = float(value[0])

            # TradingView sometimes returns milliseconds
            if timestamp > 10_000_000_000:
                timestamp /= 1000

            dt = datetime.fromtimestamp(
                timestamp,
                tz=timezone.utc
            )

            return {
                "Datetime": dt,
                "Open": float(value[1]),
                "High": float(value[2]),
                "Low": float(value[3]),
                "Close": float(value[4]),
                "Volume": float(value[5]),
            }

        except Exception:

            return None

    # ========================================================
    # PARSE MODERN DU
    # ========================================================

    def _parse_du(self, obj, bars):

        if not isinstance(obj, dict):
            return

        data = obj.get("p")

        if not isinstance(data, list):
            return

        if len(data) < 2:
            return

        payload = data[1]

        if not isinstance(payload, dict):
            return

        # Example:
        # {
        #   "sds_1": {
        #       "s": [...]
        #   }
        # }

        for series_data in payload.values():

            if not isinstance(series_data, dict):
                continue

            states = series_data.get("s")

            if not isinstance(states, list):
                continue

            for state in states:

                if not isinstance(state, dict):
                    continue

                value = state.get("v")

                bar = self._parse_bar_value(
                    value
                )

                if bar:

                    bars.append(bar)

    # ========================================================
    # PARSE TIMESCALE UPDATE
    # ========================================================

    def _parse_timescale_update(
        self,
        obj,
        bars
    ):

        payload = obj.get("p")

        if not isinstance(payload, list):
            return

        if len(payload) < 2:
            return

        data = payload[1]

        if not isinstance(data, dict):
            return

        for value in data.values():

            if not isinstance(value, dict):
                continue

            # Different protocol versions
            # can use node / s / st

            states = (
                value.get("s")
                or value.get("st")
            )

            if not states:
                continue

            if isinstance(states, dict):
                states = [states]

            if not isinstance(states, list):
                continue

            for state in states:

                if isinstance(state, dict):

                    bar_value = (
                        state.get("v")
                        or state.get("i")
                    )

                    bar = self._parse_bar_value(
                        bar_value
                    )

                    if bar:
                        bars.append(bar)

    # ========================================================
    # GET HIST
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
        
            symbol = self._format_symbol(
                symbol,
                exchange,
                fut_contract
            )
        
            interval_value = self._interval_value(interval)
        
            logger.info(
                "GET HIST: %s | TF=%s | BARS=%s | AUTH=%s",
                symbol,
                interval_value,
                n_bars,
                self.auth_method,
            )
        
            self._create_connection()
        
            bars = []
        
            try:
        
                # ====================================================
                # AUTH
                # ====================================================
        
                self._send_message(
                    "set_auth_token",
                    [self.token]
                )
        
                # ====================================================
                # CHART SESSION
                # ====================================================
        
                self._send_message(
                    "chart_create_session",
                    [
                        self.chart_session,
                        ""
                    ]
                )
        
                # ====================================================
                # RESOLVE SYMBOL
                # ====================================================
        
                session_type = (
                    "extended"
                    if extended_session
                    else "regular"
                )
        
                symbol_payload = json.dumps({
                    "symbol": symbol,
                    "adjustment": "splits",
                    "session": session_type,
                })
        
                self._send_message(
                    "resolve_symbol",
                    [
                        self.chart_session,
                        "symbol_1",
                        "=" + symbol_payload,
                    ]
                )
        
                # ====================================================
                # CREATE SERIES
                # ====================================================
        
                self._send_message(
                    "create_series",
                    [
                        self.chart_session,
                        "s1",
                        "s1",
                        "symbol_1",
                        interval_value,
                        int(n_bars),
                    ]
                )
        
                # ====================================================
                # TIMEZONE
                # ====================================================
        
                self._send_message(
                    "switch_timezone",
                    [
                        self.chart_session,
                        "exchange"
                    ]
                )
        
                # ====================================================
                # RECEIVE DATA
                # ====================================================
        
                start_time = time.time()
                completed = False
        
                while time.time() - start_time < self.WS_TIMEOUT:
        
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
        
                    if self.ws_debug:
                        logger.info(
                            "RECV: %s",
                            raw[:2000]
                        )
        
                    # ------------------------------------------------
                    # HEARTBEAT
                    # ------------------------------------------------
        
                    if "~m~~h~" in raw:
        
                        try:
                            self.ws.send(raw)
                        except Exception:
                            pass
        
                    # ------------------------------------------------
                    # EXTRACT TV MESSAGES
                    # ------------------------------------------------
        
                    messages = self._extract_messages(raw)
        
                    for message in messages:
        
                        try:
        
                            obj = json.loads(message)
        
                        except Exception:
        
                            continue
        
                        method = obj.get("m")
        
                        # --------------------------------------------
                        # SYMBOL ERROR
                        # --------------------------------------------
        
                        if method == "symbol_error":
        
                            params = obj.get("p", [])
        
                            reason = (
                                params[2]
                                if len(params) > 2
                                else "Unknown symbol error"
                            )
        
                            raise RuntimeError(
                                f"TradingView symbol error: "
                                f"{reason} | {symbol}"
                            )
        
                        # --------------------------------------------
                        # SERIES ERROR
                        # --------------------------------------------
        
                        if method == "series_error":
        
                            raise RuntimeError(
                                f"TradingView series error: "
                                f"{obj.get('p')}"
                            )
        
                        # --------------------------------------------
                        # CRITICAL ERROR
                        # --------------------------------------------
        
                        if method == "critical_error":
        
                            raise RuntimeError(
                                f"TradingView critical error: "
                                f"{obj.get('p')}"
                            )
        
                        # --------------------------------------------
                        # DATA
                        # --------------------------------------------
        
                        if method == "du":
        
                            self._parse_du(
                                obj,
                                bars
                            )
        
                        elif method == "timescale_update":
        
                            self._parse_timescale_update(
                                obj,
                                bars
                            )
        
                        # --------------------------------------------
                        # COMPLETE
                        # --------------------------------------------
        
                        elif method == "series_completed":
        
                            completed = True
        
                    # ------------------------------------------------
                    # STOP
                    # ------------------------------------------------
        
                    if completed and bars:
                        break
        
                # ====================================================
                # NO DATA
                # ====================================================
        
                if not bars:
        
                    logger.warning(
                        "No bars received for %s",
                        symbol
                    )
        
                    return pd.DataFrame(
                        columns=[
                            "Datetime",
                            "Open",
                            "High",
                            "Low",
                            "Close",
                            "Volume",
                            "symbol",
                        ]
                    )
        
                # ====================================================
                # DATAFRAME
                # ====================================================
        
                df = pd.DataFrame(bars)
        
                # Remove duplicates
                df = (
                    df.drop_duplicates(
                        subset=["Datetime"]
                    )
                    .sort_values("Datetime")
                    .reset_index(drop=True)
                )
        
                # ====================================================
                # TIMEZONE
                # ====================================================
        
                india = pytz.timezone(
                    "Asia/Kolkata"
                )
        
                if df["Datetime"].dt.tz is None:
        
                    df["Datetime"] = (
                        df["Datetime"]
                        .dt.tz_localize("UTC")
                    )
        
                df["Datetime"] = (
                    df["Datetime"]
                    .dt.tz_convert(india)
                    .dt.tz_localize(None)
                )
        
                # ====================================================
                # SYMBOL
                # ====================================================
        
                df.insert(
                    0,
                    "symbol",
                    symbol
                )
        
                logger.info(
                    "SUCCESS: %s candles received for %s",
                    len(df),
                    symbol
                )
        
                return df
        
            finally:
        
                try:
                    self.ws.close()
                except Exception:
                    pass
        
                self.ws = None
        
            # ------------------------------------------------
            # BUILD DF
            # ------------------------------------------------

            if not bars:

                logger.warning(
                    "No bars received for %s",
                    symbol
                )

                return pd.DataFrame(
                    columns=[
                        "Datetime",
                        "Open",
                        "High",
                        "Low",
                        "Close",
                        "Volume",
                        "symbol",
                    ]
                )

            df = pd.DataFrame(
                bars
            )

            # Remove duplicate candles
            df = (
                df.drop_duplicates(
                    subset=["Datetime"]
                )
                .sort_values(
                    "Datetime"
                )
                .reset_index(
                    drop=True
                )
            )

            # Convert UTC -> India
            india = pytz.timezone(
                "Asia/Kolkata"
            )

            if df["Datetime"].dt.tz is None:

                df["Datetime"] = (
                    df["Datetime"]
                    .dt.tz_localize("UTC")
                )

            df["Datetime"] = (
                df["Datetime"]
                .dt.tz_convert(india)
                .dt.tz_localize(None)
            )

            df.insert(
                0,
                "symbol",
                symbol
            )

            logger.info(
                "Received %s candles for %s",
                len(df),
                symbol
            )

            return df

        finally:

            try:

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

        url = self.SEARCH_URL.format(
            text,
            exchange
        )

        try:

            response = self.http.get(
                url,
                timeout=15
            )

            response.raise_for_status()

            text_data = response.text

            text_data = re.sub(
                r"</?em>",
                "",
                text_data
            )

            return response.json()

        except Exception as e:

            logger.warning(
                "search_symbol failed: %s",
                e
            )

            return []
