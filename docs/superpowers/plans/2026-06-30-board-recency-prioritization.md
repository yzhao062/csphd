# Board Edit-Recency Prioritization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorder the PhD opportunity board so recently added/changed listings appear first (ties → school A→Z), driven by per-row `firstSeen`/`lastChanged` dates derived from daily snapshot diffs.

**Architecture:** The daily sync (`tools/build_openings.py`) stamps each opening with `firstSeen`/`lastChanged` by diffing the freshly fetched rows against the previous committed `data/openings.json`. The client (`board.html`) drops school grouping for a flat list sorted by `lastChanged` desc, shows the school inline, and renders a 「新」/「更新」 recency badge. The subtle date/badge math lives in a small, unit-tested `js/recency.js` (a local same-origin script, like `data/openings.js`).

**Tech Stack:** Vanilla ES5 JS in static HTML, Python 3.12 standard library only, `node:test` for the JS helper (dev-only, zero npm deps), `unittest` for the build (stdlib).

## Global Constraints

- **Zero external runtime dependencies; mainland-China direct-connect.** No CDN, Google Fonts, analytics, or third-party requests at view time. Only local same-origin resources (`./js/recency.js` is allowed; it is local, exactly like `./data/openings.js`).
- **Build script: Python standard library only** — no pip installs.
- **Chinese punctuation is full-width** (，。：、「」) in user-facing copy.
- **Static site, no user-facing build step** — pages are opened directly.
- **Backward compatible:** `board.html` must work with data that has no `firstSeen`/`lastChanged` (the window between shipping and the next cron). Dateless data → order falls back to school A→Z, no badges, no errors.

---

### Task 1: Stamp `firstSeen`/`lastChanged` in the build

**Files:**
- Modify: `tools/build_openings.py` (add constants + 4 functions; refactor `build_payload`, `write_outputs`, `main`)
- Test: `tools/test_build_openings.py` (create)

**Interfaces:**
- Produces:
  - `identity_key(record) -> str` — `normalize(faculty) + "\x00" + normalize(school) + "\x00" + category`, whitespace-collapsed + lowercased.
  - `tracked_signature(record) -> tuple` — whitespace-collapsed values of `interests, positions, requirements, materials, term, deadline, contact, homepage`.
  - `load_previous(data_dir) -> dict[str, list[dict]]` — prior rows grouped by `identity_key`; `{}` if file missing/invalid.
  - `stamp_recency(openings, previous, today) -> None` — mutates each row in place, adding `firstSeen`/`lastChanged` (ISO `YYYY-MM-DD`).
  - `data_dir_path() -> str`; `build_payload(today)`; `write_outputs(payload, data_dir)`.

- [ ] **Step 1: Write the failing test**

Create `tools/test_build_openings.py`:

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_openings as bo  # noqa: E402

TODAY = "2026-07-05"


def row(faculty="Jane Doe", university="MIT", category="长期", interests="GNN", **extra):
    base = {"faculty": faculty, "university": university, "category": category,
            "interests": interests, "positions": "", "requirements": "",
            "materials": "", "term": "", "deadline": "", "contact": "", "homepage": ""}
    base.update(extra)
    return base


