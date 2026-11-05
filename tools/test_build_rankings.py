import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_rankings as br  # noqa: E402

US = {"A", "B"}


def row(dept="A", area="nips", adjusted="1.0", year="2020"):
    return {"name": "X", "dept": dept, "area": area, "count": "1.0",
            "adjustedcount": adjusted, "year": year}


def score(rows):
    return br.department_scores(rows, US, 2016, 2026)


class DepartmentScores(unittest.TestCase):
    def test_geometric_mean_over_all_areas(self):
        expected = round((81.0 * 8.0) ** (1.0 / len(br.AREAS)), 1)
        rows = [row(area="nips", adjusted="80"), row(area="cvpr", adjusted="7")]
        self.assertEqual(score(rows)["A"], expected)

    def test_venues_of_one_area_add_up_before_the_mean(self):
        split = [row(area="cvpr", adjusted="30"), row(area="iccv", adjusted="50")]
        self.assertEqual(score(split), score([row(area="cvpr", adjusted="80")]))

    def test_next_tier_venue_is_ignored(self):
        self.assertEqual(score([row(area="kdd", adjusted="80")]), {})

    def test_year_window_is_inclusive(self):
        rows = [row(year="2015"), row(dept="B", year="2016"), row(year="2027")]
        self.assertEqual(list(score(rows)), ["B"])

    def test_non_us_department_is_ignored(self):
        self.assertEqual(score([row(dept="Elsewhere")]), {})


class CompetitionRanks(unittest.TestCase):
    def test_ties_share_a_rank_and_skip_the_next(self):
        ranks = br.competition_ranks({"a": 9, "b": 7, "c": 7, "d": 1}, reverse=True)
        self.assertEqual(ranks, {"a": 1, "b": 2, "c": 2, "d": 4})

    def test_ascending_order(self):
        ranks = br.competition_ranks({"a": 3.0, "b": 1.5}, reverse=False)
        self.assertEqual(ranks, {"b": 1, "a": 2})


def located(*names):
    return {n: {"city": "X, PA", "location": 10.0, "jobs": 5, "venues": 6} for n in names}


class Combine(unittest.TestCase):
    def test_rows_join_the_three_signals_in_csrankings_order(self):
        schools = br.combine({"a": 2, "b": 1}, {"a": 8, "b": 3}, located("a", "b"))
        self.assertEqual(schools[0], {"school": "b", "city": "X, PA", "csrankings": 1, "usnews": 3,
                                      "location": 10.0, "jobs": 5, "venues": 6})
        self.assertEqual([s["school"] for s in schools], ["b", "a"])

    def test_school_usnews_never_ranks_is_left_out(self):
        schools = br.combine({"TTI Chicago": 1, "a": 2}, {"a": 30}, located("a"))
        self.assertEqual([s["school"] for s in schools], ["a"])

    def test_unaccounted_csrankings_school_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, "New U"):
            br.combine({"a": 1, "New U": 2}, {"a": 3}, located("a"))

    def test_unknown_usnews_school_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, "Typo U"):
            br.combine({"a": 1}, {"a": 1, "Typo U": 2}, located("a", "Typo U"))

    def test_school_without_a_location_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, "location.csv: b"):
            br.combine({"a": 1, "b": 2}, {"a": 1, "b": 2}, located("a"))


class BuildPayload(unittest.TestCase):
    TODAY = dt.date(2026, 11, 4)
    INSTITUTIONS = "institution,region,countryabbrv,homepage\n"

    def test_changed_header_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, "header"):
            br.build_payload("name,dept\n", self.INSTITUTIONS, {}, {}, self.TODAY)

    def test_too_few_departments_stops_the_build(self):
        authors = ",".join(br.AUTHOR_HEADER) + "\nX,A,nips,1.0,1.0,2020\n"
        institutions = self.INSTITUTIONS + "A,northamerica,us,https://a.edu\n"
        with self.assertRaisesRegex(ValueError, "only 1"):
            br.build_payload(authors, institutions, {}, {}, self.TODAY)

    def test_payload_shape(self):
        lines = ["D%d,northamerica,us,https://d.edu" % i for i in range(br.MIN_US_DEPARTMENTS)]
        rows = ["X%d,D%d,nips,1.0,%d.0,2020" % (i, i, i + 1)
                for i in range(br.MIN_US_DEPARTMENTS)]
        authors = ",".join(br.AUTHOR_HEADER) + "\n" + "\n".join(rows) + "\n"
        payload = br.build_payload(authors, self.INSTITUTIONS + "\n".join(lines) + "\n",
                                   {"D%d" % i: i + 1 for i in range(br.MIN_US_DEPARTMENTS)},
                                   located(*("D%d" % i for i in range(br.MIN_US_DEPARTMENTS))),
                                   self.TODAY)
        self.assertEqual(payload["synced"], "2026-11-04")
        self.assertEqual(payload["csrankings"]["from"], 2016)
        self.assertEqual(payload["count"], br.MIN_US_DEPARTMENTS)
        self.assertIn("TTI Chicago", payload["excluded"])


if __name__ == "__main__":
    unittest.main()
