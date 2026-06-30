#!/usr/bin/env python3
"""Build csphd PhD-opportunity data from the maintained Google Sheet.

The sheet (https://tinyurl.com/2026phd) has two tabs with different columns:
  - short-term (gid=387325261): a Comments(=deadline) column, real PI emails,
    a leading banner row. Updated frequently.
  - long-term  (gid=0):         a Term column, generic "Email" contacts.

This script fetches both, normalizes them into one schema with a `category`
("短期"/"长期") and a `deadline` field, and writes data/openings.json and
data/openings.js (which sets window.OPENINGS for the static board page).

Run from anywhere in the repository:
    python tools/build_openings.py
"""

import csv
import datetime as dt
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request

SHEET_ID = "1vcEUT_5bXYFQgIzVKpsMQlYmV2xv15VtLXq2rvXZqRk"
SOURCE_URL = "https://tinyurl.com/2026phd"
TIMEOUT_SECONDS = 30
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)

# Each tab: its category label, gid, and the 0-based CSV column index for every
# field. A field mapped to None is absent on that tab. Short-term is listed
# first so its (deadline-driven) entries sort ahead of the long-term list.
TABS = (
    {
        "category": "短期",
        "gid": "387325261",
        "cols": {"university": 0, "faculty": 1, "interests": 2, "homepage": 3,
                 "positions": 4, "requirements": 5, "contact": 6,
                 "deadline": 7, "materials": 8, "term": None},
    },
    {
        "category": "长期",
        "gid": "0",
        "cols": {"university": 0, "faculty": 1, "interests": 2, "term": 3,
                 "homepage": 4, "positions": 5, "requirements": 6,
                 "contact": 7, "materials": 8, "deadline": None},
    },
)

TYPE_PATTERNS = (
    ("PhD", re.compile(r"ph\.?\s*d|\bphd", re.IGNORECASE)),
    ("RA", re.compile(r"(^|[^a-z])ra([^a-z]|$)|research assistant", re.IGNORECASE)),
    ("Postdoc", re.compile(r"post[-\s]?doc", re.IGNORECASE)),
    ("Intern", re.compile(r"intern", re.IGNORECASE)),
)

FIELDS = ("university", "faculty", "interests", "term", "deadline",
          "homepage", "positions", "requirements", "contact", "materials")

TRACKED_FIELDS = ("interests", "positions", "requirements", "materials",
                  "term", "deadline", "contact", "homepage")


def identity_key(record):
    faculty = re.sub(r"\s+", " ", record.get("faculty") or "").strip().lower()
    school = re.sub(r"\s+", " ", record.get("university") or "").strip().lower()
    return faculty + "\x00" + school + "\x00" + (record.get("category") or "")


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

# Merge known variant spellings of the same school so the board and the
# university filter list show each school once. Applied after whitespace
# normalization; extend as new variants appear in the source sheet.
SCHOOL_ALIASES = {
    "College of William Mary": "College of William & Mary",
    "University of Queensland, Australia": "University of Queensland (Australia)",
    "University of Wisconsin, Madison": "University of Wisconsin-Madison",
}


def normalize_school(name):
    name = re.sub(r"\s+", " ", name).strip()
    return SCHOOL_ALIASES.get(name, name)


def fetch_csv(gid):
    url = ("https://docs.google.com/spreadsheets/d/" + SHEET_ID +
           "/export?format=csv&gid=" + gid)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            if response.getcode() != 200:
                raise RuntimeError("HTTP %s for gid %s" % (response.getcode(), gid))
            return response.read().decode("utf-8-sig")
    except urllib.error.HTTPError as exc:
        raise RuntimeError("HTTP %s for gid %s" % (exc.code, gid)) from exc
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError("could not fetch gid %s: %s" % (gid, exc)) from exc


def derive_types(positions):
    return [name for name, pattern in TYPE_PATTERNS if pattern.search(positions)]


def cell(cells, index):
    if index is None or index >= len(cells):
        return ""
    return cells[index].strip()


def parse_tab(csv_text, tab):
    cols = tab["cols"]
    openings = []
    for row in csv.reader(io.StringIO(csv_text)):
        cells = [c.strip() for c in row]
        university = cell(cells, cols["university"])
        faculty = cell(cells, cols["faculty"])
        # skip the banner row (empty first cell) and the header row
        if not university or not faculty or university == "University":
            continue
        record = {field: cell(cells, cols.get(field)) for field in FIELDS}
        record["university"] = normalize_school(record["university"])
        record["category"] = tab["category"]
        record["types"] = derive_types(cell(cells, cols["positions"]))
        openings.append(record)
    return openings


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


if __name__ == "__main__":
    sys.exit(main())