class StampRecency(unittest.TestCase):
    def test_new_row_gets_today(self):
        r = row()
        bo.stamp_recency([r], {}, TODAY)
        self.assertEqual(r["firstSeen"], TODAY)
        self.assertEqual(r["lastChanged"], TODAY)

    def test_unchanged_carries_dates_forward(self):
        prev = row(firstSeen="2026-06-01", lastChanged="2026-06-10")
        previous = {bo.identity_key(prev): [prev]}
        r = row()
        bo.stamp_recency([r], previous, TODAY)
        self.assertEqual(r["firstSeen"], "2026-06-01")
        self.assertEqual(r["lastChanged"], "2026-06-10")

    def test_changed_field_bumps_lastchanged(self):
        prev = row(interests="GNN", firstSeen="2026-06-01", lastChanged="2026-06-10")
        previous = {bo.identity_key(prev): [prev]}
        r = row(interests="GNN, LLM")
        bo.stamp_recency([r], previous, TODAY)
        self.assertEqual(r["firstSeen"], "2026-06-01")
        self.assertEqual(r["lastChanged"], TODAY)

    def test_identity_ignores_case_and_whitespace(self):
        self.assertEqual(bo.identity_key(row(faculty="  Jane   Doe ")),
                         bo.identity_key(row(faculty="jane doe")))

    def test_signature_ignores_internal_whitespace(self):
        self.assertEqual(bo.tracked_signature(row(interests="GNN  ML")),
                         bo.tracked_signature(row(interests="GNN ML")))

    def test_duplicate_keys_match_positionally(self):
        p1 = row(firstSeen="2026-06-01", lastChanged="2026-06-01")
        p2 = row(firstSeen="2026-06-02", lastChanged="2026-06-02")
        previous = {bo.identity_key(p1): [p1, p2]}
        a, b = row(), row()
        bo.stamp_recency([a, b], previous, TODAY)
        self.assertEqual(a["firstSeen"], "2026-06-01")
        self.assertEqual(b["firstSeen"], "2026-06-02")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python tools/test_build_openings.py`
Expected: FAIL — `AttributeError: module 'build_openings' has no attribute 'stamp_recency'`.

- [ ] **Step 3: Add constants and the four functions**

In `tools/build_openings.py`, after the `FIELDS = (...)` tuple (around line 64), add:

```python
TRACKED_FIELDS = ("interests", "positions", "requirements", "materials",
                  "term", "deadline", "contact", "homepage")


def identity_key(record):
    faculty = re.sub(r"\s+", " ", record.get("faculty", "")).strip().lower()
    school = re.sub(r"\s+", " ", record.get("university", "")).strip().lower()
    return faculty + "\x00" + school + "\x00" + record.get("category", "")


def tracked_signature(record):
    return tuple(re.sub(r"\s+", " ", (record.get(field) or "")).strip()
                 for field in TRACKED_FIELDS)


def load_previous(data_dir):
    path = os.path.join(data_dir, "openings.json")
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return {}
    previous = {}
    for record in payload.get("openings", []):
        previous.setdefault(identity_key(record), []).append(record)
    return previous


def stamp_recency(openings, previous, today):
    used = {}
    for record in openings:
        key = identity_key(record)
        bucket = previous.get(key, [])
        cursor = used.get(key, 0)
        used[key] = cursor + 1
        prior = bucket[cursor] if cursor < len(bucket) else None
        if prior is None:
            record["firstSeen"] = today
            record["lastChanged"] = today
            continue
        record["firstSeen"] = prior.get("firstSeen") or today
        last_changed = prior.get("lastChanged") or today
        if tracked_signature(record) != tracked_signature(prior):
            last_changed = today
        record["lastChanged"] = last_changed
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python tools/test_build_openings.py`
Expected: PASS — `Ran 6 tests ... OK`.

- [ ] **Step 5: Wire stamping into the pipeline**

Replace `build_payload`, `write_outputs`, and `main`. First, change `build_payload` to take `today` (around line 124):

```python
def build_payload(today):
    short = parse_tab(fetch_csv(TABS[0]["gid"]), TABS[0])
    long_ = parse_tab(fetch_csv(TABS[1]["gid"]), TABS[1])
    openings = short + long_
    return {
        "synced": today,
        "source": SOURCE_URL,
        "count": len(openings),
        "shortterm": len(short),
        "longterm": len(long_),
        "openings": openings,
    }
```

Then replace `write_outputs` (around line 138) with a `data_dir_path` helper plus a `data_dir`-taking writer:

```python
def data_dir_path():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, os.pardir))
    return os.path.join(repo_root, "data")


def write_outputs(payload, data_dir):
    os.makedirs(data_dir, exist_ok=True)
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    with open(os.path.join(data_dir, "openings.json"), "w", encoding="utf-8") as handle:
        handle.write(json_text)
    with open(os.path.join(data_dir, "openings.js"), "w", encoding="utf-8") as handle:
        handle.write("window.OPENINGS = " + json_text + ";")
```

Then replace `main` (around line 150):

```python
def main():
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    data_dir = data_dir_path()
    try:
        payload = build_payload(today)
    except RuntimeError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    stamp_recency(payload["openings"], load_previous(data_dir), today)
    write_outputs(payload, data_dir)
    print("Synced %s openings (short %s, long %s)." % (
        payload["count"], payload["shortterm"], payload["longterm"]))
    return 0
