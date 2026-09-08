import contextlib
import csv
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
    return {"count": count, "shortterm": shortterm, "longterm": longterm,
            "tab_counts": {"387325261": shortterm, "0": longterm}}


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
                   "shortterm": 3, "longterm": 0, "openings": [],
                   "tab_counts": {"387325261": 3, "0": 0}}
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
                   "shortterm": 94, "longterm": 462, "openings": [],
                   "tab_counts": {"387325261": 94, "0": 462}}
        with tempfile.TemporaryDirectory() as data_dir:
            self._seed_previous(data_dir, 556)
            with mock.patch.object(bo, "build_payload", return_value=healthy), \
                    mock.patch.object(bo, "data_dir_path", return_value=data_dir), \
                    mock.patch.object(bo, "write_outputs") as write_outputs:
                rc = self._run_main()
        self.assertEqual(rc, 0)
        write_outputs.assert_called_once()


HEADERS = {
    "387325261": ["University", "Faculty", "Research Interests", "Homepage",
                  "Positions", "Requirements", "How to Reach out", "Comments", ""],
    "0": ["University", "Faculty", "Research Interests", "Notes", "Homepage",
          "Positions", "Requirements", "How to Reach out", "@",
          "", "", "", "", "", "", "", "", ""],
}

SOURCE_ROWS = {
    "387325261": ["MIT", "Jane Doe", "GNN", "https://example.org/jane", "PhD, RA",
                  "CV", "jane@example.org", "Open until filled", "Research statement"],
    "0": ["Stanford", "John Doe", "NLP", "2027 Fall", "https://example.org/john",
          "PhD", "GRE optional", "john@example.org", "CV and transcript"],
}


def tab_csv(header, rows, banner=False):
    stream = io.StringIO()
    writer = csv.writer(stream)
    if banner:
        writer.writerow([""] * 7 + ["Recruitment notices", ""])
    writer.writerow(header)
    writer.writerows(rows)
    return stream.getvalue()


