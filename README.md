# Ticker Mention Tracker

Tracks how often any ticker you choose is mentioned on X, and a rough
bullish/bearish read on that chatter, polled every 12 hours. Search or pick
a ticker in the dashboard to switch what's shown — it's not locked to one
symbol. Built to need near-zero maintenance: GitHub Actions runs the
collector on a schedule, commits the result, and GitHub Pages serves the
dashboard — no server to keep alive.

## How it works

1. **`collector.py`** loops over every symbol in the `TICKERS` list at the
   top of the file. For each one it calls the X API (pay-per-use tier):
   - `tweets/counts/recent` → mention *volume* for the window since the last run.
   - `tweets/search/recent` → a ~100-tweet text sample from the same window.
   - Scores that sample with a small finance lexicon (bullish/bearish word
     lists + basic negation handling) to get a sentiment score from -1 to +1.
   - Appends one row per ticker per run to `data.json`, keyed by symbol.
2. **`.github/workflows/collect.yml`** runs `collector.py` at 00:00 and 12:00
   UTC and commits the updated `data.json` back to the repo.
3. **`index.html`** reads `data.json` client-side. Type a ticker into the
   search box (or click one in the dropdown) to switch the charts to that
   symbol — no backend needed to view it, works as a static page.

## Setup

1. **Get an X API bearer token.** Create a project at
   [developer.x.com](https://developer.x.com), enroll in pay-per-use, and
   generate a bearer token (App-only auth is sufficient — you're only reading
   public data).
2. **Push this folder to a GitHub repo**, keeping the `.github/workflows/`
   folder structure intact.
3. **Add the token as a repo secret:** Settings → Secrets and variables →
   Actions → New repository secret → name it `X_BEARER_TOKEN`.
4. **Enable GitHub Pages:** Settings → Pages → Deploy from branch → `main` /
   root. Your dashboard will be live at `https://<you>.github.io/<repo>/`.
5. **Trigger a manual run** from the Actions tab (`workflow_dispatch`) to
   populate real data instead of the seeded sample in `data.json`.

## Adding or removing tickers

Open `collector.py` and edit the `TICKERS` list near the top:

```python
TICKERS = ["UBER", "GRAB", "TSLA"]   # add or remove symbols here
```

Each symbol gets its own array in `data.json` automatically, and shows up
in the dashboard's search box the next time the collector runs — no changes
needed in `index.html`.

## Cost (rough)

At 2 runs/day, each ticker costs ~100 sampled tweet reads/run × 2 = 200
reads/day ≈ $1/day at $0.005/read, plus a lightweight counts call. Call it
**$25–35/month per ticker**. Three tickers (the seeded default) lands around
$75–100/month — worth checking against your actual usage after the first
week rather than trusting the estimate blindly.

## Extending

- **Better sentiment:** the lexicon scorer is deliberately simple (free,
  fast, no dependencies). If you want more nuance — sarcasm, context,
  "$UBER calls printing" vs. "$UBER calls me broke" — swap `score_sentiment()`
  for a call to an LLM (e.g. Claude) classifying the same tweet sample. At
  ~100 tweets/run this is well under a cent per run, but adds an external
  API dependency and a bit of latency.
- **Backtesting:** once you've got a few weeks of `data.json`, it's a plain
  JSON time series — easy to pull into pandas alongside price data to check
  whether the sentiment score actually leads price moves before you trust it
  for anything.

## Notes

- `tweets/counts/all` (full historical backfill) requires X's Enterprise
  tier (~$42k/month) — this tool only accumulates history forward from when
  you start running it.
- The lexicon in `collector.py` (`BULLISH_WORDS` / `BEARISH_WORDS`) is the
  easiest thing to tune — it's a plain set, not a model, so you can edit it
  directly based on what you see misclassified.