```

- [ ] **Step 6: Re-run tests; confirm still green**

Run: `python tools/test_build_openings.py`
Expected: PASS — `OK`. (No live network needed; tests exercise the pure functions only.)

- [ ] **Step 7: Commit**

```bash
git add tools/build_openings.py tools/test_build_openings.py
git commit -m "feat(build): stamp firstSeen/lastChanged via snapshot diff"
```

---

### Task 2: Tested `js/recency.js` helper

**Files:**
- Create: `js/recency.js`
- Test: `tests/recency.test.js`

**Interfaces:**
- Produces (exposed as `Recency` global in the browser, `module.exports` in Node):
  - `daysBetween(aIso, bIso) -> number` — whole days `b - a` for `YYYY-MM-DD` strings; `NaN` if unparseable.
  - `recencyTag(firstSeen, lastChanged, trackStart, synced, windowDays) -> "新" | "更新" | ""`.

- [ ] **Step 1: Write the failing test**

Create `tests/recency.test.js`:

```javascript
const test = require("node:test");
const assert = require("node:assert");
const { daysBetween, recencyTag } = require("../js/recency.js");

test("daysBetween counts whole days", () => {
  assert.strictEqual(daysBetween("2026-06-01", "2026-06-15"), 14);
});

test("cold start (firstSeen == trackStart) yields no badge", () => {
  assert.strictEqual(recencyTag("2026-06-30", "2026-06-30", "2026-06-30", "2026-06-30", 14), "");
});

test("new within window yields 新", () => {
  assert.strictEqual(recencyTag("2026-07-02", "2026-07-02", "2026-06-30", "2026-07-05", 14), "新");
});

test("updated within window yields 更新", () => {
  assert.strictEqual(recencyTag("2026-06-30", "2026-07-03", "2026-06-30", "2026-07-05", 14), "更新");
});

test("change older than window yields no badge", () => {
  assert.strictEqual(recencyTag("2026-06-30", "2026-07-01", "2026-06-30", "2026-07-20", 14), "");
});

test("new beats updated", () => {
  assert.strictEqual(recencyTag("2026-07-04", "2026-07-04", "2026-06-30", "2026-07-05", 14), "新");
});

test("no tracking data yields no badge", () => {
  assert.strictEqual(recencyTag("", "", "", "2026-07-05", 14), "");
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test tests/`
Expected: FAIL — cannot find module `../js/recency.js`.

- [ ] **Step 3: Implement `js/recency.js`**

Create `js/recency.js`:

```javascript
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Recency = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // Whole-day difference (b - a) between two "YYYY-MM-DD" dates; NaN if unparseable.
  function daysBetween(aIso, bIso) {
    var a = Date.parse(aIso + "T00:00:00Z");
    var b = Date.parse(bIso + "T00:00:00Z");
    if (isNaN(a) || isNaN(b)) return NaN;
    return Math.round((b - a) / 86400000);
  }

  // "新" if the row first appeared after tracking began and within the window;
  // "更新" if its content last changed after tracking began and within the window;
  // "" otherwise — including the cold start (firstSeen == trackStart) and dateless data.
  function recencyTag(firstSeen, lastChanged, trackStart, synced, windowDays) {
    if (!trackStart || !synced) return "";
    function fresh(d) {
      if (!d || d <= trackStart) return false;
      var n = daysBetween(d, synced);
      return !isNaN(n) && n >= 0 && n <= windowDays;
    }
    if (fresh(firstSeen)) return "新";
    if (fresh(lastChanged)) return "更新";
    return "";
  }

  return { daysBetween: daysBetween, recencyTag: recencyTag };
});
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `node --test tests/`
Expected: PASS — `tests 7`, `pass 7`, `fail 0`.
(If Node ≥18 is not installed, skip this run; `js/recency.js` is also exercised by the Task 3 browser check. Do not add npm dependencies.)

- [ ] **Step 5: Commit**

```bash
git add js/recency.js tests/recency.test.js
git commit -m "feat(board): add tested recency tag/date helper"
```

---

### Task 3: Flat recency-sorted board in `board.html`

**Files:**
- Modify: `board.html` (CSS in `<style>`; JS in the inline `<script>`; one `<script src>` tag)

