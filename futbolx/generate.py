#!/usr/bin/env python3
"""
futbolx/generate.py

Pulls live-sports event JSON from futbol-x.xyz and builds:
  - futbolx.m3u8       combined M3U playlist, grouped by category
  - futbolx_epg.xml.gz  matching XMLTV EPG (full schedule, using starts_at/ends_at)

Source quirks (confirmed by hand-checking the API):
  - Each category JSON returns {success, streams: [{category, streams: [event...]}]}
  - Each event has one or more inner "streams" (multi-feed events, e.g. backup feeds).
  - Stream URLs are a MIX of direct .m3u8 links and embed-page URLs
    (e.g. embedindia.st, pooembed.eu). Both are included as-is; sorting
    playable vs embed-only is left for a later pass (see liveeventsfilter.py
    in the repo root for the playability-check approach if needed).
  - starts_at / ends_at are naive ISO timestamps (no offset) and are treated
    as UTC -- confirmed against a real WWE Raw broadcast time.
"""

import gzip
import sys
import xml.sax.saxutils as saxutils
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = "https://futbol-x.xyz"

# One JSON file per category. Key = output group-title, value = endpoint filename.
CATEGORY_FEEDS = {
    "Football": "football.json",
    "Motorsports": "motorsports.json",
    "Basketball": "basketball.json",
    "Fights": "fights.json",
    "NFL": "nfl.json",
    "MLB": "mlb.json",
    "Wrestling": "wrestling.json",
}

# Source timestamps have no timezone info; treat them as this offset.
SOURCE_TZ = timezone.utc

TIMEOUT = 20
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

OUTPUT_DIR = Path(__file__).resolve().parent
M3U_OUTPUT = OUTPUT_DIR / "futbolx.m3u8"
EPG_OUTPUT = OUTPUT_DIR / "futbolx_epg.xml.gz"

TVG_ID_PREFIX = "futbolx-"

# Public raw URL where the EPG will live once committed - embedded in the
# M3U header so players (TiviMate, etc.) can auto-load the guide.
EPG_RAW_URL = (
    "https://raw.githubusercontent.com/BuddyChewChew/sports/main/"
    "futbolx/futbolx_epg.xml.gz"
)


def fetch_category(filename: str) -> dict | None:
    """Fetch and parse one category JSON file. Returns None on failure."""
    url = f"{BASE_URL}/api/{filename}"
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            print(f"  ! {filename}: API reported success=false")
            return None
        return data
    except requests.RequestException as exc:
        print(f"  ! {filename}: request failed ({exc})")
        return None
    except ValueError as exc:
        print(f"  ! {filename}: invalid JSON ({exc})")
        return None


