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