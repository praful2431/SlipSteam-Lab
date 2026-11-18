import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch_data as fetch


class FetchContractTests(unittest.TestCase):
    def test_extract_section_mapping(self):
        source = '''HEADER = 1\nEVENT_SECTIONS_FILE = {\n    "Australian Grand Prix": "albert-park-circuit",\n    "Belgian Grand Prix": "spa",\n}\nOTHER = 2\n'''
        self.assertEqual(fetch.extract_section_mapping(source), {
            "Australian Grand Prix": "albert-park-circuit",
            "Belgian Grand Prix": "spa",
        })

    def test_kimi_folder_aliases(self):
        for name in ("ANT", "Kimi", "Kimi Antonelli", "Andrea Kimi Antonelli"):
            self.assertTrue(fetch.is_target_driver_folder(name, "ANT"))
        self.assertFalse(fetch.is_target_driver_folder("LEC", "ANT"))

    def test_event_slug_normalizes_accents(self):
        import preprocess_data
        self.assertEqual(preprocess_data.event_slug("São Paulo Grand Prix"), "sao_paulo_grand_prix")

    def test_optional_session_context_files_are_explicit(self):
        self.assertEqual(fetch.OPTIONAL_SESSION_FILES, {"cor.json", "drivers.json", "team_radio.json"})

    def test_raw_download_urls_are_pinned_to_commit(self):
        url = fetch.raw_url("abc123", "Australian Grand Prix/Qualifying/1_tel.json")
        self.assertIn("/abc123/Australian%20Grand%20Prix/Qualifying/1_tel.json", url)

    def test_safe_output_path_rejects_parent_traversal(self):
        with self.assertRaises(ValueError):
            fetch.safe_output_path(Path("/tmp/root"), "../escape.json")


    def test_event_resolver_accepts_dated_source_folder(self):
        entries = [{"path": "2026-03-08_Australian_Grand_Prix", "sha": "abc"}]
        resolved = fetch.resolve_event_folder("Australian Grand Prix", entries)
        self.assertEqual(resolved["sha"], "abc")

    def test_event_resolver_rejects_ambiguous_name(self):
        entries = [
            {"path": "2026_Australian_Grand_Prix"},
            {"path": "2027_Australian_Grand_Prix"},
        ]
        with self.assertRaisesRegex(ValueError, "matches multiple folders"):
            fetch.resolve_event_folder("Australian Grand Prix", entries)

    def test_event_resolver_rejects_unknown_name(self):
        with self.assertRaisesRegex(ValueError, "No event folder matches"):
            fetch.resolve_event_folder("Unknown Grand Prix", [{"path": "Australian Grand Prix"}])


    def test_preprocessor_event_filter_accepts_date_prefixed_folder(self):
        import preprocess_data
        self.assertTrue(preprocess_data.event_folder_matches(
            "2026-03-08_Australian_Grand_Prix", "Australian Grand Prix"
        ))

    def test_event_argument_is_required(self):
        with patch("sys.argv", ["fetch_data.py"]):
            with self.assertRaises(SystemExit) as error:
                fetch.parse_args()
        self.assertEqual(error.exception.code, 2)

    def test_required_session_context_files_are_selected(self):
        for filename in ("session_info.json", "session_laptimes.json", "weather.json", "rcm.json", "corners.json"):
            self.assertIn(filename, fetch.SESSION_FILES)
        self.assertIn("team_radio.json", fetch.SESSION_FILES)
        self.assertIn("drivers.json", fetch.SESSION_FILES)


if __name__ == "__main__":
    unittest.main()