def parse_timestamp(value: str | None) -> datetime | None:
    """Parse a naive ISO timestamp from the source and attach SOURCE_TZ."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SOURCE_TZ)
    return dt


def xmltv_time(dt: datetime) -> str:
    """Format a datetime as XMLTV timestamp, e.g. 20260623000000 +0000."""
    return dt.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S +0000")


def collect_channels(group_title: str, category_data: dict) -> list[dict]:
    """
    Flatten one category's JSON into a list of channel dicts ready for
    M3U + EPG output. Multi-feed events produce one channel entry per feed,
    all sharing the same tvg_id so the EPG guide applies to every feed.
    """
    channels = []

    for block in category_data.get("streams", []):
        block_category = block.get("category") or group_title

        for event in block.get("streams", []):
            name = event.get("name") or "Unknown Event"
            uri_name = event.get("uri_name")
            starts_at_raw = event.get("starts_at") or ""
            if not uri_name:
                # Fall back to a slug derived from name + start time so two
                # differently-dated events with the same name don't collide.
                slug_base = name.lower().replace(" ", "-").replace(":", "")
                date_part = starts_at_raw[:10].replace("-", "") if starts_at_raw else "nodate"
                uri_name = f"{slug_base}-{date_part}"
            poster = event.get("poster") or ""
            tag = event.get("tag") or block_category
            starts_at = parse_timestamp(event.get("starts_at"))
            ends_at = parse_timestamp(event.get("ends_at"))

            feeds = event.get("streams") or []
            tvg_id = f"{TVG_ID_PREFIX}{uri_name}"

            for idx, feed in enumerate(feeds, start=1):
                feed_url = feed.get("url")
                if not feed_url:
                    continue
                feed_title = feed.get("title") or "Main Feed"

                # Only suffix the display name when there's more than one feed,
                # so single-feed events (the vast majority) stay clean.
                if len(feeds) > 1:
                    display_name = f"{name} ({feed_title})"
                else:
                    display_name = name

                channels.append(
                    {
                        "tvg_id": tvg_id,
                        "event_name": name,
                        "display_name": display_name,
                        "group_title": group_title,
                        "logo": poster,
                        "tag": tag,
                        "url": feed_url,
                        "starts_at": starts_at,
                        "ends_at": ends_at,
                        "feed_index": idx,
                    }
                )

    return channels


def build_m3u(all_channels: list[dict]) -> str:
    lines = [f'#EXTM3U url-tvg="{EPG_RAW_URL}"']
    for ch in all_channels:
        extinf = (
            f'#EXTINF:-1 tvg-id="{ch["tvg_id"]}" '
            f'tvg-logo="{ch["logo"]}" '
            f'group-title="{ch["group_title"]}",{ch["display_name"]}'
        )
        lines.append(extinf)
        lines.append(ch["url"])
    return "\n".join(lines) + "\n"


def build_epg(all_channels: list[dict]) -> bytes:
    """Build a full-schedule XMLTV guide: one <channel> per unique tvg_id,
    one <programme> per channel entry that has valid start/end times."""

    seen_channel_ids = {}
    for ch in all_channels:
        if ch["tvg_id"] not in seen_channel_ids:
            # Use the base event name for the channel display-name (strip any
            # "(Feed Title)" suffix added for multi-feed events in the M3U).
            seen_channel_ids[ch["tvg_id"]] = ch.get("event_name", ch["display_name"])

    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<tv>"]

    for tvg_id, display_name in seen_channel_ids.items():
        esc_name = saxutils.escape(display_name)
        xml_parts.append(f'  <channel id="{tvg_id}">')
        xml_parts.append(f"    <display-name>{esc_name}</display-name>")
        xml_parts.append("  </channel>")

    seen_programmes = set()
    for ch in all_channels:
        if not ch["starts_at"] or not ch["ends_at"]:
            continue
        start = xmltv_time(ch["starts_at"])
        stop = xmltv_time(ch["ends_at"])
        dedupe_key = (ch["tvg_id"], start, stop)
        if dedupe_key in seen_programmes:
            continue
        seen_programmes.add(dedupe_key)

        esc_title = saxutils.escape(ch["event_name"])
        esc_tag = saxutils.escape(str(ch["tag"]))
        xml_parts.append(
            f'  <programme start="{start}" stop="{stop}" channel="{ch["tvg_id"]}">'
        )
        xml_parts.append(f"    <title>{esc_title}</title>")
        xml_parts.append(f"    <category>{esc_tag}</category>")
        xml_parts.append("  </programme>")

    xml_parts.append("</tv>")
    xml_str = "\n".join(xml_parts) + "\n"
    return gzip.compress(xml_str.encode("utf-8"))


def main() -> int:
    all_channels: list[dict] = []

    print("Fetching futbol-x.xyz category feeds...")
    for group_title, filename in CATEGORY_FEEDS.items():
        print(f"  -> {group_title} ({filename})")
        data = fetch_category(filename)
        if data is None:
            continue
        channels = collect_channels(group_title, data)
        print(f"     {len(channels)} channel entries")
        all_channels.extend(channels)

    if not all_channels:
        print("No channels collected from any feed -- aborting without overwriting outputs.")
        return 1

    print(f"\nTotal channel entries: {len(all_channels)}")

    m3u_text = build_m3u(all_channels)
    M3U_OUTPUT.write_text(m3u_text, encoding="utf-8")
    print(f"Wrote {M3U_OUTPUT} ({len(all_channels)} entries)")

    epg_bytes = build_epg(all_channels)
    EPG_OUTPUT.write_bytes(epg_bytes)
    print(f"Wrote {EPG_OUTPUT} ({len(epg_bytes)} bytes gzipped)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