**Interfaces:**
- Consumes: `Recency.recencyTag(firstSeen, lastChanged, trackStart, synced, windowDays)` from Task 2; `firstSeen`/`lastChanged` fields from Task 1.
- Produces: a flat, recency-sorted board (no school groups), school shown inline, 「新」/「更新」 badges.

- [ ] **Step 1: Load the recency helper**

Find (around line 175):

```html
<script src="./data/openings.js"></script>
<script>
```

Replace with:

```html
<script src="./data/openings.js"></script>
<script src="./js/recency.js"></script>
<script>
```

- [ ] **Step 2: Swap dead school-group CSS for inline-school + badge CSS**

Find (around lines 42-46):

```css
  .school-group{margin:0}
  .school-head{position:sticky;top:var(--control-h);z-index:3;display:flex;align-items:center;justify-content:space-between;gap:10px;background:#eef2f8;border-top:1px solid var(--line);border-bottom:1px solid #d6dde8;border-left:3px solid var(--accent);padding:6px 10px;font-size:13px;line-height:1.25}
  .school-name{font-weight:800;color:var(--ink);min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .school-count{flex:0 0 auto;color:var(--muted);font-size:12px;font-variant-numeric:tabular-nums}
  .school-count .short{color:var(--warn);font-weight:750}
```

Replace with:

```css
  .school-inline{color:var(--muted);font-weight:650;white-space:nowrap}
  .badge.fresh{border-color:rgba(21,128,61,.3);background:#f0fdf4;color:#15803d}
  .badge.upd{border-color:rgba(31,111,235,.28);background:#eff6ff;color:var(--accent)}
```

- [ ] **Step 3: Remove the `--control-h` variable and its two media-query users**

Find (line 10) and remove the trailing `--control-h:88px`:

```css
  :root{--ink:#16181d; --muted:#5b6270; --line:#e6e8ec; --bg:#fff; --accent:#1f6feb; --accent-ink:#fff; --warn:#b45309; --soft:#f7f8fa; --control-h:88px}
```

Replace with:

```css
  :root{--ink:#16181d; --muted:#5b6270; --line:#e6e8ec; --bg:#fff; --accent:#1f6feb; --accent-ink:#fff; --warn:#b45309; --soft:#f7f8fa}
```

In the `@media (min-width:760px)` block, find and delete this line:

```css
    .school-head{padding-left:10px;padding-right:10px}
```

In the `@media (max-width:620px)` block, find and delete this line:

```css
    .school-head{top:var(--control-h);padding:5px 7px}
```

- [ ] **Step 4: Remove the now-unused sticky-offset machinery**

Find and delete the `setStickyOffset` function (around lines 443-447):

```javascript
  function setStickyOffset(){
    if (!controls) return;
    var height = Math.ceil(controls.getBoundingClientRect().height);
    document.documentElement.style.setProperty("--control-h", height + "px");
  }
```

Find `render` (around line 696) and delete the `setStickyOffset();` call so it begins:

```javascript
  function render(){
    if (!hasData) {
```

Find and delete the entire resize handler (around lines 765-770):

```javascript
  window.addEventListener("resize", function(){
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(function(){
      setStickyOffset();
    }, 80);
  });
```

- [ ] **Step 5: Add recency config globals**

Find (around lines 204-205):

```javascript
  var NOW = new Date();
  var NOW_CODE = NOW.getFullYear() * 12 + NOW.getMonth();
```

Add immediately after:

```javascript
  var RECENCY_WINDOW_DAYS = 14;
  var SYNCED = text(rawData && rawData.synced);
  var TRACK_START = "";  // earliest firstSeen across cards; set after mergeEntities
```

- [ ] **Step 6: Carry `firstSeen`/`lastChanged` through the merge**

Find the `firstNonEmpty` helper (around lines 306-309) and add two date helpers right after it:

```javascript
  function minDate(items, key){
    var best = ""; items.forEach(function(it){ var v = text(it[key]); if (v && (!best || v < best)) best = v; }); return best;
  }
  function maxDate(items, key){
    var best = ""; items.forEach(function(it){ var v = text(it[key]); if (v && v > best) best = v; }); return best;
  }
```

In `mergeEntities`, find the merged-item object (around lines 359-374) and add two fields (after the `materials:` line, before the closing `};`):

