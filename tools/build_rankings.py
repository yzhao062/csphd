#!/usr/bin/env python3
"""Build the data behind the US CS PhD ranking on rank.html.

Each school carries three signals, and the page applies the weights in js/ranking.js:
  - CSRankings: recomputed here from the public CSV files with the site's default
    view (US institutions, all areas, top-tier venues, the last ten years).
  - U.S. News Best National Universities (undergraduate): read from the hand-kept
    data/usnews_national.csv, because U.S. News publishes no data file. Its `school`
    column uses the CSRankings institution name.
  - Location: read from data/location.csv, which tools/build_location.py writes.

Every school CSRankings scores must be in the CSV or in NOT_IN_USNEWS, and every listed
school needs a location, otherwise the build stops: a school left out silently would
shift every rank below it.

Run from anywhere in the repository:
    python tools/build_rankings.py
    python tools/build_rankings.py --csrankings-dir PATH   (use local CSV copies)
"""

import argparse
import csv
import datetime as dt
import io
import json
import os
import sys
import urllib.request

CSRANKINGS_RAW = "https://raw.githubusercontent.com/emeryberger/CSrankings/gh-pages/"
CSRANKINGS_URL = "https://csrankings.org/#/index?all&us"
USNEWS_URL = "https://www.usnews.com/best-colleges/rankings/national-universities"
USNEWS_EDITION = 2027
AUTHOR_FILE = "generated-author-info.csv"
INSTITUTION_FILE = "institutions.csv"
AUTHOR_HEADER = ["name", "dept", "area", "count", "adjustedcount", "year"]
TIMEOUT_SECONDS = 120
WINDOW_YEARS = 10

# Schools with no single National Universities rank in the 2027 edition: graduate-only,
# on another U.S. News list, or given only a range. IUPUI split in 2024, so its CSRankings
# entry has no matching U.S. News school.
NOT_IN_USNEWS = {
    "Air Force Inst. of Technology",
    "CUNY",
    "IUPUI",
    "Naval Postgraduate School",
    "New Mexico Tech",
    "OHSU",
    "TTI Chicago",
    "Towson University",
    "UCCS",
    "University of New Orleans",
}

# A healthy download scores about 200 US departments. Far fewer means the CSV format
# changed or the fetch returned something else, so the build stops.
MIN_US_DEPARTMENTS = 100

# Top-tier venue -> area, copied from parentMap minus nextTier in CSRankings' csrankings.js.
# Next-tier venues (kdd, icde, pods, hpca, ndss, eurosys, fast, usenixatc, oopsla, icfp,
# ase, issta, eurographics) are off in its default view, and `pets` belongs to no area.
AREA_OF_VENUE = {
    "aaai": "ai", "ijcai": "ai",
    "cvpr": "vision", "eccv": "vision", "iccv": "vision",
    "icml": "mlmining", "iclr": "mlmining", "nips": "mlmining",
    "acl": "nlp", "emnlp": "nlp", "naacl": "nlp",
    "sigir": "inforet", "www": "inforet",
    "asplos": "arch", "isca": "arch", "micro": "arch",
    "ccs": "sec", "oakland": "sec", "usenixsec": "sec",
    "vldb": "mod", "sigmod": "mod",
    "dac": "da", "iccad": "da",
    "emsoft": "bed", "rtas": "bed", "rtss": "bed",
    "sc": "hpc", "hpdc": "hpc", "ics": "hpc",
    "mobicom": "mobile", "mobisys": "mobile", "sensys": "mobile",
    "imc": "metrics", "sigmetrics": "metrics",
    "osdi": "ops", "sosp": "ops",
    "popl": "plan", "pldi": "plan",
    "fse": "soft", "icse": "soft",
    "nsdi": "comm", "sigcomm": "comm",
    "siggraph": "graph", "siggraph-asia": "graph",
    "focs": "act", "soda": "act", "stoc": "act",
    "crypto": "crypt", "eurocrypt": "crypt",
    "cav": "log", "lics": "log",
    "ismb": "bio", "recomb": "bio",
    "ec": "ecom", "wine": "ecom",
    "chiconf": "chi", "ubicomp": "chi", "uist": "chi",
    "icra": "robotics", "iros": "robotics", "rss": "robotics",
    "vis": "visualization", "vr": "visualization",
    "sigcse": "csed",
}
AREAS = sorted(set(AREA_OF_VENUE.values()))


def us_institutions(institution_rows):
    return {row["institution"] for row in institution_rows if row["countryabbrv"] == "us"}


