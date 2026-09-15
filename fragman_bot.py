#!/usr/bin/env python3
"""
Dizi Fragman -> Telegram Bot
-----------------------------
Watches the official YouTube channels of TRT1, ATV, Show TV, Kanal D,
Star TV (edit the list below to add/remove channels), and notifies you on
Telegram the moment a new video whose title looks like a "fragman"
(trailer / bölüm tanıtımı) is uploaded.

Why YouTube instead of news sites:
  - Channels post fragmanlar to YouTube directly and immediately — this is
    the actual primary source, not a news site reporting on it later.
  - YouTube provides a free RSS feed per channel
    (https://www.youtube.com/feeds/videos.xml?channel_id=...) with NO API
    key, NO quota, and NO login required. It typically reflects new
    uploads within minutes.

Setup required before first run: verify CHANNELS below. Handles
(the "@something" in a channel's URL) occasionally change hands or get
rebranded, so don't trust the pre-filled ones blindly — see README.
"""

import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

import feedparser
import requests

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "PUT_YOUR_CHAT_ID_HERE")

SEEN_FILE = Path(__file__).parent / "seen_fragman.json"
CHANNEL_ID_CACHE_FILE = Path(__file__).parent / "channel_ids.json"
MAX_SEEN = 3000

# --- VERIFY THESE BEFORE FIRST RUN (see README "Step 0") -------------------
# label -> channel URL (handle form, e.g. https://www.youtube.com/@something)
CHANNELS = {
    "TRT1": "https://www.youtube.com/@trt1",
    "ATV": "https://www.youtube.com/@atvturkiye",
    "Show TV": "https://www.youtube.com/@showtv",
    "Kanal D": "https://www.youtube.com/@kanald",
    "Star TV": "https://www.youtube.com/@StarTVResmi",
    "NOW TV": "https://www.youtube.com/@nowtvturkiye",
}
# -----------------------------------------------------------------------

# A video only counts as a "fragman" notification if its title contains one
# of these (case-insensitive, Turkish-aware). Edit freely.
FRAGMAN_KEYWORDS = [
    "fragman", "fragmanı", "fragmanı yayınlandı",
    "tanıtım", "tanıtımı",
    "yeni bölüm", "yeni sezon",
    "teaser", "trailer", "yakında"
]

YT_RSS = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
REQUEST_TIMEOUT = 15


# --------------------------------------------------------------------------
# CHANNEL ID RESOLUTION (handle/URL -> UC... id, cached to a file)
# --------------------------------------------------------------------------

def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default
    return default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")


def resolve_channel_id(url: str) -> str | None:
    """Fetch a channel page and extract its UC... channel id."""
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"[warn] could not fetch channel page {url}: {exc}", file=sys.stderr)
        return None

    # The channel id shows up in a canonical link and/or embedded JSON.
    match = re.search(r'"channelId":"(UC[\w-]{20,})"', resp.text)
    if not match:
        match = re.search(r'/channel/(UC[\w-]{20,})"', resp.text)
    return match.group(1) if match else None


def get_channel_ids() -> dict:
    """Return {label: channel_id}, resolving+caching handles as needed."""
    cache = load_json(CHANNEL_ID_CACHE_FILE, {})
    changed = False
    result = {}
    for label, url in CHANNELS.items():
        if url in cache:
            result[label] = cache[url]
            continue
        cid = resolve_channel_id(url)
        if cid:
            cache[url] = cid
            result[label] = cid
            changed = True
            print(f"[info] resolved {label} -> {cid}")
        else:
            print(f"[warn] could not resolve channel id for {label} ({url}) — skipping this run", file=sys.stderr)
        time.sleep(1)
    if changed:
        save_json(CHANNEL_ID_CACHE_FILE, cache)
    return result


# --------------------------------------------------------------------------
# FETCH + FILTER
# --------------------------------------------------------------------------

def is_fragman(title: str) -> bool:
    t = title.lower().replace("ı", "i")
    return any(kw.lower().replace("ı", "i") in t for kw in FRAGMAN_KEYWORDS)


def fetch_channel_videos(label: str, channel_id: str):
    url = YT_RSS.format(channel_id=channel_id)
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"[warn] failed to fetch YouTube feed for {label}: {exc}", file=sys.stderr)
        return []

    parsed = feedparser.parse(resp.content)
    items = []
    for entry in parsed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "")
        if not title or not link or not is_fragman(title):
            continue
        items.append({
            "id": entry.get("yt_videoid", link),
            "label": label,
            "title": title,
            "link": link,
            "published": entry.get("published", ""),
        })
    return items


def fetch_all(channel_ids: dict):
    all_items = []
    for label, cid in channel_ids.items():
        all_items.extend(fetch_channel_videos(label, cid))
        time.sleep(1)
    return all_items


# --------------------------------------------------------------------------
# TELEGRAM
# --------------------------------------------------------------------------

def send_telegram_message(text: str) -> bool:
    if TELEGRAM_BOT_TOKEN.startswith("PUT_YOUR") or TELEGRAM_CHAT_ID.startswith("PUT_YOUR"):
        print("[error] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not configured.", file=sys.stderr)
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        resp = requests.post(url, data=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        print(f"[error] Telegram send failed: {exc} | body={getattr(exc.response, 'text', '')}", file=sys.stderr)
        return False


def escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_message(item: dict) -> str:
    title = escape_html(item["title"])
    label = escape_html(item["label"])
    return f"🎬 <b>{title}</b>\n📺 {label}\n{item['link']}"


# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------

def main():
    seen = set(load_json(SEEN_FILE, []))
    first_run = len(seen) == 0

    channel_ids = get_channel_ids()
    if not channel_ids:
        print("[error] no channel ids resolved — check CHANNELS in the script.", file=sys.stderr)
        return

    items = fetch_all(channel_ids)

    if first_run:
        all_ids = {it["id"] for it in items}
        save_json(SEEN_FILE, list(all_ids))
        print(f"First run: recorded {len(all_ids)} existing fragman video(s) as baseline, sent nothing.")
        return

    new_items = {it["id"]: it for it in items if it["id"] not in seen}.values()

    if not new_items:
        print("No new fragmanlar.")
        return

    print(f"Found {len(new_items)} new fragman video(s). Sending to Telegram...")
    sent = 0
    for it in new_items:
        if send_telegram_message(format_message(it)):
            seen.add(it["id"])
            sent += 1
            time.sleep(1.5)

    save_json(SEEN_FILE, list(seen)[-MAX_SEEN:])
    print(f"Sent {sent}/{len(new_items)} item(s).")


if __name__ == "__main__":
    main()
