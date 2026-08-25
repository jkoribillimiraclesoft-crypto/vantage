# VANTAGE — GCP Data Engineering AI Intelligence (Live)

A real, running version of the personalized AI intelligence dashboard: it pulls
actual data from live sources, scores it with a real Claude API call against
your GCP Data Engineer profile, stores it, and serves it through Streamlit —
deployable to a public URL.

## What's actually real here

- **Live sources**, each isolated so one failure never breaks the others:
  - arXiv (official Atom API)
  - Hacker News (official Firebase API, filtered by keyword)
  - GitHub (official search API, by topic: `llm-agents`, `data-engineering`, `mcp`, `rag`)
  - Google Cloud Blog, Google Cloud Release Notes, dbt Labs Blog, LangChain Blog,
    Snowflake Blog, Meta AI Blog (RSS — best-known public feed URLs; see note below)
- **Real AI analysis** — every new item is sent to Claude (`claude-sonnet-4-6`)
  with your profile, and the model returns the scored, personalized analysis.
  The model is only ever asked for *analysis* (summary, why it matters, scores,
  category) — title/source/URL/date are never generated, only passed through
  from what was actually fetched.
- **Deduplication** against everything already stored, plus near-duplicate
  title matching, so re-running the refresh doesn't reprocess the same story
  or burn API calls on it twice.
- **SQLite storage** (`data/vantage.db`) so results persist between visits.
- **Configurable weighted scoring** (GCP / Data Engineering / AI / Career /
  Adoption / Future) — adjustable live on the Profile page, re-ranking
  everything instantly since raw component scores are already stored.

### About the RSS feed URLs

Google Cloud Blog, dbt, LangChain, Snowflake, and Meta AI's RSS URLs in
`lib/config.py` are the best-known public feed addresses for each vendor as of
this build. Vendors do change these occasionally. If a source shows 0 items on
the **Source Status** page, check that source's current RSS URL and update it
in `lib/config.py` — everything else keeps working. arXiv, Hacker News, and
GitHub use stable official APIs and shouldn't need this.

## Run it locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your-key-here
streamlit run app.py
```

Open the local URL (usually http://localhost:8501). If the database is empty,
it auto-runs one refresh on first load. Otherwise, click **🔄 Refresh live
data** in the sidebar any time.

**Never paste your real API key into a chat message, ticket, or committed
file.** Set it as an environment variable or a platform secret only.

## Deploy it to a public URL (Streamlit Community Cloud — free)

1. **Push this project to GitHub.**
   ```bash
   cd vantage_live
   git init
   git add .
   git commit -m "VANTAGE live"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```
   (`.gitignore` already excludes the local database and any secrets file —
   nothing sensitive gets pushed.)

2. **Go to** [share.streamlit.io](https://share.streamlit.io) **and sign in with GitHub.**

3. Click **New app**, pick your repo/branch, and set the main file path to `app.py`.

4. Before or after deploying, open the app's **Settings → Secrets** and add:
   ```toml
   ANTHROPIC_API_KEY = "your-key-here"
   ```
   This is Streamlit's encrypted secrets store — nobody but you (and the app
   at runtime) can see it.

5. Click **Deploy**. You'll get a public URL like
   `https://your-app-name.streamlit.app` you can open from any device.

6. On first load with the key set, it auto-runs a refresh. After that, use
   the **🔄 Refresh live data** button whenever you want new data — each
   refresh costs a small number of Claude API calls (roughly one per 8 new
   items found), so it's manual by design rather than constantly polling.

## What's still not built (from the original full spec)

- Scheduled/automatic refresh independent of someone opening the app (would
  need a cron trigger — e.g. GitHub Actions running the pipeline on a
  schedule and committing the updated DB, or a small separate worker).
- The LangGraph 5-agent architecture specifically — this build reaches the
  same *outcome* (research → relevance → summary → career impact → learning
  recommendation) through one well-structured Claude call per batch, which is
  faster and cheaper than 5 sequential agent calls per item. Worth revisiting
  as a LangGraph pipeline if you want agent-level tracing/observability later.
- ChromaDB/Qdrant vector storage and Ollama/local models — not needed yet
  since dedup here uses title similarity rather than embeddings, and Claude
  via API is doing the analysis. Both are drop-in additions later if needed.
