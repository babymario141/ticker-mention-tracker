#!/usr/bin/env python3
"""
$TICKER mention + sentiment collector for X (Twitter).

Runs on a schedule (GitHub Actions cron, or any machine with cron/Task
Scheduler). Each run:
  1. Calls X API's tweets/counts/recent to get the mention VOLUME for the
     query window since the last run.
  2. Calls tweets/search/recent to pull a text SAMPLE of recent mentions.
  3. Scores that sample bullish / bearish / neutral with a finance-tuned
     lexicon (fast, free, deterministic — no external ML calls needed).
  4. Appends one row to data.json, which the dashboard (index.html) reads.

Environment variables required:
  X_BEARER_TOKEN   - Bearer token from your X developer app (pay-per-use project)

Configure tickers / cadence in CONFIG below.
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

TICKERS = ["UBER", "GRAB", "TSLA"]  # add/remove symbols here — each gets its own entry in data.json
SAMPLE_SIZE = 100                  # tweets pulled per run for sentiment scoring (max 100/request)
DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
X_API_BASE = "https://api.x.com/2"

# ---------------------------------------------------------------------------
# Finance sentiment lexicon
# Loosely modeled on Loughran-McDonald finance word lists + common retail
# trader slang. Keep this list editable — it's the easiest lever to tune
# without touching the rest of the pipeline.
# ---------------------------------------------------------------------------

BULLISH_WORDS = {
    "bullish", "buy", "buying", "long", "calls", "moon", "mooning", "breakout",
    "rally", "rallying", "upgrade", "upgraded", "beat", "beats", "outperform",
    "strong buy", "undervalued", "squeeze", "accumulate", "accumulating",
    "green", "pump", "pumping", "rip", "ripping", "up", "surge", "surging",
    "all time high", "ath", "new high", "buy the dip", "btd", "oversold bounce",
}

BEARISH_WORDS = {
    "bearish", "sell", "selling", "short", "shorting", "puts", "dump", "dumping",
    "crash", "crashing", "downgrade", "downgraded", "miss", "misses",
    "underperform", "overvalued", "red", "plunge", "plunging", "tank", "tanking",
    "sell off", "selloff", "down", "falling", "fell", "drop", "dropping",
    "new low", "resistance rejection", "bag holder", "bagholder", "rug",
}

NEGATORS = {"not", "no", "n't", "never", "isn't", "wasn't", "won't", "don't"}


def score_sentiment(texts):
    """Very simple lexicon scorer with basic negation handling.
    Returns (bullish_count, bearish_count, neutral_count, avg_score)
    where avg_score is in [-1, 1].
    """
    bullish, bearish, neutral = 0, 0, 0
    scores = []

    for raw in texts:
        text = raw.lower()
        words = re.findall(r"[a-z']+", text)
        hits = 0
        for i, w in enumerate(words):
            negated = i > 0 and words[i - 1] in NEGATORS
            if w in BULLISH_WORDS:
                hits += -1 if negated else 1
            elif w in BEARISH_WORDS:
                hits += 1 if negated else -1
        # also check multi-word phrases
        for phrase in BULLISH_WORDS:
            if " " in phrase and phrase in text:
                hits += 1
        for phrase in BEARISH_WORDS:
            if " " in phrase and phrase in text:
                hits -= 1

        if hits > 0:
            bullish += 1
        elif hits < 0:
            bearish += 1
        else:
            neutral += 1
        scores.append(max(-1, min(1, hits / 3)))  # clip per-tweet score

    avg_score = sum(scores) / len(scores) if scores else 0.0
    return bullish, bearish, neutral, round(avg_score, 3)


# ---------------------------------------------------------------------------
# X API calls
# ---------------------------------------------------------------------------

def x_api_get(path, params, bearer_token):
    url = f"{X_API_BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {bearer_token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def get_mention_count(ticker, bearer_token, hours_back):
    """Sum of tweets/counts/recent buckets over the lookback window."""
    query = f'"${ticker}" -is:retweet lang:en'
    start_time = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = x_api_get(
        "/tweets/counts/recent",
        {"query": query, "start_time": start_time, "granularity": "hour"},
        bearer_token,
    )
    buckets = data.get("data", [])
    return sum(b["tweet_count"] for b in buckets)


def get_sample_texts(ticker, bearer_token, n):
    query = f'"${ticker}" -is:retweet lang:en'
    data = x_api_get(
        "/tweets/search/recent",
        {"query": query, "max_results": min(max(n, 10), 100), "tweet.fields": "text"},
        bearer_token,
    )
    return [t["text"] for t in data.get("data", [])]


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    bearer_token = os.environ.get("X_BEARER_TOKEN")
    if not bearer_token:
        print("ERROR: X_BEARER_TOKEN environment variable not set.", file=sys.stderr)
        sys.exit(1)

    # how far back this run covers — matches your polling cadence (12h default)
    hours_back = int(os.environ.get("LOOKBACK_HOURS", "12"))

    data = load_data()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for ticker in TICKERS:
        try:
            count = get_mention_count(ticker, bearer_token, hours_back)
            sample = get_sample_texts(ticker, bearer_token, SAMPLE_SIZE)
            bullish, bearish, neutral, avg_score = score_sentiment(sample)
        except Exception as e:
            print(f"ERROR fetching {ticker}: {e}", file=sys.stderr)
            continue

        row = {
            "timestamp": now_iso,
            "mention_count": count,
            "sample_size": len(sample),
            "bullish": bullish,
            "bearish": bearish,
            "neutral": neutral,
            "sentiment_score": avg_score,  # -1 (very bearish) to +1 (very bullish)
        }

        data.setdefault(ticker, []).append(row)
        print(f"{ticker}: {row}")

    save_data(data)


if __name__ == "__main__":
    main()
