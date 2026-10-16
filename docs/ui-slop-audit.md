# UI SLOP Audit + AI Insights (Ollama) — Alpha web

Scope: `packages/web/src`. Evidence gathered via grep/read on 2026-09-20.
Design system baseline: `styles/theme/base.css` (`--r:4px`, `--rl:12px`, `--sh`,
`--card-sh`), shared primitives in `components.jsx`.

Severity: 🔴 high (breaks or reads as generic) · 🟡 medium · 🟢 minor/mostly-ok.

---

## 1. Card grid as default layout — 🔴 high
Card-grid used **30×** across **14 files** (`className="sg"|"sg-4"`, `repeat(auto-fit…)`).
- `pages/dashboard.jsx` — `sg-4` with **7** StatCards.
- `pages/income_tracker.jsx`, `investment_tracker.jsx` — 4 grids each.
- `pages/BusinessAnalytics.jsx` — 3 grids.
Every analytics surface opens with a metric grid regardless of the page's job.
**Fix:** reserve the grid for genuinely parallel, equal-weight metrics. On the
dashboard, lead with one focal number (net cash flow or health) and demote the
rest to a compact strip; don't grid seven unrelated metrics.

## 2. Weak hierarchy inside cards — 🔴 high
`components.jsx` `StatCard` renders label + value + sub with `.sc-val` always
`font-weight:800` (`components.css`). All 7 dashboard cards have identical visual
weight — no focal point. `dashboard.jsx` `MacroMarketOverview` renders 4 metrics
all at `fontSize:16, fontWeight:900`.
**Fix:** introduce a weight/size scale (one hero metric larger; secondary metrics
smaller/lighter). Vary `StatCard` by role rather than one uniform style.

## 3. Card as filler — 🔴 high
`dashboard.jsx` forces empty metrics into cards:
- Goals → `"0"` when none.
- Health Score → `"—"` when no data.
- Safe To Spend → `"—"` when no data.
Three of seven cards can render placeholders, padding the grid with non-info.
**Fix:** hide or merge empty metrics; a card must earn its place with real data
or a clear next action.

## 4 & 5. Missing / single-state cards — 🟡 medium (corrected)
Deeper inspection revised this down. Good primitives EXIST
(`WidgetSkeleton`, `DashboardSkeleton`, `ApiError`, `Empty` with variants,
`LoadingSpinner`) and the core trackers use them. The pages first flagged as
happy-path-only actually DO handle states, just with **local** patterns rather
than the shared primitives:
- `advanced.jsx` — loading (L409/481), empty (L393), no-data (L612).
- `BusinessAnalytics.jsx` — loading spinner (L593), empty states (L338/531).
- `BehavioralDashboard.jsx` / `LustDashboard.jsx` — local `Skeleton`/`GpSkeleton`
  + empty states.
- `stock_ml.jsx` — `StockMLSkeleton` + loading + error.
The one genuine failure was `advanced.jsx` crashing on `summary.avg_daily_net`
when data was absent — fixed separately (default-guarded destructure + backend
summary block).
**Remaining gap (consistency, not missing states):** these pages reinvent local
skeleton/empty instead of the shared primitives. Migrate them to
`WidgetSkeleton`/`ApiError`/`Empty` over time for a uniform state vocabulary.
Status after this pass: no known unguarded-crash paths; states are covered.

## 6. Border-radius everywhere — 🟡 medium
Tokens exist (`--r:4px`, `--rl:12px`) but are widely bypassed: **297** hardcoded
`borderRadius:`/`pill` occurrences across 28 files. Examples:
- `dashboard.jsx` `HeroVisual` → `borderRadius:24` (magic number).
- `components.jsx` `ModuleLoader` → `12`, `8`, `4` inline.
- `components.css` `.btn` → hardcoded `8px` (not `var(--r)`).
Radius is applied uniformly, so shape carries no meaning (urgent vs neutral).
**Fix:** use only `--r`/`--rl` (add `--rs` if needed); differentiate by element
role — sharper corners for data/critical surfaces, rounded for soft/interactive.

## 7. Drop shadow as default depth — 🟡 medium
The real issue is CSS, not inline (inline `boxShadow` only 20×). `components.css`
`.card{box-shadow:var(--card-sh)}` applies to **every** card. Light theme
(`light/tokens.css`) sets `--card-sh` to a real shadow on all cards; dark theme
(`base.css`) correctly sets `--card-sh:none` and uses border contrast.
`.btn-p` always carries `box-shadow:var(--ind-d)`.
**Fix:** reserve elevation for true layering (modal > card > bg). Flatten
same-level cards in light mode too (border/contrast), matching the dark theme.

## 8. Spacing from muscle memory — 🟡 medium
Spacing is the 8px family (`gap:14/16`, `padding:14px 16px`, inline `16/20/32`)
with no spacing token scale in `base.css` (only radius/type tokens exist).
`dashboard.jsx`, `components.jsx` use 16/20/32 directly. Consistent but doesn't
express hierarchy (important elements get no extra breathing room).
**Fix:** add spacing tokens (`--sp-1..6`) and allocate space by importance, not
by habit.

## 9. Overuse of badges/pills — 🟡 medium
`Pill` variants (`g/r/y/c`) are all the **same** size + glow (`components.css`
`.pill{…} .pill.g{box-shadow:var(--glow-gr)}`). Heavy pill/badge density:
`stock_analyzer.jsx`, `BusinessAnalytics.jsx`, `advanced.jsx`, `receipt_reader.jsx`,
`RiskExposure.jsx` all in the 18–39 range (combined with radius count). Every
status/type gets identical loud treatment, so nothing stands out.
**Fix:** one emphasized pill style for genuinely important status; render routine
labels as plain text or a muted variant. Drop the glow on non-critical pills.

---

## AI Insights → local Ollama (`satgeze/ornith-9b-1m:q2_k`)

App-side integration DONE (verified `GET /api/ai/status` → `model:
satgeze/ornith-9b-1m:q2_k`):
- `docker-compose.override.yml` (insights): `PROVIDER_OVERRIDE=ollama`,
  `OLLAMA_HOST=http://host.docker.internal:11434`,
  `OLLAMA_MODEL_OVERRIDE=satgeze/ornith-9b-1m:q2_k`, plus
  `extra_hosts: host.docker.internal:host-gateway` (container reaches host Ollama —
  verified 200).
- `provider_strategy.py`: added `/api/generate` fallback when a model rejects
  `/api/chat`.

BLOCKER (host-side, not app): the model ships with `RENDERER qwen3.5` /
`PARSER qwen3.5` and requires a newer Ollama runtime. Host Ollama is **0.33.2**,
which rejects both `/api/chat` and `/api/generate` with
`"…does not support chat/generate"`. `ollama show` metadata is fine
(qwen35, 9B, capabilities: completion/vision/tools/thinking).
**Action to enable real AI output:** upgrade host Ollama to a version that
implements the qwen3.5 renderer (`winget upgrade Ollama.Ollama` or reinstall
from ollama.com), then restart Ollama with `OLLAMA_HOST=0.0.0.0:11434`. No app
change needed after that. Until then, insights fall back to the rule engine
(`ai_powered:true, provider:rules`).
