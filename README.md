# Dizi News → Telegram Bot

Notifies you on Telegram whenever there's news about the Turkish series
world: new fragmanlar, new series announcements, cast/kadro changes,
reyting results, etc. — pulled from all major Turkish outlets, not just
one channel's social media.

## How it works

It queries [Google News RSS](https://news.google.com/rss) with a set of
Turkish search terms (see `QUERIES` in `dizi_bot.py`) every time it runs,
compares results against `seen.json` (what it already sent you), and
Telegram-messages you anything new. This covers Hürriyet, Milliyet,
CNN Türk, NTV, Sabah, Habertürk, and dozens more automatically — including
whatever they report about TRT1, ATV, Show TV, Kanal D, Star TV, etc.

## 1. Create your Telegram bot

1. Open Telegram, message **@BotFather**, send `/newbot`, follow the
   prompts. You'll get a **bot token** like `123456789:AAExxxxxxxxxxxx`.
2. Start a chat with your new bot (search its username, hit Start) — or
   add it to a group/channel where you want the alerts.
3. Get your **chat id**:
   - Send any message to the bot first.
   - Then open in a browser:
     `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Look for `"chat":{"id": ...}` in the JSON response — that number
     (can be negative for groups) is your `TELEGRAM_CHAT_ID`.

## 2. Choose where it runs

### Option A — GitHub Actions (free, no server needed) — recommended

1. Create a new **private** GitHub repo and push this folder to it.
2. In the repo: **Settings → Secrets and variables → Actions → New
   repository secret**, add:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. That's it — `.github/workflows/dizi-bot.yml` runs the bot every 20
   minutes automatically. You can also trigger it manually from the
   **Actions** tab (`Run workflow`).
4. The workflow commits the updated `seen.json` back to the repo after
   each run so it remembers what it already sent you.

### Option B — Your own computer / server (cron)

1. `pip install -r requirements.txt`
2. Set the two environment variables, e.g. in your shell profile:
   ```bash
   export TELEGRAM_BOT_TOKEN="123456789:AAExxxxxxxxxxxx"
   export TELEGRAM_CHAT_ID="123456789"
   ```
3. Test it once: `python3 dizi_bot.py`
4. Add a cron job to run it every 20 minutes:
   ```
   */20 * * * * cd /path/to/dizi-bot && /usr/bin/python3 dizi_bot.py >> bot.log 2>&1
   ```
   (`crontab -e` to edit your crontab.)

## 3. Customize what it watches

Open `dizi_bot.py` and edit the `QUERIES` dict — each entry is a label
plus a Turkish search phrase. Add more channels, specific series names
you follow, actor names, etc.:

```python
QUERIES = {
    "Dizi haberleri": "dizi haberleri",
    "Yeni dizi": "yeni dizi başlıyor",
    "Dizi fragman": "dizi fragmanı",
    "Kadro / oyuncu değişikliği": "dizi kadrosuna katıldı OR diziden ayrılıyor",
    "Reyting": "dizi reyting sonuçları",
    "TRT1 dizi": "TRT1 dizi",
    "ATV dizi": "ATV dizi",
    "Show TV dizi": "Show TV dizi",
    "Kanal D dizi": "Kanal D dizi",
    "Star TV dizi": "Star TV dizi",
    # Example: follow one specific series closely
    # "Yalı Çapkını": "Yalı Çapkını",
}
```

More queries = more API calls per run but each is free and fast; 10–20
queries is no problem.

## 4. Notes & limits

- Google News RSS has no official rate limit but don't set the schedule
  to run every minute — 15–30 min intervals is plenty for news.
- Some stories will appear under more than one query (e.g. a fragman
  story matching both "Dizi fragman" and "ATV dizi") — the script already
  de-duplicates by article link within each run and across runs.
- If you want to also watch a channel's own YouTube uploads (where
  fragmanlar often post first, sometimes before any news site picks it
  up), that's a good follow-up: YouTube's Data API can watch a channel's
  uploads playlist for free. Ask if you'd like that added.
