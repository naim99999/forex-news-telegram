import os
import json
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

LATEST_FILE = DATA_DIR / "latest.json"
STATE_FILE = DATA_DIR / "state.json"

BD_TZ = timezone(timedelta(hours=6))


def now_utc():
    return datetime.now(timezone.utc)


def parse_datetime(date_string):
    if not date_string:
        return None

    value = date_string.strip()

    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        pass

    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue

    return None


def get_feed():
    headers = {
        "User-Agent": "Mozilla/5.0 Forex News Dashboard"
    }

    r = requests.get(
        FEED_URL,
        headers=headers,
        timeout=25
    )

    r.raise_for_status()
    return r.json()


def load_json(path, default):
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram credentials missing.")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": True
    }

    try:
        r = requests.post(
            url,
            json=payload,
            timeout=20
        )

        print("Telegram:", r.status_code, r.text[:300])

        return r.ok

    except Exception as e:
        print("Telegram error:", e)
        return False


def event_id(event):
    date = event.get("date", "")
    title = event.get("title", "")
    currency = event.get("country", "")
    return f"{date}|{currency}|{title}"


def impact_icon(impact):
    value = str(impact or "").lower()

    if "high" in value:
        return "🔴"

    if "medium" in value:
        return "🟠"

    return "⚪"


def polarity(title):
    t = title.lower()

    negative = [
        "unemployment rate",
        "jobless claims",
        "initial claims",
        "continuing claims",
        "unemployment claims"
    ]

    positive = [
        "nonfarm",
        "non-farm",
        "nfp",
        "employment change",
        "retail sales",
        "industrial production",
        "gdp",
        "gross domestic",
        "manufacturing pmi",
        "services pmi",
        "average hourly earnings"
    ]

    context = [
        "interest rate",
        "fomc",
        "fed",
        "ecb",
        "boe",
        "boj",
        "rba",
        "boc",
        "rate decision",
        "cpi",
        "inflation",
        "ppi"
    ]

    if any(x in t for x in negative):
        return "negative"

    if any(x in t for x in positive):
        return "positive"

    if any(x in t for x in context):
        return "context"

    return "context"


def number(value):
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    replacements = [
        (",", ""),
        ("%", ""),
        ("K", "000"),
        ("M", "000000"),
        ("B", "000000000")
    ]

    try:
        cleaned = text

        if cleaned.endswith("K"):
            return float(cleaned[:-1].replace(",", "")) * 1000

        if cleaned.endswith("M"):
            return float(cleaned[:-1].replace(",", "")) * 1000000

        if cleaned.endswith("B"):
            return float(cleaned[:-1].replace(",", "")) * 1000000000

        return float(cleaned.replace(",", "").replace("%", ""))

    except Exception:
        return None


def get_bias(event):
    actual = number(event.get("actual"))
    forecast = number(event.get("forecast"))

    if actual is None or forecast is None:
        return "CONTEXT"

    kind = polarity(event.get("title", ""))

    if kind == "positive":

        if actual > forecast:
            return "BULLISH"

        if actual < forecast:
            return "BEARISH"

    elif kind == "negative":

        if actual < forecast:
            return "BULLISH"

        if actual > forecast:
            return "BEARISH"

    return "CONTEXT"


def pair_direction(currency, bias):
    currency = str(currency or "").upper()

    if bias == "BULLISH":

        mapping = {
            "USD": {
                "EURUSD": "DOWN",
                "GBPUSD": "DOWN",
                "AUDUSD": "DOWN",
                "NZDUSD": "DOWN",
                "USDJPY": "UP",
                "USDCHF": "UP",
                "USDCAD": "UP",
                "XAUUSD": "DOWN"
            },
            "EUR": {
                "EURUSD": "UP"
            },
            "GBP": {
                "GBPUSD": "UP"
            },
            "JPY": {
                "USDJPY": "DOWN"
            },
            "AUD": {
                "AUDUSD": "UP"
            },
            "NZD": {
                "NZDUSD": "UP"
            },
            "CAD": {
                "USDCAD": "DOWN"
            },
            "CHF": {
                "USDCHF": "DOWN"
            }
        }

        return mapping.get(currency, {})

    if bias == "BEARISH":

        mapping = {
            "USD": {
                "EURUSD": "UP",
                "GBPUSD": "UP",
                "AUDUSD": "UP",
                "NZDUSD": "UP",
                "USDJPY": "DOWN",
                "USDCHF": "DOWN",
                "USDCAD": "DOWN",
                "XAUUSD": "UP"
            },
            "EUR": {
                "EURUSD": "DOWN"
            },
            "GBP": {
                "GBPUSD": "DOWN"
            },
            "JPY": {
                "USDJPY": "UP"
            },
            "AUD": {
                "AUDUSD": "DOWN"
            },
            "NZD": {
                "NZDUSD": "DOWN"
            },
            "CAD": {
                "USDCAD": "UP"
            },
            "CHF": {
                "USDCHF": "UP"
            }
        }

        return mapping.get(currency, {})

    return {}


