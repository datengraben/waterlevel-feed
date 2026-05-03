import pytest
import scrape

# 12 header lines + data rows matching the pegelonline format
def _response(*rows):
    return "\n".join(["h"] * 12 + list(rows) + [""])


# --- parse_response (RED: function does not exist yet) ---

def test_parse_response_returns_last_valid():
    text = _response("00:15#232", "01:00#XXX,XXX", "01:15#240")
    assert scrape.parse_response(text) == ("01:15", 240)

def test_parse_response_all_invalid():
    assert scrape.parse_response(_response("00:15#XXX,XXX")) == (None, None)

def test_parse_response_skips_x_entries():
    text = _response("00:15#250", "00:30#XXX,XXX")
    assert scrape.parse_response(text) == ("00:15", 250)


# --- parse_threshold ---

def test_parse_threshold_unset():
    assert scrape.parse_threshold("_NO_SUCH_VAR") is None

def test_parse_threshold_set(monkeypatch):
    monkeypatch.setenv("WATER_LEVEL_WARNING", "250")
    assert scrape.parse_threshold("WATER_LEVEL_WARNING") == 250


# --- to_utc ---

def test_to_utc_summer_offset():
    dt = scrape.to_utc("06.06.2023", "20:00")  # CEST = UTC+2
    assert dt.hour == 18

def test_to_utc_midnight_rollover():
    # 24:00 local → 07.06 00:00 CEST → 06.06 22:00 UTC
    dt = scrape.to_utc("06.06.2023", "24:00")
    assert dt.day == 6 and dt.hour == 22


# --- write_feed / load_existing_items ---

ITEM = {
    "guid": "http://x.example#1",
    "title": "Test",
    "description": "desc",
    "pubDate": "Mon, 06 Jun 2023 18:00:00 +0000",
    "link": "http://x.example",
}

def test_feed_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr(scrape, "FEED_FILE", str(tmp_path / "feed.xml"))
    scrape.write_feed([ITEM])
    items = scrape.load_existing_items()
    assert len(items) == 1
    assert items[0]["title"] == "Test"
    assert items[0]["guid"] == ITEM["guid"]

def test_feed_caps_at_max_items(monkeypatch, tmp_path):
    monkeypatch.setattr(scrape, "FEED_FILE", str(tmp_path / "feed.xml"))
    scrape.write_feed([{**ITEM, "guid": f"g{i}"} for i in range(25)])
    assert len(scrape.load_existing_items()) == scrape.MAX_ITEMS

def test_load_returns_empty_without_file(monkeypatch, tmp_path):
    monkeypatch.setattr(scrape, "FEED_FILE", str(tmp_path / "missing.xml"))
    assert scrape.load_existing_items() == []