```javascript
        materials: joinUnique(items, "materials", " / "),
        firstSeen: minDate(items, "firstSeen"),
        lastChanged: maxDate(items, "lastChanged")
```

(Single-row entries already carry `firstSeen`/`lastChanged` on `entry.item`, so no change is needed for them.)

- [ ] **Step 7: Replace `groupEntries` with a flat comparator**

Find and delete the whole `groupEntries` function (around lines 500-526). In its place add:

```javascript
  function compareEntries(a, b){
    var la = text(a.item.lastChanged), lb = text(b.item.lastChanged);
    if (la !== lb) return la < lb ? 1 : -1;  // newer date first; empty sorts last
    var c = normalizedSchool(a.item).localeCompare(normalizedSchool(b.item), "en", { sensitivity: "base" });
    if (c !== 0) return c;
    return text(a.item.faculty).localeCompare(text(b.item.faculty), "en", { sensitivity: "base" });
  }
```

- [ ] **Step 8: Delete `makeGroup`**

Find and delete the whole `makeGroup` function (around lines 664-688). Nothing else references it after Step 9.

- [ ] **Step 9: Render a flat sorted list**

In `render`, find the grouping block (around lines 719-726):

```javascript
    var fragment = document.createDocumentFragment();
    groupEntries(filtered).forEach(function(group){
      fragment.appendChild(makeGroup(group));
    });
    emptyMessage.classList.add("hidden");
    emptyMessage.textContent = "";
    clearElement(results);
    results.appendChild(fragment);
```

Replace with:

```javascript
    filtered.sort(compareEntries);
    var fragment = document.createDocumentFragment();
    filtered.forEach(function(entry){ fragment.appendChild(makeRow(entry)); });
    emptyMessage.classList.add("hidden");
    emptyMessage.textContent = "";
    clearElement(results);
    results.appendChild(fragment);
```

- [ ] **Step 10: Show the recency badge + school inline in each row**

In `makeRow`, find (around lines 609-612):

```javascript
    var main = document.createElement("div");
    main.className = "row-main";
    main.appendChild(makeFaculty(item));
    main.appendChild(createText("span", "sep", "·"));
```

Replace with:

```javascript
    var main = document.createElement("div");
    main.className = "row-main";
    var tag = (typeof Recency !== "undefined")
      ? Recency.recencyTag(text(item.firstSeen), text(item.lastChanged), TRACK_START, SYNCED, RECENCY_WINDOW_DAYS)
      : "";
    if (tag) main.appendChild(makeBadge(tag, tag === "新" ? "fresh" : "upd"));
    main.appendChild(createText("span", "school-inline", normalizedSchool(item)));
    main.appendChild(createText("span", "sep", "·"));
    main.appendChild(makeFaculty(item));
    main.appendChild(createText("span", "sep", "·"));
```

- [ ] **Step 11: Compute `TRACK_START` after the merge**

Find (around line 772):

```javascript
  openings = mergeEntities(openings);
  setupHeader();
```

Replace with:

```javascript
  openings = mergeEntities(openings);
  TRACK_START = openings.reduce(function(min, e){
    var v = text(e.item.firstSeen); return (v && (!min || v < min)) ? v : min;
  }, "");
  setupHeader();
```

- [ ] **Step 12: Verify in a browser with a dated fixture**

Temporarily replace the data file (it is git-tracked, so restore is clean). From the repo root in PowerShell:

```powershell
@'
window.OPENINGS = {
  "synced": "2026-07-05", "source": "https://tinyurl.com/2026phd",
  "count": 5, "shortterm": 1, "longterm": 4,
  "openings": [
    {"university":"Boston University","faculty":"Alice Adams","interests":"NLP","category":"长期","types":["PhD"],"firstSeen":"2026-06-30","lastChanged":"2026-06-30"},
    {"university":"Stanford University","faculty":"Bob Brown","interests":"RL","category":"长期","types":["PhD"],"firstSeen":"2026-07-04","lastChanged":"2026-07-04"},
    {"university":"MIT","faculty":"Carol Chen","interests":"Vision","category":"长期","types":["PhD"],"firstSeen":"2026-06-30","lastChanged":"2026-07-03"},
    {"university":"Yale University","faculty":"Dan Davis","interests":"Theory","category":"短期","deadline":"2026-08-01","types":["PhD"],"firstSeen":"2026-06-30","lastChanged":"2026-06-30"},
    {"university":"CMU","faculty":"Eve Evans","interests":"Systems","category":"长期","types":["PhD"],"firstSeen":"2026-06-30","lastChanged":"2026-06-30"}
  ]
};
'@ | Set-Content -Encoding UTF8 data/openings.js
```