def fmt_time(dt):
    if not dt:
        return "Unknown"

    local = dt.astimezone(BD_TZ)

    return local.strftime("%d %b %Y • %I:%M %p")


def compact_result(event, bias):
    title = event.get("title", "News")
    currency = event.get("country", "")
    actual = event.get("actual", "-")
    forecast = event.get("forecast", "-")
    previous = event.get("previous", "-")

    lines = [
        "📊 NEWS RESULT",
        "",
        f"{impact_icon(event.get('impact'))} {currency} • {title}",
        f"Actual: {actual}",
        f"Forecast: {forecast}",
        f"Previous: {previous}",
        "",
        f"Bias: {bias}"
    ]

    directions = pair_direction(currency, bias)

    if directions:
        lines.append("")

        for pair, direction in directions.items():
            icon = "🟢" if direction == "UP" else "🔴"
            lines.append(f"{icon} {pair} {direction}")

    return "\n".join(lines)


def compact_before(event):
    title = event.get("title", "News")
    currency = event.get("country", "")
    forecast = event.get("forecast", "-")
    previous = event.get("previous", "-")

    lines = [
        "⏳ NEWS IN ~10 MIN",
        "",
        f"{impact_icon(event.get('impact'))} {currency} • {title}",
        f"Forecast: {forecast}",
        f"Previous: {previous}",
        "",
        "⚠️ Watch market reaction"
    ]

    return "\n".join(lines)


def is_high_impact(event):
    impact = str(event.get("impact", "")).lower()

    return "high" in impact


def main():

    print("Starting Forex Factory analyzer...")

    events = get_feed()

    if not isinstance(events, list):
        raise RuntimeError("Forex Factory response is not a list")

    state = load_json(
        STATE_FILE,
        {
            "before_sent": [],
            "result_sent": []
        }
    )

    latest_events = []

    now = now_utc()

    for event in events:

        if not is_high_impact(event):
            continue

        dt = parse_datetime(event.get("date"))

        if not dt:
            continue

        uid = event_id(event)

        bias = get_bias(event)

        directions = pair_direction(
            event.get("country"),
            bias
        )

        item = {
            "id": uid,
            "title": event.get("title"),
            "currency": event.get("country"),
            "impact": event.get("impact"),
            "date": event.get("date"),
            "time_bd": fmt_time(dt),
            "actual": event.get("actual"),
            "forecast": event.get("forecast"),
            "previous": event.get("previous"),
            "bias": bias,
            "directions": directions
        }

        latest_events.append(item)

        diff_minutes = (dt - now).total_seconds() / 60

        # -------------------------
        # 10 MINUTE WARNING
        # -------------------------

        if 7 <= diff_minutes <= 12:

            if uid not in state["before_sent"]:

                message = compact_before(event)

                if telegram(message):

                    state["before_sent"].append(uid)

                    print(
                        "10-minute alert sent:",
                        event.get("title")
                    )

        # -------------------------
        # RESULT
        # -------------------------

        if -5 <= diff_minutes <= 0:

            actual = event.get("actual")

            if actual not in [None, "", "-"]:

                if uid not in state["result_sent"]:

                    message = compact_result(
                        event,
                        bias
                    )

                    if telegram(message):

                        state["result_sent"].append(uid)

                        print(
                            "Result sent:",
                            event.get("title")
                        )

    # Keep state small

    state["before_sent"] = state["before_sent"][-500:]
    state["result_sent"] = state["result_sent"][-500:]

    save_json(
        STATE_FILE,
        state
    )

    # Dashboard data

    latest_events.sort(
        key=lambda x: x.get("date") or ""
    )

    dashboard = {
        "updated_utc": now.isoformat(),
        "updated_bd": now.astimezone(BD_TZ).strftime(
            "%d %b %Y • %I:%M:%S %p"
        ),
        "source": "Forex Factory Calendar",
        "market": "REAL MARKET • OTC OFF",
        "events": latest_events[:100]
    }

    save_json(
        LATEST_FILE,
        dashboard
    )

    print(
        f"Processed {len(latest_events)} high-impact events."
    )


if __name__ == "__main__":
    main()
