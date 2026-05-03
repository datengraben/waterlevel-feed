from datetime import datetime, timedelta
import os
import re
import xml.etree.ElementTree as ET

import pytz
import requests

STATION = "GIESSEN KLÄRWERK"
RIVER = "LAHN"
STATION_URL = "https://www.pegelonline.wsv.de/gast/stammdaten?pegelnummer=25800100"
DATA_URL_TEMPLATE = (
    "https://www.pegelonline.wsv.de/webservices/files/Wasserstand+Rohdaten"
    "/LAHN/GIESSEN+KL%C3%84RWERK/{}/down.txt"
)
FEED_FILE = "feed.xml"
MAX_ITEMS = 20

local_tz = pytz.timezone("Europe/Berlin")
utc_tz = pytz.utc


def fetch_latest_level(date_str):
    url = DATA_URL_TEMPLATE.format(date_str)
    rsp = requests.get(url, timeout=30)
    rsp.raise_for_status()
    data = rsp.text.split("\n")[12:-1]
    data = [row.replace("\r", "") for row in data]
    rows = [(row.split("#")[0], row.split("#")[1]) for row in data if "#" in row]
    valid = [r for r in rows if not re.search("X", r[1])]
    if not valid:
        return None, None
    time_str, level_str = valid[-1]
    return time_str, int(level_str)


def parse_threshold(env_var):
    val = os.environ.get(env_var)
    return int(val) if val else None


def to_utc(date_str, time_str):
    if time_str == "24:00":
        time_str = "00:00"
        dt = datetime.strptime(date_str + " " + time_str, "%d.%m.%Y %H:%M") + timedelta(days=1)
    else:
        dt = datetime.strptime(date_str + " " + time_str, "%d.%m.%Y %H:%M")
    return local_tz.localize(dt, is_dst=None).astimezone(utc_tz)


def load_existing_items():
    if not os.path.exists(FEED_FILE):
        return []
    tree = ET.parse(FEED_FILE)
    channel = tree.getroot().find("channel")
    if channel is None:
        return []
    items = []
    for item in channel.findall("item"):
        items.append({
            "guid": item.findtext("guid", ""),
            "title": item.findtext("title", ""),
            "description": item.findtext("description", ""),
            "pubDate": item.findtext("pubDate", ""),
            "link": item.findtext("link", ""),
        })
    return items


def write_feed(items):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = f"Wasserstand {STATION} ({RIVER})"
    ET.SubElement(channel, "link").text = STATION_URL
    ET.SubElement(channel, "description").text = (
        f"Wasserstand-Warnungen für Pegel {STATION} an der {RIVER}"
    )
    ET.SubElement(channel, "language").text = "de"

    for item in items[-MAX_ITEMS:]:
        el = ET.SubElement(channel, "item")
        ET.SubElement(el, "title").text = item["title"]
        ET.SubElement(el, "link").text = item["link"]
        ET.SubElement(el, "description").text = item["description"]
        ET.SubElement(el, "pubDate").text = item["pubDate"]
        ET.SubElement(el, "guid", isPermaLink="false").text = item["guid"]

    ET.indent(rss, space="  ")
    tree = ET.ElementTree(rss)
    with open(FEED_FILE, "wb") as f:
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding="unicode" if False else "utf-8", xml_declaration=False)


def main():
    warning_threshold = parse_threshold("WATER_LEVEL_WARNING")
    alert_threshold = parse_threshold("WATER_LEVEL_ALERT")

    d = datetime.strftime(datetime.now(), "%d.%m.%Y")
    time_str, level = fetch_latest_level(d)

    if level is None:
        print("No valid data available.")
        return

    print(f"{d} {time_str}: {level} cm")

    # Determine severity
    if alert_threshold is not None and level >= alert_threshold:
        severity = "alert"
        prefix = "🔴 ALARM"
    elif warning_threshold is not None and level >= warning_threshold:
        severity = "warning"
        prefix = "🟡 Warnung"
    elif warning_threshold is None and alert_threshold is None:
        severity = "info"
        prefix = "📍"
    else:
        print(f"Level {level} cm below warning threshold ({warning_threshold} cm) — no item emitted.")
        return

    pub_dt = to_utc(d, time_str)
    guid = f"{STATION_URL}#{pub_dt.strftime('%Y%m%dT%H%M%SZ')}"

    existing = load_existing_items()

    if any(item["guid"] == guid for item in existing):
        print(f"Item for {time_str} already in feed — skipping.")
        return

    threshold_info = ""
    if warning_threshold:
        threshold_info += f"Warnschwelle: {warning_threshold} cm. "
    if alert_threshold:
        threshold_info += f"Alarmschwelle: {alert_threshold} cm. "

    new_item = {
        "guid": guid,
        "title": f"{prefix} Pegel {level} cm – {STATION} ({d} {time_str})",
        "description": (
            f"Aktueller Wasserstand: {level} cm. "
            f"{threshold_info}"
            f"Station: {STATION}, Fluss: {RIVER}. "
            f"Datenquelle: {STATION_URL}"
        ),
        "pubDate": pub_dt.strftime("%a, %d %b %Y %H:%M:%S +0000"),
        "link": STATION_URL,
    }

    existing.append(new_item)
    write_feed(existing)
    print(f"Feed updated: [{severity}] {level} cm → {FEED_FILE}")


if __name__ == "__main__":
    main()
