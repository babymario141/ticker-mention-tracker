# Ticker Mention Tracker

Tracks how often a ticker is mentioned on X, and a rough bullish/bearish
read on that chatter, overlaid against the actual stock price. Search or
pick a ticker in the dashboard to switch what's shown, and toggle the time
range (1D/1W/1M/6M/1Y/YTD) on the charts. Runs entirely on GitHub —
**manual trigger only, no automatic schedule** — so it never spends money
without you explicitly asking it to.

## How it works

1. **`collector.py`** loops over every entry in the `QUERIES` list at the
   top of the file. For each one it calls the X API (pay-per-use tier):
   - `tweets/counts/recent` → mention *volume* for the window since the last run.
   - `tweets/search/recent` → a ~50-tweet text sample from the same window.
   - Scores that sample with a small finance lexicon (bullish/bearish word
     lists + basic negation handling) to get a sentiment score from -1 to +1.
   - Appends one row per entry per run to `data.json`, keyed by label.
2. **`.github/workflows/collect.yml`** only runs when you manually trigger
   it from the Actions tab (`workflow_dispatch`) — no cron schedule, so
   nothing calls the X API unless you tell it to.
3. **`index.html`** reads `data.json` client-side. Search or pick a ticker,
   pick a time range, and it renders mention volume + sentiment, each
   overlaid with the actual stock price fetched live from Yahoo Finance
   (only for symbols that look like real tickers — plain names like
   "Unitree" skip the price fetch and just show mentions/sentiment).

## Setup

Same as before: get an X API bearer token, push to a GitHub repo with the
`.github/workflows/` structure intact, add `X_BEARER_TOKEN` as a repo
secret, enable GitHub Pages. See the earlier setup steps if this is your
first time — nothing about setup itself changed, only the automation
behavior and the dashboard.

## Running the collector

Go to the repo's **Actions** tab → **Collect ticker mentions** → **Run
workflow**. That's it — it only runs when you click this. Each run costs
roughly $0.25–0.50 for one ticker at 50 sampled tweets (down from the
100-tweet default), so a handful of manual runs a week is genuinely cheap.

## Adding tickers or keyword searches

Open `collector.py` and edit the `QUERIES` list:

```python
QUERIES = [
    {"label": "UBER", "query": '"$UBER"'},
    # {"label": "GRAB", "query": '"$GRAB"'},
    # {"label": "Unitree", "query": '"Unitree" (robot OR robotics OR IPO OR humanoid OR stock)'},
]
```

Uncomment or add entries, commit, then run the workflow manually. Each
label shows up in the dashboard's search box automatically.

## Price overlay

The dashboard fetches `query1.finance.yahoo.com`'s chart endpoint directly
from your browser, routed through a public CORS proxy
(`api.allorigins.win`) since Yahoo doesn't allow direct browser requests.
This is unofficial and free — no API key needed — but also unauthenticated
and could break or rate-limit without notice. It only fires for labels that
look like real ticker symbols (short, all-caps).

## Cost (rough, per manual run)

At 50 sampled tweets per ticker: ~50 reads × $0.005 ≈ $0.25, plus a
lightweight counts call. A few runs a week for one ticker should land well
under $10/month — check developer.x.com's usage page against this after a
week of real use.

## Extending

- **Better sentiment:** swap `score_sentiment()` in `collector.py` for an
  LLM classification pass on the same tweet sample if the lexicon feels
  too blunt — still cheap at this sample size, just adds a dependency.
- **Backtesting:** `data.json` is a plain JSON time series — pull it into
  pandas alongside price history to check whether sentiment or volume
  actually leads price moves before trusting either as a signal.

## Notes

- `tweets/counts/all` (full historical backfill) requires X's Enterprise
  tier (~$42k/month) — this tool only accumulates history forward from
  when you run it.
- The lexicon in `collector.py` (`BULLISH_WORDS` / `BEARISH_WORDS`) is a
  plain editable set, not a model — tune it directly based on what you see
  misclassified.
