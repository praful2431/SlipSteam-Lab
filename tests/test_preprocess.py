import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import preprocess_data as prep


class PreprocessingContractTests(unittest.TestCase):
    def test_session_time_alignment_and_xyz_preservation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw_root = root / "data" / "raw" / "tracinginsights_2026"
            session_dir = raw_root / "Example Grand Prix" / "Qualifying"
            driver_dir = session_dir / "ANT"
            driver_dir.mkdir(parents=True)
            out_root = root / "data" / "processed"

            (session_dir / "session_info.json").write_text(json.dumps({
                "t0_date": "2026-03-07T04:47:18.712000",
                "session_start_time": 761.484,
                "total_laps": None,
                "track_status": {"Time": [0.0, 20.0], "Status": ["1", "2"], "Message": ["AllClear", "Yellow"]},
                "session_status": {"Time": [0.0, 50.0], "Status": ["Inactive", "Started"]},
                "session_info": {"Name": "Qualifying"},
            }), encoding="utf-8")
            (session_dir / "session_laptimes.json").write_text(json.dumps({
                "drv": ["ANT", "LEC"], "dNum": ["12", "16"], "lap": [1, 1],
                "lST": [1986.451, 1900.0], "sesT": [2089.014, 1980.0],
                "lSD": ["2026-03-07T05:20:25.163000000", "2026-03-07T05:18:58.712000000"],
                "iacc": [False, True], "ff1G": [False, False], "del": [False, False],
            }), encoding="utf-8")
            (driver_dir / "1_tel.json").write_text(json.dumps({"tel": {
                "time": [0.0, 0.1, 0.2], "speed": [100.0, "not_numeric", 102.0],
                "rpm": [10000, 10100, 10200], "gear": [4, 4, 4],
                "throttle": [80.0, 104.0, 100.0], "brake": [0, 0, 0],
                "distance": [0.0, 2.8, 5.6], "rel_distance": [0.0, 0.01, 0.02],
                "x": [1.0, 2.0, 3.0], "y": [4.0, 5.0, 6.0], "z": [7.0, 8.0, 9.0],
                "acc_x": [1.0, 1.1, 1.2], "acc_y": [0.0, 0.1, 0.2], "acc_z": [0.0, 0.0, 0.0],
            }}), encoding="utf-8")
            (session_dir / "cor.json").write_text(json.dumps({
                "corners": [{"X": 10, "Y": 20, "Number": 1, "Letter": "A", "Angle": 45, "Distance": 30}],
                "marshal_lights": [], "marshal_sectors": [],
            }), encoding="utf-8")
            (session_dir / "corners.json").write_text(json.dumps({
                "TrackX": [1, 2, 3], "TrackY": [4, 5, 6], "TrackTime": [0.0, 0.2, 0.4],
                "MiniSectorIndex": [1, 2], "Rotation": 44,
                "CornerNumber": [1], "X": [10], "Y": [20], "Distance": [30],
                "SectionType": ["Straight"], "SectionStartPercent": [0.0],
                "SectionEndPercent": [100.0], "SectionStartDistance": [0.0],
                "SectionEndDistance": [5000.0],
                "LayoutYear": 2022, "LayoutLapSession": "FP1",
            }), encoding="utf-8")
            (session_dir / "rcm.json").write_text(json.dumps({
                "time": ["2026-03-07T05:00:00.000000000", 900.0],
                "cat": ["Flag", "Other"], "msg": ["YELLOW", "TEST"],
                "status": [None, None], "flag": ["YELLOW", None],
                "scope": ["Track", None], "sector": [None, None],
                "dNum": [None, None], "lap": [None, None],
            }), encoding="utf-8")
            (raw_root / "references").mkdir(parents=True)
            (raw_root / "references" / "event_section_mapping.json").write_text(
                json.dumps({"Example Grand Prix": "example-circuit"}), encoding="utf-8")
            (raw_root / "sections").mkdir()
            (raw_root / "sections" / "example-circuit.json").write_text(
                json.dumps([["Straight", 0.0, 50.0], ["Medium", 50.0, 100.0]]), encoding="utf-8")

            summary = prep.process_one_session(
                session_dir.parent, session_dir, raw_root, out_root, "ANT"
            )
            output_dir = out_root / "example_grand_prix" / "qualifying"
            with (output_dir / "kimi_telemetry.csv").open(encoding="utf-8") as handle:
                rows = list(__import__("csv").DictReader(handle))

            self.assertEqual(len(rows), 3)
            self.assertAlmostEqual(float(rows[0]["lap_elapsed_s"]), 0.0)
            self.assertAlmostEqual(float(rows[1]["lap_elapsed_s"]), 0.1)
            self.assertNotIn("lap_time_s", rows[0])
            self.assertAlmostEqual(float(rows[0]["session_time_s"]), 1986.451)
            self.assertAlmostEqual(float(rows[1]["session_time_s"]), 1986.551)
            self.assertEqual(rows[0]["timestamp_utc"], "2026-03-07T05:20:25.163Z")
            self.assertEqual(rows[0]["car_z_m"], "7.0")
            self.assertEqual(rows[1]["throttle_source_pct"], "104.0")
            self.assertEqual(rows[1]["speed_kmh"], "")
            self.assertIn("invalid_numeric_speed_kmh", rows[1]["quality_flags"])
            self.assertIn("throttle_outside_documented_0_100_range", rows[1]["quality_flags"])
            self.assertIn("source_timing_alignment_iacc_false", rows[0]["quality_flags"])
            self.assertEqual(rows[0]["lap_timing_alignment_accurate"], "0")
            self.assertFalse(summary["track_geometry"]["track_z_available"])
            self.assertEqual(summary["outputs"]["track_section_rows"], 2)
            self.assertEqual(summary["outputs"]["track_section_reference_rows"], 1)
            self.assertEqual(summary["outputs"]["track_minisector_rows"], 2)
            with (output_dir / "track_markers.csv").open(encoding="utf-8") as handle:
                marker_rows = list(__import__("csv").DictReader(handle))
            self.assertEqual(marker_rows[0]["marker_letter"], "A")

            audit_path = output_dir / "lap_timing_audit.csv"
            with audit_path.open(encoding="utf-8") as handle:
                audit_rows = list(__import__("csv").DictReader(handle))
            self.assertEqual(audit_rows[0]["timing_audit_status"], "unique_match_iacc_false")
            self.assertAlmostEqual(float(audit_rows[0]["derived_minus_source_lap_start_s"]), 0.0, places=3)

            rcm_path = output_dir / "race_control.csv"
            with rcm_path.open(encoding="utf-8") as handle:
                rcm_rows = list(__import__("csv").DictReader(handle))
            self.assertAlmostEqual(float(rcm_rows[0]["session_time_s"]), 761.288, places=3)
            self.assertAlmostEqual(float(rcm_rows[1]["session_time_s"]), 900.0, places=3)

    def test_driver_and_team_radio_context_exports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            session_dir = root / "Australian Grand Prix" / "Qualifying"
            session_dir.mkdir(parents=True)
            out_dir = root / "out"
            out_dir.mkdir()

            (session_dir / "drivers.json").write_text(json.dumps({
                "driver": ["ANT", "LEC"],
                "team": ["Mercedes", "Ferrari"],
                "dn": [12, 16],
                "fn": ["Andrea Kimi", "Charles"],
                "ln": ["Antonelli", "Leclerc"],
                "tc": ["00D7B6", "ED113B"],
                "url": ["https://example.test/ant.png", "https://example.test/lec.png"],
            }), encoding="utf-8")
            (session_dir / "team_radio.json").write_text(json.dumps({
                "drv": ["ANT", "LEC"],
                "dNum": ["12", "16"],
                "date": ["2026-03-07T05:20:25.163Z", "2026-03-07T05:22:00Z"],
                "file": ["ANT/radio/ANT_12_clip.mp3", "None"],
                "url": ["https://example.test/ant.mp3", "https://example.test/lec.mp3"],
            }), encoding="utf-8")
            origin = prep.parse_iso_datetime("2026-03-07T04:47:18.712000")

            driver_count, driver_warnings = prep.process_drivers(
                "Australian Grand Prix", "Qualifying", session_dir, out_dir
            )
            radio_count, radio_warnings = prep.process_team_radio(
                "Australian Grand Prix", "Qualifying", session_dir, out_dir, origin
            )

            import csv
            with (out_dir / "drivers.csv").open(encoding="utf-8") as handle:
                driver_rows = list(csv.DictReader(handle))
            with (out_dir / "team_radio.csv").open(encoding="utf-8") as handle:
                radio_rows = list(csv.DictReader(handle))

            self.assertEqual(driver_count, 2)
            self.assertEqual(driver_warnings, [])
            self.assertEqual(driver_rows[0]["driver_code"], "ANT")
            self.assertEqual(driver_rows[0]["team_name"], "Mercedes")
            self.assertEqual(radio_count, 2)
            self.assertEqual(radio_warnings, [])
            self.assertAlmostEqual(float(radio_rows[0]["session_time_s"]), 1986.451, places=3)
            self.assertEqual(radio_rows[0]["audio_file_path"], "ANT/radio/ANT_12_clip.mp3")
            self.assertEqual(radio_rows[1]["audio_file_path"], "")

    def test_object_style_track_sections_are_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            session_dir = root / "Example Grand Prix" / "Qualifying"
            session_dir.mkdir(parents=True)
            out_dir = root / "out"
            out_dir.mkdir()
            (session_dir / "corners.json").write_text(json.dumps({
                "TrackX": [0.0, 1.0],
                "TrackY": [2.0, 3.0],
                "sections": [
                    {"Type": "Straight", "StartPercent": 0.0, "EndPercent": 50.0,
                     "StartDistance": 0.0, "EndDistance": 2500.0}
                ],
            }), encoding="utf-8")

            result = prep.process_track_geometry(
                session_dir, out_dir, "Example Grand Prix", "Qualifying"
            )
            import csv
            with (out_dir / "track_section_reference.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(result["section_band_count"], 1)
            self.assertEqual(rows[0]["section_type"], "Straight")
            self.assertEqual(rows[0]["end_distance_m"], "2500.0")


if __name__ == "__main__":
    unittest.main()