def department_scores(author_rows, institutions, start_year, end_year):
    """Return {department: score}, the smoothed geometric mean over all areas.

    Matches CSRankings' computeStats: the product of (adjusted count + 1) over every
    area, raised to 1 / number of areas, then rounded to one decimal before ranking.
    """
    counts = {}
    for row in author_rows:
        dept = row["dept"]
        area = AREA_OF_VENUE.get(row["area"])
        if area is None or dept not in institutions:
            continue
        if not start_year <= int(row["year"]) <= end_year:
            continue
        per_area = counts.setdefault(dept, {})
        per_area[area] = per_area.get(area, 0.0) + float(row["adjustedcount"])

    scores = {}
    for dept, per_area in counts.items():
        product = 1.0
        for area in AREAS:
            product *= per_area.get(area, 0.0) + 1.0
        scores[dept] = round(product ** (1.0 / len(AREAS)), 1)
    return scores


def competition_ranks(values, reverse):
    """Return {key: rank} with ties sharing a rank and the next rank skipped (1, 2, 2, 4)."""
    ordered = sorted(values.items(), key=lambda item: item[1], reverse=reverse)
    ranks = {}
    previous = None
    for index, (key, value) in enumerate(ordered, start=1):
        if value != previous:
            rank = index
            previous = value
        ranks[key] = rank
    return ranks


def combine(csrankings_ranks, usnews_ranks, locations):
    """Return one row per school, in CSRankings order."""
    unknown = sorted(set(usnews_ranks) - set(csrankings_ranks))
    if unknown:
        raise ValueError("U.S. News schools not found in CSRankings: " + ", ".join(unknown))
    missing = sorted(set(csrankings_ranks) - set(usnews_ranks) - NOT_IN_USNEWS)
    if missing:
        raise ValueError("CSRankings schools missing from the U.S. News CSV: "
                         + ", ".join(missing))
    unlocated = sorted(set(usnews_ranks) - set(locations))
    if unlocated:
        raise ValueError("Schools missing from data/location.csv: " + ", ".join(unlocated))

    schools = [
        {
            "school": school,
            "city": locations[school]["city"],
            "csrankings": csrankings_ranks[school],
            "usnews": rank,
            "location": locations[school]["location"],
            "jobs": locations[school]["jobs"],
            "venues": locations[school]["venues"],
        }
        for school, rank in usnews_ranks.items()
    ]
    schools.sort(key=lambda s: (s["csrankings"], s["school"]))
    return schools


def read_source(name, local_dir):
    if local_dir:
        with open(os.path.join(local_dir, name), encoding="utf-8", newline="") as handle:
            return handle.read()
    with urllib.request.urlopen(CSRANKINGS_RAW + name, timeout=TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


def parse_csv(text):
    return list(csv.DictReader(io.StringIO(text)))


def load_usnews(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return {row["school"]: int(row["rank"]) for row in csv.DictReader(handle)}


def load_locations(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return {
            row["school"]: {"city": row["city"], "location": float(row["location"]),
                            "jobs": int(row["jobs"]), "venues": int(row["venues"])}
            for row in csv.DictReader(handle)
        }


def build_payload(author_text, institution_text, usnews_ranks, locations, today):
    if author_text.splitlines()[0].replace('"', "").split(",") != AUTHOR_HEADER:
        raise ValueError(AUTHOR_FILE + " header changed")

    end_year = today.year
    start_year = end_year - WINDOW_YEARS
    scores = department_scores(parse_csv(author_text),
                               us_institutions(parse_csv(institution_text)),
                               start_year, end_year)
    if len(scores) < MIN_US_DEPARTMENTS:
        raise ValueError("only %d US departments scored" % len(scores))

    csrankings_ranks = competition_ranks(scores, reverse=True)
    schools = combine(csrankings_ranks, usnews_ranks, locations)
    return {
        "synced": today.isoformat(),
        "csrankings": {"source": CSRANKINGS_URL, "from": start_year, "to": end_year,
                       "areas": len(AREAS)},
        "usnews": {"source": USNEWS_URL, "edition": USNEWS_EDITION},
        "count": len(schools),
        "schools": schools,
        "excluded": sorted(NOT_IN_USNEWS),
    }


def data_dir_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def write_output(payload, data_dir):
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    with open(os.path.join(data_dir, "rankings.js"), "w", encoding="utf-8") as handle:
        handle.write("window.CS_RANKINGS = " + text + ";\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csrankings-dir", help="read the CSRankings CSV files from here")
    args = parser.parse_args()

    data_dir = data_dir_path()
    payload = build_payload(read_source(AUTHOR_FILE, args.csrankings_dir),
                            read_source(INSTITUTION_FILE, args.csrankings_dir),
                            load_usnews(os.path.join(data_dir, "usnews_national.csv")),
                            load_locations(os.path.join(data_dir, "location.csv")),
                            dt.date.today())
    write_output(payload, data_dir)
    print("Wrote %d schools" % payload["count"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
