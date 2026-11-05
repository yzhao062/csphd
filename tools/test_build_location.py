import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_location as bl  # noqa: E402


def campus(school="A", lat="40.0", lon="-75.0", county="42001", cbsa="11111"):
    return {"school": school, "city": "X, PA", "lat": lat, "lon": lon,
            "county": county, "cbsa": cbsa}


ALL_JOBS = {code: 10 for code in bl.COMPUTING_CODES}
ALL_VENUES = {code: 5 for code in bl.VENUE_CODES}


class Distance(unittest.TestCase):
    def test_one_degree_of_latitude_is_about_111_km(self):
        self.assertAlmostEqual(bl.distance_km(40, -75, 41, -75), 111.2, delta=0.5)


class Parsing(unittest.TestCase):
    def test_gazetteer_header_padding_is_ignored(self):
        text = "GEOID\tINTPTLAT\tINTPTLONG        \n42001\t40.0\t-75.0     \n"
        self.assertEqual(bl.parse_county_points(text)["42001"], (40.0, -75.0))

    def test_san_francisco_point_is_fixed(self):
        text = "GEOID\tINTPTLAT\tINTPTLONG\n06075\t37.727\t-123.032\n"
        self.assertEqual(bl.parse_county_points(text)["06075"], bl.COUNTY_POINT_FIXES["06075"])

    def test_business_counts_keep_only_listed_codes(self):
        text = ('fipstate,fipscty,naics,emp,est\n'
                '42,001,5415//,100,9\n'
                '42,001,722511,70,8\n'
                '42,001,722513,60,7\n')
        jobs, venues = bl.parse_business_counts(text)
        self.assertEqual(jobs, {"42001": {"5415//": 100}})
        self.assertEqual(venues, {"42001": {"722511": 8}})

    def test_a_non_numeric_count_stops_the_build(self):
        with self.assertRaises(ValueError):
            bl.parse_business_counts('fipstate,fipscty,naics,emp,est\n42,001,5415//,N,9\n')

    def test_metro_counties_pad_to_five_digits(self):
        text = "CBSA,STCOU\n11111,1001\n11111,\n"
        self.assertEqual(bl.parse_metro_counties(text), {"11111": {"01001"}})


class CampusInputs(unittest.TestCase):
    POINTS = {"42001": (40.0, -75.0), "42002": (40.25, -75.0), "42003": (40.5, -75.0),
              "42004": (41.0, -75.0)}

    def test_jobs_reach_metro_counties_and_the_40_km_circle(self):
        jobs = {"42002": ALL_JOBS, "42003": ALL_JOBS, "42004": ALL_JOBS}
        total, _, _ = bl.campus_inputs(campus(), self.POINTS, jobs, {}, {"11111": {"42004"}})
        self.assertEqual(total, 2 * sum(ALL_JOBS.values()))

    def test_venues_stay_inside_the_20_km_circle(self):
        venues = {"42001": ALL_VENUES, "42002": ALL_VENUES}
        _, total, _ = bl.campus_inputs(campus(), self.POINTS, {}, venues, {})
        self.assertEqual(total, sum(ALL_VENUES.values()))

    def test_venues_reach_a_neighbouring_county_inside_the_20_km_circle(self):
        points = {"42001": (40.0, -75.0), "42005": (40.1, -75.0)}
        venues = {"42001": ALL_VENUES, "42005": ALL_VENUES}
        _, total, _ = bl.campus_inputs(campus(), points, {}, venues, {})
        self.assertEqual(total, 2 * sum(ALL_VENUES.values()))

    def test_the_home_county_counts_even_when_its_point_is_far_away(self):
        jobs, venues, _ = bl.campus_inputs(campus(county="42004"), self.POINTS,
                                           {"42004": ALL_JOBS}, {"42004": ALL_VENUES}, {})
        self.assertEqual((jobs, venues), (sum(ALL_JOBS.values()), sum(ALL_VENUES.values())))

    def test_an_absent_cell_marks_the_school_partial(self):
        short = {code: 10 for code in bl.COMPUTING_CODES[1:]}
        _, _, partial = bl.campus_inputs(campus(), self.POINTS, {"42001": short},
                                         {"42001": ALL_VENUES}, {})
        self.assertTrue(partial)

    def test_all_cells_present_is_not_partial(self):
        _, _, partial = bl.campus_inputs(campus(), self.POINTS, {"42001": ALL_JOBS},
                                         {"42001": ALL_VENUES}, {})
        self.assertFalse(partial)


class LocationScores(unittest.TestCase):
    def test_best_scores_1_and_worst_scores_100(self):
        scores = bl.location_scores({"big": (1000, 500), "mid": (100, 50), "small": (1, 1)})
        self.assertEqual(scores["big"], 1.0)
        self.assertEqual(scores["small"], 100.0)
        self.assertTrue(1 < scores["mid"] < 100)

    def test_log_scale_gives_diminishing_returns(self):
        scores = bl.location_scores({"a": (100000, 1000), "b": (10000, 1000), "c": (1000, 1000),
                                     "d": (1, 1)})
        self.assertLess(scores["b"] - scores["a"], 50)

    def test_jobs_and_venues_weigh_the_same(self):
        scores = bl.location_scores({"jobs": (1000, 1), "venues": (1, 1000), "both": (1000, 1000),
                                     "none": (0, 0)})
        self.assertEqual(scores["jobs"], scores["venues"])


class BuildRows(unittest.TestCase):
    def test_too_few_counties_stops_the_build(self):
        with self.assertRaisesRegex(ValueError, "only 1 counties"):
            bl.build_rows([campus()], {"42001": (40.0, -75.0)}, {}, {}, {})

    def test_campus_county_outside_the_gazetteer_stops_the_build(self):
        points = {str(i): (0.0, 0.0) for i in range(bl.MIN_COUNTIES)}
        with self.assertRaisesRegex(ValueError, "Lost U"):
            bl.build_rows([campus("Lost U")], points, {}, {}, {})


if __name__ == "__main__":
    unittest.main()
