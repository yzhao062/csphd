# Board prioritization by edit-recency — Design

- **Date:** 2026-06-30
- **Status:** Approved (brainstorming) — pending implementation plan
- **Components:** `board.html` (client board) + `tools/build_openings.py` (daily sync) + `data/openings.{js,json}` (schema)
- **Author:** Yue Zhao (with Claude)

## Problem

The PhD opportunity board currently groups openings **by school**: schools that have any 短期
(deadline-driven) opening float to the top, the rest are sorted alphabetically A→Z, and within a
school it is 短期-first then source-sheet order (`groupEntries`, `board.html`). The net effect is an
alphabetical-by-school list, so a freshly-posted or freshly-updated listing is buried under stale
ones. A returning student cannot see "what's new / who is actively recruiting" at a glance.

## Goal

Order the board so that **recently added or updated listings appear first**. Ties fall back to the
familiar alphabetical-by-school order, so the board's resting state still looks like today's.

## Non-goals

- Deadline- or term-based sorting (term parsing stays, but only for filtering/display).
- Reconstructing edit history from git (kept as a future option — see Out of scope).
- A user-facing sort toggle.
- Sub-day / real-time update resolution.

## Decisions (from brainstorming)

1. **Signal:** edit-recency — a listing rises when it is newly added or its content changes.
2. **Layout:** one flat stream, newest → oldest. No school group headers. **School shown inline** on
   each row. All existing filters (关键词 / 学校 / 时效 / 类型 / 学期) stay.
3. **Order:** `lastChanged` descending → tie: school A→Z → tie: faculty A→Z.
4. **短期 no longer floats** structurally. Short-term openings surface via recency + the 短期 badge +
   the 时效 filter. (Confirmed acceptable.)
5. **Mechanism:** self-contained snapshot diff — dates stored *inside* `openings.json`, computed by
   diffing each daily build against the previous committed file. **No dependency on Google edit
   metadata.**
6. **Cold start accepted:** no history before tracking begins; day 1 everything is "new" and the
   board falls back to alphabetical-by-school, then differentiates as edits land.

## Why change-tracking is valid long-term

The build already fetches the sheet's CSV export daily, and a CSV export always reflects the sheet's
*current* state. We detect changes ourselves by diffing today's rows against the previous committed
`openings.json`; any edit a PI makes to a tracked field shows up in the next day's CSV and is caught.
This adds **no new external dependency** beyond the daily sync the board already relies on. The daily
commit of the dated file persists the history (and incidentally turns git history into an auditable
change log, which keeps the git-backfill option open later).

## Data model

Each opening object in `data/openings.json` and `data/openings.js` gains two fields:

```json
"firstSeen":   "YYYY-MM-DD",
"lastChanged": "YYYY-MM-DD"
```

`firstSeen` = date the row first appeared; `lastChanged` = date its tracked content last changed.
No other schema changes. Top-level `synced` is unchanged.

## Build logic — `tools/build_openings.py`

After assembling today's rows (fetch/parse unchanged), stamp the two dates:

1. Load the previous `data/openings.json` if present; build a lookup of prior rows.
2. **Identity key** per row: `normalize(faculty)` + sep + `normalize(school)` + sep + `category`
   (school normalization already applied via `SCHOOL_ALIASES`). If two rows share a key,
   disambiguate by occurrence order.
3. **Tracked fields** (the change set): `interests, positions, requirements, materials, term,
   deadline, contact, homepage`. Compare whitespace-collapsed values. `university / faculty /
   category / types` are identity/derived and excluded from the change check.
4. With `today` = UTC date (same source as `synced`):
   - key found, all tracked fields equal → carry `firstSeen` and `lastChanged` forward
   - key found, any tracked field differs → keep `firstSeen`, set `lastChanged = today`
   - key not found → `firstSeen = lastChanged = today`
5. Missing/blank prior dates (first run after this ships) → treat as `today` (cold start).
6. Remains pure standard library.

## Client logic — `board.html`

1. **Merge:** in `mergeEntities`, set card `lastChanged = max(row.lastChanged)` and
   `firstSeen = min(row.firstSeen)` across merged rows.
2. **Sort (replaces `groupEntries` / `makeGroup`):** flat list sorted by `lastChanged` desc, then
   school `localeCompare` A→Z, then faculty A→Z. Rows with a missing `lastChanged` sort as oldest.
3. **Render:** drop the school group sections; render each card as a row that now shows **school
   inline** (today the school lives only in the group header). Keep faculty, interests,
   type/category badges, when (deadline/term), contact, and the details toggle.
4. **Recency badge** — gated by a freshness window `RECENCY_WINDOW_DAYS` (default 14) measured from
   `synced`, plus a cold-start gate `trackingStart = min(firstSeen)` over the dataset:
   - 「新」 when `firstSeen > trackingStart` **and** `synced − firstSeen ≤ window`.
   - 「更新」 when not 新, `lastChanged > trackingStart`, **and** `synced − lastChanged ≤ window`.
   - Day 1 every row has `firstSeen == trackingStart`, so no badges show; as edits land the badges
     appear and then expire after the window. Optional muted `更新 M-D` text alongside.

   (The window alone would light up everything on day 1; `trackingStart` alone would keep flagging a
   months-old change forever. Both gates together are required.)
5. **Filters:** unchanged behavior; they filter the flat list. The school `<select>` stays.
6. **Backward compatible:** if the loaded data has no `firstSeen / lastChanged` (board ships before
   the next sync runs the new build), all cards share the missing-date baseline → order falls back to
   school A→Z and no badges show. No breakage.
7. The sticky `.school-head` styles become unused — remove or repurpose. The sticky filter bar stays.

## Edge cases & limitations

- **1-day resolution** — multiple same-day edits collapse to one date.
- **Identity churn** — a PI rename or an unseen school spelling reads as a one-time false "new".
- **Content-based** — re-entering an identical value is correctly *not* counted as a change.
- **Skipped syncs** — if the sync is down for days, a change is dated to the next successful sync,
  not the true edit day.
- **No pre-launch history** (cold start).

## Verification

- **Client:** a small fixture `openings.js` with hand-set `firstSeen / lastChanged` across a few
  schools/dates; open `board.html` locally and confirm ordering (recent first, ties A→Z), inline
  school, badges, and the dateless-fallback case.
- **Build:** run `build_openings.py` against a stubbed "previous" `openings.json` with the network
  fetch replaced by fixture CSV — once unchanged (dates carry forward) and once with an edited field
  plus a new row (`lastChanged` / `firstSeen` update) — and assert the stamped dates. Keep it a tiny
  standalone check; the repo has no test framework.

## Out of scope / future

- Git-history backfill to seed pre-launch recency (Approach 2/3 from brainstorming).
- A sort toggle, or a "recently updated" digest on the homepage.