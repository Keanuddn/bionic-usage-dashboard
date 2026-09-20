# Bionic Usage Dashboard

A local usage dashboard for **LM Studio Bionic** — token consumption, what it
was spent on, and your **real weekly plan limit**, rendered as an Übersicht
desktop widget (Nothing-style, light mode) with a full-page dashboard one
click / ⌥⌘D away.

No server, no cloud calls from the dashboard itself. Everything is read from
files that Bionic already maintains on your machine.

## What you get

- **Desktop widget** (Übersicht): hero token count for the week, IN/OUT/CALLS,
  official weekly-limit bar with % remaining, top-3 sessions, live limit badge
- **Click the widget** (or a global hotkey) → full-page dashboard:
  - Week / Month / All-time toggle with delta vs. previous period
  - Official **weekly limit** with reset countdown (read from Bionic's own cache)
  - 30-day input/output chart
  - Top sessions, model distribution, top tools
  - Gamified achievements (STREAK, DEEP DIVE, NIGHT SHIFT, TOOL SMITH, …)

## How it works

Bionic stores per-message token counts, session names and the selected model
in per-project SQLite databases, and its cloud-billing response (including
your real weekly limit) in a local JSON cache:

| Source | Used for |
|---|---|
| `~/.lmstudio/apps/bionic/projects/*/.internal/ng-sessions.sqlite` | messages, token counts (`context.before/self`), session names, tool calls, model per session (`modelSpecifier`) |
| `~/.lmstudio/apps/bionic/.internal/cloud-account.json` | official weekly limit: `remainingBasisPoints`, `resetsAtIso` — the same numbers as lmstudio.ai → Plan & Billing |

`extract.py` (stdlib only) reads both and writes `data.json` + `data.js`.
The Übersicht widget runs it every 60 seconds and renders the result.

## Setup

**1. Clone and place**

```bash
git clone https://github.com/Keanuddn/bionic-usage-dashboard.git
cd bionic-usage-dashboard
```

**2. Try the full dashboard right now** (no setup needed)

```bash
cp sample/data.js data.js   # demo data
open dashboard.html
```

**3. Install [Übersicht](https://tracesof.net/uebersicht)**

```bash
brew install --cask ubersicht
```

**4. Install the widget**

```bash
mkdir -p ~/Library/Application\ Support/Übersicht/widgets
cp -r widget ~/Library/Application\ Support/Übersicht/widgets/bionic-usage.widget
```

Then edit `widget/index.jsx` and set `BASE` to the folder containing
`extract.py` and `dashboard.html`.

**5. Make the widget clickable** (once)

- Übersicht menu bar icon → **Preferences…** → check **Enable interaction**
- System Settings → Privacy & Security → Accessibility → enable **Übersicht**

**6. Optional: global hotkey** with [Hammerspoon](https://www.hammerspoon.org/)

```lua
-- ~/.hammerspoon/init.lua
hs.hotkey.bind({ "alt", "cmd" }, "d", function()
  hs.execute('open "/path/to/bionic-usage-dashboard/dashboard.html"')
end)
```

## Configuration

`config.json`:

```json
{
  "weekly_token_budget": 1000000,
  "monthly_token_budget": 4000000,
  "deep_dive_context_tokens": 100000
}
```

The **weekly limit section uses official data** when Bionic's
`cloud-account.json` cache is present — budgets are only a fallback (and used
for the Month/All-time views).

### Limit accuracy

Bionic's weekly limit is measured server-side in **microcredits** (Bionic+ =
10,000 per week). The dashboard converts credits → tokens using your own
calibration: set `weekly_token_budget` so that the token count and the
official percentage match. In testing, local token counts tracked the official
percentage with ~0.3 percentage points deviation. The cache refreshes when the
Bionic app syncs billing context, so values can lag a few minutes — the
dashboard shows the data's timestamp.

## Privacy

`data.json` / `data.js` contain your session names and usage numbers. They are
gitignored — nothing personal gets committed. Everything stays on your machine.

## Notes

- Input tokens = `context.before` of assistant messages (what was actually
  sent per request); output = `context.self`. Cached-input discounts are not
  modeled (conservative).
- Tested on macOS with Bionic + Übersicht 1.6.

## License

[MIT](LICENSE)
