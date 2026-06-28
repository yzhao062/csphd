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
        record["category"] = tab["category"]
        record["types"] = derive_types(cell(cells, cols["positions"]))
        openings.append(record)
    return openings


def build_payload():
    short = parse_tab(fetch_csv(TABS[0]["gid"]), TABS[0])
    long_ = parse_tab(fetch_csv(TABS[1]["gid"]), TABS[1])
    openings = short + long_
    return {
        "synced": dt.datetime.now(dt.timezone.utc).date().isoformat(),
        "source": SOURCE_URL,
        "count": len(openings),
        "shortterm": len(short),
        "longterm": len(long_),
        "openings": openings,
    }


def write_outputs(payload):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, os.pardir))
    data_dir = os.path.join(repo_root, "data")
    os.makedirs(data_dir, exist_ok=True)
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    with open(os.path.join(data_dir, "openings.json"), "w", encoding="utf-8") as handle:
        handle.write(json_text)
    with open(os.path.join(data_dir, "openings.js"), "w", encoding="utf-8") as handle:
        handle.write("window.OPENINGS = " + json_text + ";")


def main():
    try:
        payload = build_payload()
    except RuntimeError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    write_outputs(payload)
    print("Synced %s openings (short %s, long %s)." % (
        payload["count"], payload["shortterm"], payload["longterm"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
