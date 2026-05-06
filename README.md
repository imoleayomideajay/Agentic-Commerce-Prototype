# Agentic Commerce Studio

A working Streamlit prototype of an autonomous retail e-commerce system.

It demonstrates — end-to-end — how AI agents can synthesise product data,
generate creative assets, and deploy them based on live customer signals.
Built to be shown to retail executives as a credible architecture, not a toy.

## What it does

The app simulates the full **product → purchase** loop with three coordinated agents:

| Agent | Responsibility |
|---|---|
| 🧭 **Merchandiser** | Scans live inventory + signals, picks the SKUs to promote *right now*, and explains why. |
| ✍️ **Creative** | Generates ad copy (headline, body, CTA) per SKU per channel, tailored to the triggering signal. Powered by Claude (`claude-sonnet-4-20250514`). |
| 🚀 **Deployment** | Simulates pushing assets to Meta / Google / Email / On-site, with timestamps and a per-channel status board. |

An **Orchestrator** runs them in sequence on each cycle, with three autonomy modes:
*Manual → Approve each step → Fully autonomous*.

## Architecture

```
┌─ Data Synthesis Layer ──────────────────────────────────────┐
│  Product catalogue  +  Image library  +  Live signals        │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
           ┌────────────────────────────────────┐
           │   Merchandiser Agent (Claude)      │   what to promote, why
           └──────────────────┬─────────────────┘
                              ▼
           ┌────────────────────────────────────┐
           │   Creative Agent (Claude)          │   per-channel copy variants
           └──────────────────┬─────────────────┘
                              ▼
           ┌────────────────────────────────────┐
           │   Deployment Agent                 │   ship + simulate metrics
           └──────────────────┬─────────────────┘
                              ▼
                ┌──────────────────────────┐
                │   Metrics + Event Log     │
                └──────────────────────────┘
```

## Running it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL Streamlit prints (usually `http://localhost:8501`).

### With or without an API key

- **With an Anthropic API key** (paste it in the sidebar): agents reason via Claude.
- **Without one**: agents fall back to deterministic rule-based logic. The demo still
  works end-to-end — useful for offline demos or screenshots.

## UI tour

- **Sidebar** — API key, autonomy slider, channels, Run Cycle button, signal/catalogue refresh.
- **Tab 1: Live State** — catalogue, current signals, synthesised priority view.
- **Tab 2: Agent Activity** — three columns showing each agent's logs and reasoning, plus the full event log.
- **Tab 3: Deployed Creative** — gallery of generated ads with channel, SKU, signal trigger, and timestamp. Drafts can be approved individually or in bulk.
- **Tab 4: Metrics** — simulated CTR, conversion lift, and per-channel performance.

## Inspectable architecture

The **Advanced** expander at the top of the page exposes the live prompts driving
the Merchandiser and Creative agents. Edit them in the UI to see behaviour change
without touching code — useful for stakeholder workshops.

## Bring your own data

The sidebar has a **📤 Bring your own data (CSV)** expander that accepts real catalogue and signal exports.

**Catalogue CSV** — required columns: `sku_id`, `name`, `category`. Optional columns are auto-filled with sensible defaults: `price`, `stock_level`, `image_url`, `description`, `tags`, `margin_pct`. Download the template from the sidebar to see the exact shape.

**Signals CSV** *(optional)* — required columns: `type`, `description`, `affected_category`. `intensity` is optional (defaults to 0.7).

The validator gives clear feedback: which columns were defaulted, how many SKUs have zero stock, whether any signals reference categories that don't exist in the catalogue. Garbage input is rejected with a useful error rather than silently producing nonsense.

A small data-source badge in the sidebar shows whether you're running against synthetic or uploaded data.

## Notes on honesty

- The Creative Agent generates **copy**, not images. Hero images are selected from
  the catalogue's image library. Real image generation would need a separate API
  and would slow the demo significantly — calling that out rather than faking it.
- Performance metrics (CTR, conversion lift) are **simulated**. They're plausible
  ranges based on channel norms but they are not predictions.
- The catalogue, signals, and customer data are all generated in-app. No external
  data is required to run the demo.

## File layout

```
app.py            # Single-file Streamlit application
requirements.txt  # streamlit, anthropic, pandas, pillow
README.md         # This file
```