Open `board.html` in a browser. Expected order and badges, top to bottom:

1. **[新]** Stanford University · Bob Brown · RL (lastChanged 07-04)
2. **[更新]** MIT · Carol Chen · Vision (lastChanged 07-03)
3. Boston University · Alice Adams (no badge)
4. CMU · Eve Evans (no badge)
5. Yale University · Dan Davis · 短期 · 截止：2026-08-01 (no badge)

(Rows 3-5 share lastChanged 06-30, so they fall to school A→Z: Boston, CMU, Yale.)

Confirm: filters (关键词/学校/时效/类型/学期) still work; 全部展开/详情 still works; no console errors.

- [ ] **Step 13: Verify the dateless backward-compat fallback**

Run the same command but with every `"firstSeen"`/`"lastChanged"` pair removed from the fixture rows. Reload `board.html`. Expected: no badges anywhere; order is pure school A→Z (Boston, CMU, MIT, Stanford, Yale); no console errors.

- [ ] **Step 14: Restore the real data file**

```powershell
git checkout -- data/openings.js
```

- [ ] **Step 15: Commit**

```bash
git add board.html
git commit -m "feat(board): flat recency-first list with inline school and 新/更新 badges"
```

---

### Task 4: Integration check and README note

**Files:**
- Modify: `README.md` (one line in the repo-structure block)

- [ ] **Step 1: Re-run both test suites**

Run: `python tools/test_build_openings.py` → Expected: `OK`.
Run: `node --test tests/` → Expected: `pass 7` (skip if Node unavailable).

- [ ] **Step 2: Note the new fields in the README repo map**

In `README.md`, find:

```text
├── data/openings.js    机会数据（GitHub Action 每日生成）
```

Replace with:

```text
├── data/openings.js    机会数据（GitHub Action 每日生成，含 firstSeen/lastChanged 新鲜度字段）
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: note recency fields in README repo map"
```

- [ ] **Step 4: Deploy note (no code)**

`data/openings.js` is **not** regenerated locally — leave it to the daily Action (or a manual `python tools/build_openings.py`, which needs network to Google and stamps every row with that day's date as the cold-start baseline). Until the next sync runs, the live board serves dateless data and correctly falls back to school A→Z with no badges (verified in Task 3, Step 13). Recency differentiation begins accruing from the first new-build onward.

---

## Self-Review

**1. Spec coverage:**
- Data model (`firstSeen`/`lastChanged`) → Task 1. ✓
- Build snapshot-diff (identity key, tracked fields, today, carry/bump/new, cold-start blanks) → Task 1 Steps 3-5 + tests. ✓
- Client merge max/min dates → Task 3 Step 6. ✓
- Flat sort `lastChanged` desc → school A→Z → faculty A→Z → Task 3 Step 7. ✓
- Inline school + drop group headers → Task 3 Steps 2, 8, 9, 10. ✓
- Recency badge with window + `trackStart` gate → Task 2 + Task 3 Steps 5, 10, 11. ✓
- Backward compatibility with dateless data → Task 3 Step 13 (verified). ✓
- 短期 no longer floats → implied by removing `groupEntries`/`makeGroup`; verified by fixture order in Step 12 (Yale 短期 is last). ✓
- Zero external runtime deps → `js/recency.js` is local same-origin. ✓
- Verification (build unit tests + client fixture) → Tasks 1, 2, 3. ✓

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows complete code; every run step shows expected output. ✓

**3. Type consistency:** `recencyTag(firstSeen, lastChanged, trackStart, synced, windowDays)` — same signature in Task 2 definition, its tests, and the Task 3 call site. `stamp_recency`, `identity_key`, `tracked_signature`, `load_previous`, `data_dir_path`, `build_payload(today)`, `write_outputs(payload, data_dir)` — names consistent across Task 1 steps and tests. `compareEntries`, `minDate`, `maxDate`, `TRACK_START`, `SYNCED`, `RECENCY_WINDOW_DAYS` — consistent across Task 3 steps. ✓