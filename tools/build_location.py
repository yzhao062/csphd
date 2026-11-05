#!/usr/bin/env python3
"""Build the location score for rank.html from public Census files.

Each campus in data/campus.csv gets a score from two inputs, weighted equally:
  - Computing jobs: County Business Patterns employment in software publishing, data
    processing, information services, and computer systems design, summed over the
    campus's metro area and any county whose centre lies within 40 km.
  - Student entertainment: County Business Patterns establishments in arts and
    recreation, bars, full-service restaurants, and cafes, summed over the campus county
    and any county whose centre lies within 20 km.

Both inputs enter on a log scale, so the score reads from 1 (best) to 100 (worst).
County Business Patterns omits some small cells. An omitted cell adds nothing, and the
school is marked partial, because a missing row is not a true zero.

Run from anywhere in the repository, then rerun tools/build_rankings.py:
    python tools/build_location.py
    python tools/build_location.py --source-dir PATH   (use local copies of the files)
"""

import argparse
import csv
import io
import math
import os
import sys
import urllib.request
import zipfile

CBP_URL = "https://www2.census.gov/programs-surveys/cbp/datasets/2023/cbp23co.zip"
COUNTIES_URL = ("https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
                "2023_Gazetteer/2023_Gaz_counties_national.zip")
METROS_URL = ("https://www2.census.gov/programs-surveys/popest/datasets/"
              "2020-2023/metro/totals/cbsa-est2023-alldata.csv")
CBP_FILE = "cbp23co.txt"
COUNTIES_FILE = "2023_Gaz_counties_national.txt"
METROS_FILE = "cbsa-est2023-alldata.csv"
TIMEOUT_SECONDS = 180

# Codes as County Business Patterns 2023 writes them (2017 NAICS).
COMPUTING_CODES = ("5112//", "518///", "519///", "5415//")
VENUE_CODES = ("71----", "7224//", "722511", "722515")
JOB_RADIUS_KM = 40
VENUE_RADIUS_KM = 20

# The Gazetteer point for San Francisco County lies offshore, pulled there by the
# Farallon Islands, about 70 km from Berkeley.
COUNTY_POINT_FIXES = {"06075": (37.7793, -122.4193)}

# A healthy run covers about 3,000 counties. Far fewer means a file changed format.
MIN_COUNTIES = 3000


def distance_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))


def parse_county_points(text):
    """Return {county FIPS: (lat, lon)} from the tab-separated Gazetteer file."""
    lines = text.splitlines()
    header = [cell.strip() for cell in lines[0].split("\t")]
    points = {}
    for line in lines[1:]:
        row = dict(zip(header, (cell.strip() for cell in line.split("\t"))))
        points[row["GEOID"]] = (float(row["INTPTLAT"]), float(row["INTPTLONG"]))
    points.update(COUNTY_POINT_FIXES)
    return points


def parse_business_counts(text):
    """Return ({county: {code: employment}}, {county: {code: establishments}})."""
    jobs, venues = {}, {}
    for row in csv.DictReader(io.StringIO(text)):
        county = row["fipstate"] + row["fipscty"]
        if row["naics"] in COMPUTING_CODES:
            jobs.setdefault(county, {})[row["naics"]] = int(row["emp"])
        elif row["naics"] in VENUE_CODES:
            venues.setdefault(county, {})[row["naics"]] = int(row["est"])
    return jobs, venues


def parse_metro_counties(text):
    """Return {CBSA code: set of county FIPS}."""
    metros = {}
    for row in csv.DictReader(io.StringIO(text)):
        if row["STCOU"].strip():
            metros.setdefault(row["CBSA"].strip(), set()).add(row["STCOU"].strip().zfill(5))
    return metros


def counties_within(points, lat, lon, radius_km):
    return {county for county, point in points.items()
            if distance_km(lat, lon, *point) <= radius_km}


def campus_inputs(campus, points, jobs, venues, metros):
    """Return (computing jobs, venues, partial) for one campus row."""
    lat, lon = float(campus["lat"]), float(campus["lon"])
    home = campus["county"]
    job_counties = (metros.get(campus["cbsa"], set())
                    | counties_within(points, lat, lon, JOB_RADIUS_KM) | {home})
    venue_counties = counties_within(points, lat, lon, VENUE_RADIUS_KM) | {home}

    job_cells = [jobs.get(county, {}) for county in job_counties]
    venue_cells = [venues.get(county, {}) for county in venue_counties]
    total_jobs = sum(sum(cell.values()) for cell in job_cells)
    total_venues = sum(sum(cell.values()) for cell in venue_cells)
    partial = (any(not any(code in cell for cell in job_cells) for code in COMPUTING_CODES)
               or any(not any(code in cell for cell in venue_cells) for code in VENUE_CODES))
    return total_jobs, total_venues, partial


def location_scores(inputs):
    """Return {school: score} from {school: (jobs, venues)}; 1 is best, 100 is worst."""
    top_jobs = max(jobs for jobs, _ in inputs.values())
    top_venues = max(venues for _, venues in inputs.values())
    strength = {
        school: (math.log1p(jobs) / math.log1p(top_jobs)
                 + math.log1p(venues) / math.log1p(top_venues)) / 2
        for school, (jobs, venues) in inputs.items()
    }
    best, worst = max(strength.values()), min(strength.values())
    return {school: round(1 + 99 * (best - value) / (best - worst), 1)
            for school, value in strength.items()}


def read_source(local_dir, name, url):
    if local_dir:
        with open(os.path.join(local_dir, name), encoding="latin-1", newline="") as handle:
            return handle.read()
    with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
        payload = response.read()
    if url.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            payload = archive.read(name)
    return payload.decode("latin-1")


def build_rows(campuses, points, jobs, venues, metros):
    if len(points) < MIN_COUNTIES:
        raise ValueError("only %d counties loaded" % len(points))
    unknown = sorted(c["school"] for c in campuses if c["county"] not in points)
    if unknown:
        raise ValueError("Campus county not in the Gazetteer: " + ", ".join(unknown))

    values = {c["school"]: campus_inputs(c, points, jobs, venues, metros) for c in campuses}
    scores = location_scores({school: v[:2] for school, v in values.items()})
    return [
        {"school": c["school"], "city": c["city"], "jobs": values[c["school"]][0],
         "venues": values[c["school"]][1], "location": scores[c["school"]],
         "partial": int(values[c["school"]][2])}
        for c in campuses
    ]


def data_dir_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-dir", help="read the three Census files from here")
    args = parser.parse_args()

    data_dir = data_dir_path()
    with open(os.path.join(data_dir, "campus.csv"), encoding="utf-8", newline="") as handle:
        campuses = list(csv.DictReader(handle))
    jobs, venues = parse_business_counts(read_source(args.source_dir, CBP_FILE, CBP_URL))
    rows = build_rows(campuses,
                      parse_county_points(read_source(args.source_dir, COUNTIES_FILE, COUNTIES_URL)),
                      jobs, venues,
                      parse_metro_counties(read_source(args.source_dir, METROS_FILE, METROS_URL)))

    with open(os.path.join(data_dir, "location.csv"), "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print("Wrote %d schools, %d partial" % (len(rows), sum(r["partial"] for r in rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
