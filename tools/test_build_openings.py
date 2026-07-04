import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_openings as bo  # noqa: E402

TODAY = "2026-07-05"


def row(faculty="Jane Doe", university="MIT", category="长期", interests="GNN", **extra):
    base = {"faculty": faculty, "university": university, "category": category,
            "interests": interests, "positions": "", "requirements": "",
            "materials": "", "term": "", "deadline": "", "contact": "", "homepage": ""}
    base.update(extra)
    return base


def payload(count=556, shortterm=94, longterm=462):
    return {"count": count, "shortterm": shortterm, "longterm": longterm}


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


class SanityCheck(unittest.TestCase):
    def test_healthy_build_passes(self):
        self.assertIsNone(bo.sanity_check(payload(), 556))

    def test_first_run_passes_without_previous(self):
        self.assertIsNone(bo.sanity_check(payload(), 0))

    def test_empty_short_tab_aborts(self):
        self.assertIsNotNone(
            bo.sanity_check(payload(count=462, shortterm=0, longterm=462), 556))

    def test_empty_long_tab_aborts(self):
        self.assertIsNotNone(
            bo.sanity_check(payload(count=94, shortterm=94, longterm=0), 556))

    def test_massive_drop_aborts(self):
        self.assertIsNotNone(
            bo.sanity_check(payload(count=120, shortterm=20, longterm=100), 556))

    def test_normal_shortterm_churn_passes(self):
        # short-term drains near a deadline cycle; long-term holds steady
        self.assertIsNone(
            bo.sanity_check(payload(count=470, shortterm=8, longterm=462), 556))

    def test_just_below_threshold_aborts(self):
        # 0.7 * 556 = 389.2; a total of 389 is below the retain floor
        self.assertIsNotNone(
            bo.sanity_check(payload(count=389, shortterm=15, longterm=374), 556))

    def test_at_threshold_passes(self):
        # a total of 390 clears 0.7 * 556 = 389.2
        self.assertIsNone(
            bo.sanity_check(payload(count=390, shortterm=16, longterm=374), 556))


class PreviousCount(unittest.TestCase):
    def _write(self, data_dir, text):
        with open(os.path.join(data_dir, "openings.json"), "w", encoding="utf-8") as handle:
            handle.write(text)

    def test_missing_file_returns_zero(self):
        with tempfile.TemporaryDirectory() as data_dir:
            self.assertEqual(bo.previous_count(data_dir), 0)

    def test_invalid_json_returns_zero(self):
        with tempfile.TemporaryDirectory() as data_dir:
            self._write(data_dir, "{ not valid json")
            self.assertEqual(bo.previous_count(data_dir), 0)

    def test_nonnumeric_count_returns_zero(self):
        with tempfile.TemporaryDirectory() as data_dir:
            self._write(data_dir, json.dumps({"count": "many"}))
            self.assertEqual(bo.previous_count(data_dir), 0)

    def test_valid_count_is_read(self):
        with tempfile.TemporaryDirectory() as data_dir:
            self._write(data_dir, json.dumps({"count": 556, "openings": []}))
            self.assertEqual(bo.previous_count(data_dir), 556)


class MainGuard(unittest.TestCase):
    """Lock the placement invariant: a corrupt build aborts before any write."""

    @staticmethod
    def _run_main():
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            return bo.main()

    def _seed_previous(self, data_dir, count):
        with open(os.path.join(data_dir, "openings.json"), "w", encoding="utf-8") as handle:
            json.dump({"count": count, "openings": []}, handle)

    def test_corrupt_build_aborts_without_writing(self):
        corrupt = {"synced": "2026-07-05", "source": "x", "count": 3,
                   "shortterm": 3, "longterm": 0, "openings": []}
        with tempfile.TemporaryDirectory() as data_dir:
            self._seed_previous(data_dir, 556)
            with mock.patch.object(bo, "build_payload", return_value=corrupt), \
                    mock.patch.object(bo, "data_dir_path", return_value=data_dir), \
                    mock.patch.object(bo, "write_outputs") as write_outputs:
                rc = self._run_main()
        self.assertEqual(rc, 1)
        write_outputs.assert_not_called()

    def test_healthy_build_writes(self):
        healthy = {"synced": "2026-07-05", "source": "x", "count": 556,
                   "shortterm": 94, "longterm": 462, "openings": []}
        with tempfile.TemporaryDirectory() as data_dir:
            self._seed_previous(data_dir, 556)
            with mock.patch.object(bo, "build_payload", return_value=healthy), \
                    mock.patch.object(bo, "data_dir_path", return_value=data_dir), \
                    mock.patch.object(bo, "write_outputs") as write_outputs:
                rc = self._run_main()
        self.assertEqual(rc, 0)
        write_outputs.assert_called_once()


if __name__ == "__main__":
    unittest.main()