class BuildPipeline(unittest.TestCase):
    """Exercise fetching, parsing, guards, and real output files without network access."""

    def setUp(self):
        self.data_dir = self.enterContext(tempfile.TemporaryDirectory())
        self.csvs = {
            gid: tab_csv(header, [SOURCE_ROWS[gid]], banner=(gid == "387325261"))
            for gid, header in HEADERS.items()
        }
        self.fetch_errors = {}
        self.enterContext(mock.patch.object(bo, "data_dir_path", return_value=self.data_dir))
        self.urlopen = self.enterContext(
            mock.patch.object(bo.urllib.request, "urlopen", side_effect=self._response))
        self.writer = self.enterContext(
            mock.patch.object(bo, "write_outputs", wraps=bo.write_outputs))
        self._seed_previous(2)

    def _seed_previous(self, count):
        previous = json.dumps({"count": count, "openings": []})
        for name, text in (("openings.json", previous),
                           ("openings.js", "window.OPENINGS = " + previous + ";")):
            with open(os.path.join(self.data_dir, name), "w", encoding="utf-8") as handle:
                handle.write(text)
        self.before = self._outputs()

    def _outputs(self):
        result = {}
        for name in ("openings.json", "openings.js"):
            with open(os.path.join(self.data_dir, name), "rb") as handle:
                result[name] = handle.read()
        return result

    def _response(self, request, timeout):
        gid = request.full_url.rsplit("&gid=", 1)[1]
        if gid in self.fetch_errors:
            raise self.fetch_errors[gid]
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.getcode.return_value = 200
        response.read.return_value = self.csvs[gid].encode("utf-8-sig")
        return response

    def _run_main(self):
        self.stdout, self.stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(self.stdout), contextlib.redirect_stderr(self.stderr):
            return bo.main()

    def _assert_refused(self, message):
        self.assertEqual(self._run_main(), 1)
        self.writer.assert_not_called()
        self.assertEqual(self._outputs(), self.before)
        self.assertIn(message, self.stderr.getvalue())
        self.assertIn("refusing to overwrite", self.stderr.getvalue())
        self.assertEqual(self.stdout.getvalue(), "")

    def test_healthy_build_returns_success(self):
        self.assertEqual(self._run_main(), 0)
        self.writer.assert_called_once()
        outputs = self._outputs()
        result = json.loads(outputs["openings.json"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["shortterm"], 1)
        self.assertEqual(result["longterm"], 1)
        self.assertEqual(result["tab_counts"], {"387325261": 1, "0": 1})
        self.assertEqual(outputs["openings.js"], b"window.OPENINGS = " +
                         outputs["openings.json"] + b";")
        for tab, record in zip(bo.TABS, result["openings"]):
            with self.subTest(gid=tab["gid"]):
                for field, index in tab["cols"].items():
                    self.assertEqual(record[field], "" if index is None else
                                     SOURCE_ROWS[tab["gid"]][index])
                self.assertEqual(record["category"], tab["category"])
                self.assertEqual(record["firstSeen"], result["synced"])
                self.assertEqual(record["lastChanged"], result["synced"])
        self.assertEqual(result["openings"][0]["types"], ["PhD", "RA"])
        self.assertEqual(self.stderr.getvalue(), "")

    def test_active_tab_parsing_empty_refuses_without_writing(self):
        for gid, header in HEADERS.items():
            with self.subTest(gid=gid):
                original = self.csvs[gid]
                self.csvs[gid] = tab_csv(header, [], banner=(gid == "387325261"))
                self._assert_refused("a source tab parsed empty (gid %s" % gid)
                self.csvs[gid] = original

    def test_fetch_error_refuses_without_writing(self):
        for gid in HEADERS:
            errors = (
                bo.urllib.error.HTTPError("https://example.org", 404, "Not Found", {}, None),
                bo.urllib.error.URLError("unavailable"),
                TimeoutError("timed out"),
            )
            for error in errors:
                with self.subTest(gid=gid, error=type(error).__name__):
                    self.fetch_errors = {gid: error}
                    self._assert_refused("gid " + gid)
                    self.assertIn("404" if isinstance(error, bo.urllib.error.HTTPError)
                                  else str(error), self.stderr.getvalue())

    def test_shifted_header_refuses_without_writing(self):
        for gid, header in HEADERS.items():
            for index in range(len(header)):
                with self.subTest(gid=gid, inserted_column=index):
                    shifted_header = header[:index] + ["New column"] + header[index:]
                    values = SOURCE_ROWS[gid]
                    shifted_values = values[:index] + ["Inserted value"] + values[index:]
                    original = self.csvs[gid]
                    self.csvs[gid] = tab_csv(shifted_header, [shifted_values],
                                             banner=(gid == "387325261"))
                    self._assert_refused("header mismatch for gid " + gid)
                    self.assertIn("expected %r" % header, self.stderr.getvalue())
                    self.assertIn("received %r" % shifted_header, self.stderr.getvalue())
                    self.csvs[gid] = original

    def test_header_mismatch_before_valid_header_still_refuses(self):
        gid = "0"
        self.csvs[gid] = tab_csv(["Unexpected header", "Faculty"],
                                 [HEADERS[gid], SOURCE_ROWS[gid]])
        self._assert_refused("header mismatch for gid " + gid)

    def test_blank_column_insertion_refuses_without_writing(self):
        for gid, header in HEADERS.items():
            for index in range(9):
                with self.subTest(gid=gid, inserted_column=index):
                    original = self.csvs[gid]
                    values = SOURCE_ROWS[gid]
                    shifted_header = header[:index] + [""] + header[index:]
                    self.csvs[gid] = tab_csv(shifted_header,
                                             [values[:index] + [""] + values[index:]])
                    self._assert_refused("header mismatch for gid " + gid)
                    self.assertIn("received %r" % shifted_header, self.stderr.getvalue())
                    self.csvs[gid] = original

    def test_export_width_change_refuses_without_writing(self):
        # Pins a known cost of exact header comparison rather than a desirable outcome. Adding or
        # dropping a trailing blank column carries no data, yet it stops the sync until TABS is
        # updated. The check stays exact because the short-term materials column (index 8) is
        # unnamed: a prefix comparison would accept a blank inserted before it and silently drop
        # that column's text. See the comment in parse_tab.
        for gid, header in HEADERS.items():
            values = SOURCE_ROWS[gid]
            variants = {"one blank column added": (header + [""], values + [""])}
            if header and header[-1] == "":
                variants["one blank column removed"] = (header[:-1], values[:-1])
            for label, (changed_header, changed_values) in variants.items():
                with self.subTest(gid=gid, change=label):
                    original = self.csvs[gid]
                    self.csvs[gid] = tab_csv(changed_header, [changed_values])
                    self._assert_refused("header mismatch for gid " + gid)
                    self.csvs[gid] = original

    def test_missing_header_refuses_without_writing(self):
        for text in ("", "\n\n", ",Banner only,,,,,,,\n"):
            with self.subTest(csv=text):
                self.csvs["387325261"] = text
                self._assert_refused("missing header for gid 387325261")
                self.assertIn("expected %r" % HEADERS["387325261"], self.stderr.getvalue())
                self.assertIn("received []", self.stderr.getvalue())

    def test_banner_and_header_whitespace_are_accepted(self):
        for gid, header in HEADERS.items():
            with self.subTest(gid=gid):
                self.csvs[gid] = "\n" + tab_csv([" " + h + " " for h in header],
                                                [SOURCE_ROWS[gid]], banner=True)
        self.assertEqual(self._run_main(), 0)
        self.writer.assert_called_once()

    def test_single_tab_configuration_builds_successfully(self):
        self._seed_previous(1)
        for tab in bo.TABS:
            with self.subTest(gid=tab["gid"]), mock.patch.object(bo, "TABS", (tab,)):
                self.urlopen.reset_mock()
                self.writer.reset_mock()
                self.assertEqual(self._run_main(), 0)
                self.urlopen.assert_called_once()
                self.assertTrue(self.urlopen.call_args.args[0].full_url.endswith(
                    "&gid=" + tab["gid"]))
                result = json.loads(self._outputs()["openings.json"])
                self.assertEqual(result["count"], 1)
                self.assertEqual(result[tab["count_key"]], 1)
                self.assertEqual(result["tab_counts"], {tab["gid"]: 1})
                inactive_key = "longterm" if tab["count_key"] == "shortterm" else "shortterm"
                self.assertNotIn(inactive_key, result)
                self.writer.assert_called_once()

    def test_third_category_uses_configured_count_key(self):
        tab = dict(bo.TABS[1], gid="third", category="Other", count_key="other")
        self.csvs["third"] = self.csvs["0"]
        with mock.patch.object(bo, "TABS", bo.TABS + (tab,)):
            self.assertEqual(self._run_main(), 0)
        result = json.loads(self._outputs()["openings.json"])
        self.assertEqual(result["count"], 3)
        self.assertEqual(result["other"], 1)
        self.assertEqual(result["tab_counts"]["third"], 1)
        self.assertEqual(result["openings"][-1]["category"], "Other")

    def test_shared_category_counts_are_summed(self):
        tab = dict(bo.TABS[1], gid="third")
        self.csvs["third"] = self.csvs["0"]
        with mock.patch.object(bo, "TABS", bo.TABS + (tab,)):
            self.assertEqual(self._run_main(), 0)
        result = json.loads(self._outputs()["openings.json"])
        self.assertEqual(result["longterm"], 2)
        self.assertEqual(result["tab_counts"], {"387325261": 1, "0": 1, "third": 1})

    def test_nonempty_shared_category_cannot_hide_empty_source(self):
        tab = dict(bo.TABS[1], gid="third")
        self.csvs["third"] = tab_csv(HEADERS["0"], [])
        with mock.patch.object(bo, "TABS", bo.TABS + (tab,)):
            self._assert_refused("a source tab parsed empty (gid third")

    def test_single_tab_still_enforces_retention_guard(self):
        self._seed_previous(100)
        with mock.patch.object(bo, "TABS", bo.TABS[1:]):
            self._assert_refused("below 70% of the previous 100")

    def test_zero_tabs_builds_empty_payload(self):
        with mock.patch.object(bo, "TABS", ()):
            result = bo.build_payload(TODAY)
            self.assertIsNone(bo.sanity_check(result, 0))
            self.assertIsNotNone(bo.sanity_check(result, 2))
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["tab_counts"], {})
        self.assertEqual(result["openings"], [])
        self.assertNotIn("shortterm", result)
        self.assertNotIn("longterm", result)
        self.urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
