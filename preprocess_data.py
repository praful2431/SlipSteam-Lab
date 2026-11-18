#!/usr/bin/env python3
"""Create standardized CSVs from the untouched TracingInsights raw downloads.

No values are clipped, smoothed, interpolated, resampled, or deleted. The script
normalizes names/types, aligns lap-local telemetry time to the session clock when
an unambiguous laptime record is available, and writes diagnostic reports.
Uses only the Python standard library.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

DEFAULT_DRIVER_CODE = "ANT"
KIMI_FOLDER_ALIASES = {"ant", "kim", "kimi", "kimi antonelli", "andrea kimi antonelli"}
LAP_FILE_RE = re.compile(r"^(\d+)_tel\.json$", re.IGNORECASE)
MISSING_STRINGS = {"", "none", "null", "nan", "nat", "n/a", "inf", "-inf", "infinity", "-infinity"}

TELEMETRY_FIELD_MAP = {
    "time": "lap_time_s",
    "rpm": "engine_rpm",
    "speed": "speed_kmh",
    "gear": "gear",
    "throttle": "throttle_source_pct",
    "brake": "brake_applied",
    "distance": "lap_distance_m",
    "reldistance": "lap_relative_distance",
    "distancetodriverahead": "distance_to_driver_ahead_m",
    "driverahead": "driver_ahead_code",
    "accx": "acc_x_mps2",
    "accy": "acc_y_mps2",
    "accz": "acc_z_mps2",
    "x": "car_x_m",
    "y": "car_y_m",
    "z": "car_z_m",
    "drs": "drs_status",
    "datakey": "data_key",
}
TELEMETRY_NUMERIC_FIELDS = {
    "lap_time_s", "engine_rpm", "speed_kmh", "gear", "throttle_source_pct", "brake_applied",
    "lap_distance_m", "lap_relative_distance", "distance_to_driver_ahead_m", "acc_x_mps2",
    "acc_y_mps2", "acc_z_mps2", "car_x_m", "car_y_m", "car_z_m", "drs_status",
}
TELEMETRY_OUTPUT_COLUMNS = [
    "event_name", "session_name", "driver_code", "driver_number", "lap_number", "sample_index_in_lap",
    "lap_time_s", "lap_start_time_s", "session_time_s", "timestamp_utc", "time_alignment_status",
    "lap_timing_alignment_accurate",
    "engine_rpm", "speed_kmh", "gear", "throttle_source_pct", "brake_applied", "lap_distance_m",
    "lap_relative_distance", "distance_to_driver_ahead_m", "driver_ahead_code", "acc_x_mps2", "acc_y_mps2",
    "acc_z_mps2", "car_x_m", "car_y_m", "car_z_m", "drs_status", "data_key", "quality_flags",
]

LAPTIME_FIELD_MAP = {
    "time": "lap_time_s", "lap": "lap_number", "set": "session_end_time_s", "sest": "session_end_time_s",
    "lst": "lap_start_time_s", "lsd": "lap_start_utc", "s1": "sector_1_time_s", "s2": "sector_2_time_s",
    "s3": "sector_3_time_s", "s1t": "sector_1_session_time_s", "s2t": "sector_2_session_time_s",
    "s3t": "sector_3_session_time_s", "compound": "tyre_compound", "stint": "stint_number",
    "life": "tyre_life_laps", "fresh": "tyre_fresh", "pos": "position", "status": "lap_track_status_codes",
    "pb": "personal_best", "pout": "pit_out_session_time_s", "pin": "pit_in_session_time_s",
    "vi1": "speed_trap_intermediate_1_kmh", "vi2": "speed_trap_intermediate_2_kmh",
    "vfl": "speed_trap_finish_line_kmh", "vst": "speed_trap_longest_straight_kmh",
    "ms1": "mini_sector_codes_s1", "ms2": "mini_sector_codes_s2", "ms3": "mini_sector_codes_s3",
    "qs": "qualifying_segment", "drv": "driver_code", "dnum": "driver_number", "team": "team_name",
    "lst": "lap_start_time_s", "del": "lap_deleted", "delr": "lap_deleted_reason",
    "ff1g": "fastf1_generated", "iacc": "timing_alignment_accurate", "wt": "weather_session_time_s",
    "wat": "ambient_air_temp_c", "wh": "relative_humidity_pct", "wp": "pressure_mbar",
    "wr": "rainfall", "wtt": "track_temp_c", "wwd": "wind_direction_deg", "wws": "wind_speed_mps",
}
WEATHER_FIELD_MAP = {
    "wt": "session_time_s", "wat": "ambient_air_temp_c", "wh": "relative_humidity_pct",
    "wp": "pressure_mbar", "wr": "rainfall", "wtt": "track_temp_c",
    "wwd": "wind_direction_deg", "wws": "wind_speed_mps",
}
RCM_FIELD_MAP = {
    "time": "timestamp_utc", "cat": "category", "msg": "message", "status": "status",
    "flag": "flag", "scope": "scope", "sector": "sector", "dnum": "driver_number", "lap": "lap_number",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preprocess TracingInsights raw files into Slipstream-Lab CSVs")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent,
                        help="Slipstream-Lab repository root")
    parser.add_argument("--driver-code", default=DEFAULT_DRIVER_CODE, help="Driver code to process (default ANT)")
    parser.add_argument("--event", action="append", default=[], help="Limit to an event folder name; repeatable")
    parser.add_argument("--session", action="append", default=[], help="Limit to a session folder name; repeatable")
    return parser.parse_args()


def normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def snake_case(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value))
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return value or "unnamed_field"


def clean_value(value: Any) -> Any:
    if isinstance(value, str) and value.strip().casefold() in MISSING_STRINGS:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def number(value: Any) -> float | None:
    value = clean_value(value)
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def integer(value: Any) -> int | None:
    value_num = number(value)
    if value_num is None:
        return None
    if not value_num.is_integer():
        return None
    return int(value_num)


def seconds_number(value: Any) -> float | None:
    """Parse numeric seconds and common MM:SS / HH:MM:SS duration strings."""
    direct = number(value)
    if direct is not None:
        return direct
    value = clean_value(value)
    if value is None:
        return None
    text = str(value).strip()
    day_match = re.match(r"^(-?\d+)\s+days?\s+(.+)$", text, re.IGNORECASE)
    days = int(day_match.group(1)) if day_match else 0
    if day_match:
        text = day_match.group(2)
    match = re.fullmatch(r"(-?)(\d+):(\d{2}):(\d{2})(?:\.(\d+))?", text)
    if match:
        sign = -1 if match.group(1) else 1
        fraction = float("0." + match.group(5)) if match.group(5) else 0.0
        total = days * 86400 + int(match.group(2)) * 3600 + int(match.group(3)) * 60 + int(match.group(4)) + fraction
        return sign * total
    match = re.fullmatch(r"(-?)(\d+):(\d{2})(?:\.(\d+))?", text)
    if match:
        sign = -1 if match.group(1) else 1
        fraction = float("0." + match.group(4)) if match.group(4) else 0.0
        total = days * 86400 + int(match.group(2)) * 60 + int(match.group(3)) + fraction
        return sign * total
    return None


def as_bool01(value: Any) -> int | None:
    value = clean_value(value)
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    n = number(value)
    if n in (0, 1):
        return int(n)
    text = str(value).strip().casefold()
    if text in {"true", "yes", "on"}:
        return 1
    if text in {"false", "no", "off"}:
        return 0
    return None


def csv_value(value: Any) -> Any:
    value = clean_value(value)
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, bool):
        return str(value).lower()
    return value


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key)) for key in columns})


def parallel_json_rows(payload: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Read list-of-records or column-oriented parallel-array JSON without dropping fields."""
    warnings: list[str] = []
    if isinstance(payload, dict):
        for wrapper in ("tel", "data", "telemetry", "rows", "drivers", "radio"):
            if isinstance(payload.get(wrapper), (dict, list)):
                payload = payload[wrapper]
                break
    if isinstance(payload, list):
        return [item if isinstance(item, dict) else {"value": item} for item in payload], warnings
    if not isinstance(payload, dict):
        return [], ["Payload is neither a list nor a JSON object of arrays."]
    arrays = {str(key): value for key, value in payload.items() if isinstance(value, list)}
    if not arrays:
        return [], ["No list-valued columns were found in the JSON object."]
    # Some telemetry metadata (for example dataKey) is scalar and applies to
    # every sample. Broadcast primitive scalar fields rather than dropping them.
    scalars = {
        str(key): clean_value(value)
        for key, value in payload.items()
        if not isinstance(value, (list, dict))
    }
    lengths = {key: len(values) for key, values in arrays.items()}
    if len(set(lengths.values())) > 1:
        warnings.append(f"Parallel array lengths differ: {lengths}; shorter fields are blank-padded by row index.")
    row_count = max(lengths.values())
    rows = []
    for index in range(row_count):
        row = dict(scalars)
        row.update({key: clean_value(values[index]) if index < len(values) else None for key, values in arrays.items()})
        rows.append(row)
    return rows, warnings


def parse_iso_datetime(value: Any, assume_utc: bool = True) -> datetime | None:
    value = clean_value(value)
    if value is None:
        return None
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None and assume_utc:
        result = result.replace(tzinfo=timezone.utc)
    elif result.tzinfo is not None:
        result = result.astimezone(timezone.utc)
    return result


def iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def add_seconds(base: datetime | None, seconds: float | None) -> str | None:
    if base is None or seconds is None or not math.isfinite(seconds):
        return None
    return iso_utc(base + timedelta(seconds=seconds))


def seconds_between(value: Any, origin: datetime | None) -> float | None:
    dt = parse_iso_datetime(value)
    if dt is None or origin is None:
        return None
    return (dt - origin).total_seconds()


def find_value(row: dict[str, Any], target: str) -> Any:
    wanted = normalize_key(target)
    for key, value in row.items():
        if normalize_key(key) == wanted:
            return clean_value(value)
    return None


def field_value(row: dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for alias in aliases:
        value = find_value(row, alias)
        if value is not None:
            return value
    return None


def event_slug(value: str) -> str:
    ascii_text = "".join(
        char for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_text.casefold()).strip("_")
    return slug or "unknown_event"


def folder_is_driver(name: str, driver_code: str) -> bool:
    value = normalize_key(name)
    target = normalize_key(driver_code)
    if target in {"ant", "kim", "kimi", "kimiantonelli", "andre kimiantonelli".replace(" ", "")}:
        return value in {normalize_key(x) for x in KIMI_FOLDER_ALIASES}
    return value == target


def load_session_info(session_dir: Path) -> tuple[dict[str, Any], datetime | None]:
    path = session_dir / "session_info.json"
    if not path.exists():
        return {}, None
    payload = read_json(path)
    if not isinstance(payload, dict):
        return {}, None
    origin = parse_iso_datetime(payload.get("t0_date"), assume_utc=True)
    return payload, origin


def load_laptime_index(session_dir: Path, driver_code: str) -> tuple[dict[int, list[dict[str, Any]]], list[str], list[dict[str, Any]]]:
    warnings: list[str] = []
    source_path = session_dir / "session_laptimes.json"
    if not source_path.exists():
        # Fallback to the selected driver's per-driver laptimes file.
        driver_candidates = [p for p in session_dir.iterdir() if p.is_dir() and folder_is_driver(p.name, driver_code)]
        if driver_candidates:
            candidate = driver_candidates[0] / "laptimes.json"
            if candidate.exists():
                source_path = candidate
            else:
                return {}, ["session_laptimes.json and driver laptimes.json are both missing."], []
        else:
            return {}, ["session_laptimes.json is missing."], []

    rows, row_warnings = parallel_json_rows(read_json(source_path))
    warnings.extend(row_warnings)
    index: dict[int, list[dict[str, Any]]] = {}
    driver_norm = normalize_key(driver_code)
    for row in rows:
        code = field_value(row, ("drv", "driver", "driver_code"))
        if code is not None and normalize_key(code) != driver_norm:
            continue
        lap_no = integer(field_value(row, ("lap", "lap_number")))
        if lap_no is None:
            continue
        if code is None and source_path.name == "session_laptimes.json":
            # Without a driver identifier, a merged session table cannot safely be joined.
            continue
        index.setdefault(lap_no, []).append(row)

    # If the merged session table has no rows for the requested driver, try the
    # driver's own laptimes.json rather than making an unsafe join.
    if source_path.name == "session_laptimes.json" and not index:
        driver_candidates = [p for p in session_dir.iterdir() if p.is_dir() and folder_is_driver(p.name, driver_code)]
        if driver_candidates and (driver_candidates[0] / "laptimes.json").exists():
            fallback = driver_candidates[0] / "laptimes.json"
            fallback_rows, fallback_warnings = parallel_json_rows(read_json(fallback))
            warnings.append("No matching driver rows in session_laptimes.json; driver-level laptimes.json used as alignment fallback.")
            warnings.extend(fallback_warnings)
            rows_for_index = fallback_rows
            index = {}
            for row in rows_for_index:
                lap_no = integer(field_value(row, ("lap", "lap_number")))
                if lap_no is not None:
                    index.setdefault(lap_no, []).append(row)
    return index, warnings, rows


def normalize_laptime_rows(event: str, session: str, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    output: list[dict[str, Any]] = []
    warnings: list[str] = []
    for row_index, source in enumerate(rows):
        row: dict[str, Any] = {
            "event_name": event,
            "session_name": session,
            "source_row_index": row_index,
        }
        for key, value in source.items():
            normalized_key = normalize_key(key)
            column = LAPTIME_FIELD_MAP.get(normalized_key, f"source_{snake_case(key)}")
            if column in row and row[column] != csv_value(value):
                warnings.append(f"Column collision while normalizing laptime key '{key}' to '{column}'.")
                column = f"source_{snake_case(key)}"
            row[column] = clean_value(value)
        output.append(row)
    return output, warnings


def write_dynamic_csv(path: Path, rows: list[dict[str, Any]], leading: list[str]) -> None:
    all_columns = list(leading)
    for row in rows:
        for key in row:
            if key not in all_columns:
                all_columns.append(key)
    write_csv(path, rows, all_columns)


def process_telemetry(
    event: str,
    session: str,
    session_dir: Path,
    output_dir: Path,
    driver_code: str,
    session_info: dict[str, Any],
    session_origin: datetime | None,
    lap_index: dict[int, list[dict[str, Any]]],
) -> tuple[int, dict[str, Any], list[str]]:
    driver_dirs = [p for p in session_dir.iterdir() if p.is_dir() and folder_is_driver(p.name, driver_code)]
    telemetry_files: list[tuple[int, Path]] = []
    for driver_dir in driver_dirs:
        for path in driver_dir.iterdir():
            match = LAP_FILE_RE.match(path.name)
            if path.is_file() and match:
                telemetry_files.append((int(match.group(1)), path))
    telemetry_files.sort(key=lambda item: (item[0], item[1].as_posix()))

    output_rows: list[dict[str, Any]] = []
    lap_audit_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    quality = {
        "telemetry_files": len(telemetry_files),
        "rows": 0,
        "laps_with_unique_timing_match": 0,
        "laps_without_timing_match": 0,
        "laps_with_ambiguous_timing_match": 0,
        "laps_with_iacc_false": 0,
        "laps_with_iacc_missing": 0,
        "missing_session_clock_origin": session_origin is None,
        "missing_required_source_fields": {},
        "missing_sample_values_by_field": {},
        "invalid_numeric_values": {},
        "throttle_source_values_outside_0_100": 0,
    }

    required_source_fields = ("time", "speed", "throttle", "brake", "x", "y", "z")
    field_observed: dict[str, int] = {name: 0 for name in required_source_fields}
    field_missing: dict[str, int] = {name: 0 for name in required_source_fields}
    field_invalid: dict[str, int] = {}

    for lap_number, telemetry_path in telemetry_files:
        try:
            source_rows, row_warnings = parallel_json_rows(read_json(telemetry_path))
            warnings.extend(f"{telemetry_path.name}: {item}" for item in row_warnings)
        except Exception as exc:
            warnings.append(f"Could not parse {telemetry_path}: {exc}")
            continue

        matches = lap_index.get(lap_number, [])
        lap_meta = matches[0] if len(matches) == 1 else None
        lap_start_s = seconds_number(field_value(lap_meta, ("lST", "lap_start_time_s"))) if lap_meta else None
        lap_driver_number = field_value(lap_meta, ("dNum", "driver_number")) if lap_meta else None
        iacc_raw = field_value(lap_meta, ("iacc", "timing_alignment_accurate")) if lap_meta else None
        iacc = as_bool01(iacc_raw)
        lsd_raw = field_value(lap_meta, ("lSD", "lap_start_utc")) if lap_meta else None
        lsd_dt = parse_iso_datetime(lsd_raw)
        derived_lap_start_utc = add_seconds(session_origin, lap_start_s)
        derived_lap_start_dt = parse_iso_datetime(derived_lap_start_utc)
        lsd_delta_s = (
            (derived_lap_start_dt - lsd_dt).total_seconds()
            if derived_lap_start_dt is not None and lsd_dt is not None else None
        )
        reference_lap_time_s = seconds_number(field_value(lap_meta, ("time", "lap_time_s"))) if lap_meta else None
        reference_session_end_s = seconds_number(field_value(lap_meta, ("sesT", "session_end_time_s"))) if lap_meta else None
        lap_deleted = as_bool01(field_value(lap_meta, ("del", "lap_deleted"))) if lap_meta else None
        fastf1_generated = as_bool01(field_value(lap_meta, ("ff1G", "fastf1_generated"))) if lap_meta else None

        if len(matches) == 1:
            quality["laps_with_unique_timing_match"] += 1
        elif len(matches) == 0:
            quality["laps_without_timing_match"] += 1
        else:
            quality["laps_with_ambiguous_timing_match"] += 1
            warnings.append(f"Lap {lap_number}: multiple laptime records matched; session clock alignment withheld.")
        if len(matches) == 1 and iacc == 0:
            quality["laps_with_iacc_false"] += 1
        elif len(matches) == 1 and iacc is None:
            quality["laps_with_iacc_missing"] += 1

        previous_lap_time: float | None = None
        lap_times_seen: list[float] = []
        for sample_index, source in enumerate(source_rows):
            invalid_on_sample: list[str] = []
            normalized: dict[str, Any] = {}
            for source_key, output_key in TELEMETRY_FIELD_MAP.items():
                value = find_value(source, source_key)
                if output_key in TELEMETRY_NUMERIC_FIELDS:
                    if output_key == "brake_applied":
                        converted = as_bool01(value)
                    elif output_key == "gear":
                        converted = integer(value)
                    elif output_key == "lap_time_s":
                        converted = seconds_number(value)
                    else:
                        converted = number(value)
                    if value is not None and converted is None:
                        field_invalid[output_key] = field_invalid.get(output_key, 0) + 1
                        invalid_on_sample.append(output_key)
                    normalized[output_key] = converted
                else:
                    normalized[output_key] = value

            # Keep telemetry channels not yet in the shared map rather than dropping them.
            mapped_source_keys = {normalize_key(key) for key in TELEMETRY_FIELD_MAP}
            for source_key, source_value in source.items():
                if normalize_key(source_key) not in mapped_source_keys:
                    normalized[f"source_{snake_case(str(source_key))}"] = clean_value(source_value)

            missing_on_sample: list[str] = []
            for source_field in required_source_fields:
                if find_value(source, source_field) is not None:
                    field_observed[source_field] += 1
                else:
                    field_missing[source_field] += 1
                    missing_on_sample.append(f"missing_source_{source_field}")

            lap_time_s = normalized.get("lap_time_s")
            session_time_s = lap_start_s + lap_time_s if lap_start_s is not None and lap_time_s is not None and len(matches) == 1 else None
            timestamp_utc = add_seconds(session_origin, session_time_s)
            if len(matches) == 1 and lap_start_s is not None:
                alignment_status = "aligned_from_lST_plus_lap_time"
            elif len(matches) > 1:
                alignment_status = "ambiguous_laptime_match"
            elif len(matches) == 1:
                alignment_status = "missing_lap_start_time"
            else:
                alignment_status = "no_laptime_match"

            flags: list[str] = list(missing_on_sample)
            flags.extend(f"invalid_numeric_{field}" for field in invalid_on_sample)
            if session_origin is None:
                flags.append("no_session_clock_origin")
            if alignment_status != "aligned_from_lST_plus_lap_time":
                flags.append(alignment_status)
            if lap_deleted == 1:
                flags.append("source_lap_deleted")
            if fastf1_generated == 1:
                flags.append("source_lap_fastf1_generated")
            if normalized.get("throttle_source_pct") is not None and not (0 <= normalized["throttle_source_pct"] <= 100):
                quality["throttle_source_values_outside_0_100"] += 1
            if lap_time_s is not None and previous_lap_time is not None and lap_time_s < previous_lap_time:
                flags.append("non_monotonic_lap_time")
            if lap_time_s is not None:
                previous_lap_time = lap_time_s
                lap_times_seen.append(lap_time_s)

            output = {
                "event_name": event,
                "session_name": session,
                "driver_code": driver_code.upper(),
                "driver_number": lap_driver_number,
                "lap_number": lap_number,
                "sample_index_in_lap": sample_index,
                **normalized,
                "lap_start_time_s": lap_start_s,
                "lap_timing_alignment_accurate": iacc,
                "session_time_s": session_time_s,
                "timestamp_utc": timestamp_utc,
                "time_alignment_status": alignment_status,
                "quality_flags": ";".join(flags),
            }
            output_rows.append(output)

        first_lap_time = lap_times_seen[0] if lap_times_seen else None
        last_lap_time = lap_times_seen[-1] if lap_times_seen else None
        lap_audit_rows.append({
            "event_name": event,
            "session_name": session,
            "driver_code": driver_code.upper(),
            "lap_number": lap_number,
            "telemetry_file": telemetry_path.name,
            "telemetry_sample_count": len(source_rows),
            "timing_match_count": len(matches),
            "lap_start_time_s": lap_start_s,
            "lap_start_utc_source": lsd_raw,
            "lap_start_utc_derived": derived_lap_start_utc,
            "derived_minus_source_lap_start_s": lsd_delta_s,
            "lap_timing_alignment_accurate": iacc,
            "reference_lap_time_s": reference_lap_time_s,
            "reference_session_end_time_s": reference_session_end_s,
            "lap_deleted": lap_deleted,
            "fastf1_generated": fastf1_generated,
            "first_telemetry_lap_time_s": first_lap_time,
            "last_telemetry_lap_time_s": last_lap_time,
            "last_telemetry_session_time_s": (lap_start_s + last_lap_time) if lap_start_s is not None and last_lap_time is not None and len(matches) == 1 else None,
            "last_sample_minus_reference_session_end_s": (
                lap_start_s + last_lap_time - reference_session_end_s
                if lap_start_s is not None and last_lap_time is not None and reference_session_end_s is not None and len(matches) == 1
                else None
            ),
            "time_alignment_status": (
                "aligned_from_lST_plus_lap_time" if len(matches) == 1 and lap_start_s is not None else
                "missing_lap_start_time" if len(matches) == 1 else
                "no_laptime_match" if len(matches) == 0 else "ambiguous_laptime_match"
            ),
            "timing_audit_status": (
                "unique_match_missing_lST" if len(matches) == 1 and lap_start_s is None else
                "unique_match_iacc_false" if len(matches) == 1 and iacc == 0 else
                "unique_match_iacc_true" if len(matches) == 1 and iacc == 1 else
                "unique_match_iacc_missing" if len(matches) == 1 else
                "no_match" if len(matches) == 0 else "ambiguous_match"
            ),
        })

    quality["rows"] = len(output_rows)
    quality["lap_timing_audit_rows"] = len(lap_audit_rows)
    quality["missing_sample_values_by_field"] = {key: value for key, value in field_missing.items() if value}
    for source_field, observed in field_observed.items():
        if observed == 0:
            quality["missing_required_source_fields"][source_field] = True
    quality["invalid_numeric_values"] = field_invalid
    write_dynamic_csv(output_dir / "kimi_telemetry.csv", output_rows, TELEMETRY_OUTPUT_COLUMNS)
    if lap_audit_rows:
        write_dynamic_csv(output_dir / "lap_timing_audit.csv", lap_audit_rows, [
            "event_name", "session_name", "driver_code", "lap_number", "telemetry_file",
            "telemetry_sample_count", "timing_match_count", "lap_start_time_s", "lap_start_utc_source",
            "lap_start_utc_derived", "derived_minus_source_lap_start_s", "lap_timing_alignment_accurate",
            "reference_lap_time_s", "reference_session_end_time_s", "lap_deleted", "fastf1_generated",
            "first_telemetry_lap_time_s", "last_telemetry_lap_time_s", "last_telemetry_session_time_s",
            "last_sample_minus_reference_session_end_s", "time_alignment_status", "timing_audit_status",
        ])
    return len(output_rows), quality, warnings


def process_weather(event: str, session: str, session_dir: Path, out_dir: Path, session_origin: datetime | None) -> tuple[int, list[str]]:
    path = session_dir / "weather.json"
    if not path.exists():
        return 0, []
    rows, warnings = parallel_json_rows(read_json(path))
    output = []
    headers = ["event_name", "session_name", "sample_index", "session_time_s", "timestamp_utc",
               "ambient_air_temp_c", "relative_humidity_pct", "pressure_mbar", "rainfall",
               "track_temp_c", "wind_direction_deg", "wind_speed_mps"]
    for index, source in enumerate(rows):
        row = {"event_name": event, "session_name": session, "sample_index": index}
        for key, target in WEATHER_FIELD_MAP.items():
            value = find_value(source, key)
            row[target] = number(value) if key != "wr" else clean_value(value)
        t_s = number(row.get("session_time_s"))
        row["timestamp_utc"] = add_seconds(session_origin, t_s)
        output.append(row)
    write_csv(out_dir / "weather.csv", output, headers)
    return len(output), warnings


def process_race_control(event: str, session: str, session_dir: Path, out_dir: Path, session_origin: datetime | None) -> tuple[int, list[str]]:
    path = session_dir / "rcm.json"
    if not path.exists():
        return 0, []
    rows, warnings = parallel_json_rows(read_json(path))
    output = []
    headers = ["event_name", "session_name", "message_index", "source_timestamp", "timestamp_utc", "session_time_s",
               "category", "message", "status", "flag", "scope", "sector", "driver_number", "lap_number"]
    for index, source in enumerate(rows):
        row = {"event_name": event, "session_name": session, "message_index": index}
        for source_key, target in RCM_FIELD_MAP.items():
            value = find_value(source, source_key)
            if target == "timestamp_utc":
                row["source_timestamp"] = value
                numeric_time = number(value)
                if numeric_time is not None:
                    row[target] = add_seconds(session_origin, numeric_time)
                    row["session_time_s"] = numeric_time
                else:
                    row[target] = iso_utc(parse_iso_datetime(value)) or value
                    row["session_time_s"] = seconds_between(row.get(target), session_origin)
            elif target in {"sector", "lap_number"}:
                row[target] = integer(value)
            else:
                row[target] = value
        output.append(row)
    write_csv(out_dir / "race_control.csv", output, headers)
    return len(output), warnings


def process_drivers(event: str, session: str, session_dir: Path, out_dir: Path) -> tuple[int, list[str]]:
    path = session_dir / "drivers.json"
    if not path.exists():
        return 0, []
    rows, warnings = parallel_json_rows(read_json(path))
    output: list[dict[str, Any]] = []
    for index, source in enumerate(rows):
        row: dict[str, Any] = {
            "event_name": event,
            "session_name": session,
            "driver_index": index,
            "driver_code": field_value(source, ("driver", "drv", "code")),
            "team_name": field_value(source, ("team",)),
            "driver_number": field_value(source, ("dn", "dNum", "driver_number")),
            "first_name": field_value(source, ("fn", "first_name")),
            "last_name": field_value(source, ("ln", "last_name")),
            "team_color": field_value(source, ("tc", "team_color")),
            "headshot_url": field_value(source, ("url", "headshot_url")),
        }
        known = {"driver", "drv", "code", "team", "dn", "dnum", "driver_number", "fn", "first_name", "ln", "last_name", "tc", "team_color", "url", "headshot_url"}
        for key, value in source.items():
            if normalize_key(key) not in known:
                row[f"source_{snake_case(str(key))}"] = clean_value(value)
        output.append(row)
    if output:
        write_dynamic_csv(out_dir / "drivers.csv", output,
                          ["event_name", "session_name", "driver_index", "driver_code", "team_name", "driver_number", "first_name", "last_name", "team_color", "headshot_url"])
    return len(output), warnings


def process_team_radio(event: str, session: str, session_dir: Path, out_dir: Path, session_origin: datetime | None) -> tuple[int, list[str]]:
    path = session_dir / "team_radio.json"
    if not path.exists():
        return 0, []
    rows, warnings = parallel_json_rows(read_json(path))
    output: list[dict[str, Any]] = []
    for index, source in enumerate(rows):
        raw_date = field_value(source, ("date", "time", "timestamp"))
        timestamp = iso_utc(parse_iso_datetime(raw_date)) or raw_date
        row: dict[str, Any] = {
            "event_name": event,
            "session_name": session,
            "radio_index": index,
            "driver_code": field_value(source, ("drv", "driver", "driver_code")),
            "driver_number": field_value(source, ("dNum", "driver_number")),
            "source_timestamp": raw_date,
            "timestamp_utc": timestamp,
            "session_time_s": seconds_between(timestamp, session_origin),
            "audio_file_path": field_value(source, ("file", "path")),
            "recording_url": field_value(source, ("url", "recording_url")),
        }
        known = {"date", "time", "timestamp", "drv", "driver", "driver_code", "dnum", "driver_number", "file", "path", "url", "recording_url"}
        for key, value in source.items():
            if normalize_key(key) not in known:
                row[f"source_{snake_case(str(key))}"] = clean_value(value)
        output.append(row)
    if output:
        write_dynamic_csv(out_dir / "team_radio.csv", output,
                          ["event_name", "session_name", "radio_index", "driver_code", "driver_number", "source_timestamp", "timestamp_utc", "session_time_s", "audio_file_path", "recording_url"])
    return len(output), warnings


def process_status_tables(session_info: dict[str, Any], event: str, session: str, out_dir: Path) -> tuple[int, int, list[str]]:
    track = session_info.get("track_status") if isinstance(session_info, dict) else None
    status = session_info.get("session_status") if isinstance(session_info, dict) else None
    track_rows: list[dict[str, Any]] = []
    session_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    if isinstance(track, dict):
        times = track.get("Time", [])
        codes = track.get("Status", [])
        messages = track.get("Message", [])
        track_lengths = {"Time": len(times), "Status": len(codes), "Message": len(messages)}
        if len(set(track_lengths.values())) > 1:
            warnings.append(f"Track-status array lengths differ: {track_lengths}; rows are index-aligned and shorter arrays are blank-padded.")
        for index in range(max(len(times), len(codes), len(messages))):
            track_rows.append({
                "event_name": event, "session_name": session, "event_index": index,
                "session_time_s": number(times[index]) if index < len(times) else None,
                "status_code": clean_value(codes[index]) if index < len(codes) else None,
                "message": clean_value(messages[index]) if index < len(messages) else None,
            })
    if isinstance(status, dict):
        times = status.get("Time", [])
        codes = status.get("Status", [])
        session_lengths = {"Time": len(times), "Status": len(codes)}
        if len(set(session_lengths.values())) > 1:
            warnings.append(f"Session-status array lengths differ: {session_lengths}; rows are index-aligned and shorter arrays are blank-padded.")
        for index in range(max(len(times), len(codes))):
            session_rows.append({
                "event_name": event, "session_name": session, "event_index": index,
                "session_time_s": number(times[index]) if index < len(times) else None,
                "status": clean_value(codes[index]) if index < len(codes) else None,
            })
    if track_rows:
        write_csv(out_dir / "track_status.csv", track_rows,
                  ["event_name", "session_name", "event_index", "session_time_s", "status_code", "message"])
    if session_rows:
        write_csv(out_dir / "session_status.csv", session_rows,
                  ["event_name", "session_name", "event_index", "session_time_s", "status"])
    return len(track_rows), len(session_rows), warnings


def process_track_geometry(session_dir: Path, output_dir: Path, event: str, session: str) -> dict[str, Any]:
    result: dict[str, Any] = {"source_file": None, "track_point_count": 0, "track_z_available": False, "warnings": []}
    path = session_dir / "corners.json"
    if not path.exists():
        result["warning"] = "corners.json unavailable; track geometry not exported."
        return result
    payload = read_json(path)
    if not isinstance(payload, dict):
        result["warning"] = "corners.json was not a JSON object."
        return result
    result["source_file"] = path.relative_to(session_dir.parent.parent).as_posix()
    xs = payload.get("TrackX") if isinstance(payload.get("TrackX"), list) else []
    ys = payload.get("TrackY") if isinstance(payload.get("TrackY"), list) else []
    zs = payload.get("TrackZ") if isinstance(payload.get("TrackZ"), list) else None
    times = payload.get("TrackTime") if isinstance(payload.get("TrackTime"), list) else None
    track_array_lengths = {
        name: len(values) for name, values in {
            "TrackX": xs, "TrackY": ys, "TrackZ": zs or [], "TrackTime": times or [],
        }.items() if values
    }
    if len(set(track_array_lengths.values())) > 1:
        result["warnings"].append(
            f"Track geometry array lengths differ: {track_array_lengths}; rows are index-aligned and shorter arrays are blank-padded."
        )
    count = max(len(xs), len(ys), len(zs or []), len(times or []))
    centerline_rows = []
    for index in range(count):
        centerline_rows.append({
            "event_name": event,
            "session_name": session,
            "point_index": index,
            "track_x_m": number(xs[index]) if index < len(xs) else None,
            "track_y_m": number(ys[index]) if index < len(ys) else None,
            "track_z_m": number(zs[index]) if zs is not None and index < len(zs) else None,
            "track_source_time_s": number(times[index]) if times is not None and index < len(times) else None,
        })
    if centerline_rows:
        write_csv(output_dir / "track_outline.csv", centerline_rows,
                  ["event_name", "session_name", "point_index", "track_x_m", "track_y_m", "track_z_m", "track_source_time_s"])
    result["track_point_count"] = count
    result["track_z_available"] = zs is not None and len(zs) > 0
    result["track_x_point_count"] = len(xs)
    result["track_y_point_count"] = len(ys)
    result["track_z_point_count"] = len(zs) if zs is not None else 0
    result["track_rotation_deg"] = number(payload.get("Rotation"))
    result["track_time_point_count"] = len(times) if times is not None else 0
    result["mini_sector_count"] = 0

    mini_sector_indices = payload.get("MiniSectorIndex") if isinstance(payload.get("MiniSectorIndex"), list) else []
    if mini_sector_indices:
        mini_rows = [
            {"event_name": event, "session_name": session, "mini_sector_end_index": index,
             "track_point_index": integer(value)}
            for index, value in enumerate(mini_sector_indices)
        ]
        write_csv(output_dir / "track_minisectors.csv", mini_rows,
                  ["event_name", "session_name", "mini_sector_end_index", "track_point_index"])
        result["mini_sector_count"] = len(mini_rows)

    result["layout_reference"] = {
        "layout_year": clean_value(payload.get("LayoutYear")),
        "layout_round": clean_value(payload.get("LayoutRound")),
        "layout_race_date": clean_value(payload.get("LayoutRaceDate")),
        "layout_meeting_name": clean_value(payload.get("LayoutMeetingName")),
        "layout_lap_driver_number": clean_value(payload.get("LayoutLapDriverNumber")),
        "layout_lap_number": clean_value(payload.get("LayoutLapNumber")),
        "layout_lap_session": clean_value(payload.get("LayoutLapSession")),
        "layout_lap_time_s": number(payload.get("LayoutLapTime")),
        "layout_lap_start_date": clean_value(payload.get("LayoutLapStartDate")),
        "layout_lap_start_session_time_s": number(payload.get("LayoutLapStartSessionTime")),
        "layout_lap_session_start_time_s": number(payload.get("LayoutLapSessionStartTime")),
    }

    # Corner table is sourced from the same payload's parallel arrays.
    corner_fields = {
        "CornerNumber": "corner_number", "CornerLabel": "corner_label", "CornerLetter": "corner_letter",
        "X": "corner_x_m", "Y": "corner_y_m", "Angle": "corner_angle_deg", "Distance": "corner_distance_m",
        "MVDistance": "corner_multiviewer_distance_m", "Section": "corner_speed_class", "SectionType": "track_section_type",
    }
    arrays = {key: payload.get(key) for key in corner_fields if isinstance(payload.get(key), list)}
    corner_lengths = {key: len(values) for key, values in arrays.items() if values}
    if len(set(corner_lengths.values())) > 1:
        result["warnings"].append(
            f"Corner attribute array lengths differ: {corner_lengths}; rows are index-aligned and shorter arrays are blank-padded."
        )
    corner_count = max((len(values) for values in arrays.values()), default=0)
    corner_rows = []
    for index in range(corner_count):
        row: dict[str, Any] = {"event_name": event, "session_name": session, "corner_index": index}
        for source_key, output_key in corner_fields.items():
            values = arrays.get(source_key, [])
            row[output_key] = clean_value(values[index]) if index < len(values) else None
        corner_rows.append(row)
    if corner_rows:
        write_dynamic_csv(output_dir / "track_corners.csv", corner_rows, ["event_name", "session_name", "corner_index"])
    result["corner_count"] = corner_count

    section_band_fields = {
        "SectionType": "section_type",
        "SectionStartPercent": "start_percent",
        "SectionEndPercent": "end_percent",
        "SectionStartDistance": "start_distance_m",
        "SectionEndDistance": "end_distance_m",
    }
    section_arrays = {key: payload.get(key) for key in section_band_fields if isinstance(payload.get(key), list)}
    section_lengths = {key: len(values) for key, values in section_arrays.items() if values}
    section_band_rows = []
    if any(section_arrays.values()):
        if len(set(section_lengths.values())) > 1:
            result["warnings"].append(
                f"Track section reference array lengths differ: {section_lengths}; rows are index-aligned and shorter arrays are blank-padded."
            )
        section_band_count = max((len(values) for values in section_arrays.values()), default=0)
        for index in range(section_band_count):
            row = {"event_name": event, "session_name": session, "section_index": index}
            for source_key, output_key in section_band_fields.items():
                values = section_arrays.get(source_key, [])
                value = values[index] if index < len(values) else None
                row[output_key] = number(value) if output_key in {"start_percent", "end_percent", "start_distance_m", "end_distance_m"} else clean_value(value)
            section_band_rows.append(row)
    else:
        object_sections = payload.get("sections", [])
        if isinstance(object_sections, list):
            for index, section in enumerate(object_sections):
                if not isinstance(section, dict):
                    continue
                row = {"event_name": event, "session_name": session, "section_index": index}
                aliases = {
                    "section_type": ("Type", "SectionType", "type", "section_type"),
                    "start_percent": ("StartPercent", "start_percent"),
                    "end_percent": ("EndPercent", "end_percent"),
                    "start_distance_m": ("StartDistance", "start_distance_m"),
                    "end_distance_m": ("EndDistance", "end_distance_m"),
                }
                for output_key, source_keys in aliases.items():
                    value = field_value(section, source_keys)
                    row[output_key] = number(value) if output_key in {"start_percent", "end_percent", "start_distance_m", "end_distance_m"} else clean_value(value)
                section_band_rows.append(row)
        section_band_count = len(section_band_rows)
    if section_band_rows:
        write_csv(output_dir / "track_section_reference.csv", section_band_rows,
                  ["event_name", "session_name", "section_index", "section_type", "start_percent", "end_percent", "start_distance_m", "end_distance_m"])
    result["section_band_count"] = section_band_count
    return result


def process_legacy_cor(session_dir: Path, output_dir: Path, event: str, session: str) -> int:
    """Optional marker export from legacy cor.json; does not replace corners.json."""
    path = session_dir / "cor.json"
    if not path.exists():
        return 0
    payload = read_json(path)
    if not isinstance(payload, dict):
        return 0
    rows: list[dict[str, Any]] = []
    for family in ("corners", "marshal_lights", "marshal_sectors"):
        records = payload.get(family, [])
        if not isinstance(records, list):
            continue
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            rows.append({
                "event_name": event, "session_name": session, "marker_family": family,
                "marker_index": index, "marker_number": clean_value(record.get("Number")),
                "marker_letter": clean_value(record.get("Letter")),
                "x_m": number(record.get("X")), "y_m": number(record.get("Y")),
                "angle_deg": number(record.get("Angle")), "distance_m": number(record.get("Distance")),
            })
    if rows:
        write_csv(output_dir / "track_markers.csv", rows,
                  ["event_name", "session_name", "marker_family", "marker_index", "marker_number", "marker_letter", "x_m", "y_m", "angle_deg", "distance_m"])
    return len(rows)


def process_sections(raw_root: Path, event: str, session: str, output_dir: Path) -> tuple[int, str | None]:
    mapping_path = raw_root / "references" / "event_section_mapping.json"
    if not mapping_path.exists():
        return 0, "event_section_mapping.json is missing."
    mapping = read_json(mapping_path)
    stem = mapping.get(event) if isinstance(mapping, dict) else None
    if not stem:
        return 0, f"No section-file mapping for event '{event}'."
    path = raw_root / "sections" / f"{stem}.json"
    if not path.exists():
        return 0, f"Mapped section file is missing: {path.name}."
    payload = read_json(path)
    rows = []
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                rows.append({
                    "event_name": event, "session_name": session, "section_index": index,
                    "section_type": clean_value(item[0]), "start_percent": number(item[1]), "end_percent": number(item[2]),
                })
            elif isinstance(item, dict):
                rows.append({"event_name": event, "session_name": session, "section_index": index, **item})
    if rows:
        write_dynamic_csv(output_dir / "track_sections.csv", rows,
                          ["event_name", "session_name", "section_index", "section_type", "start_percent", "end_percent"])
    return len(rows), None


def process_one_session(event_dir: Path, session_dir: Path, raw_root: Path, out_root: Path, driver_code: str) -> dict[str, Any]:
    event, session = event_dir.name, session_dir.name
    output_dir = out_root / event_slug(event) / event_slug(session)
    output_dir.mkdir(parents=True, exist_ok=True)
    session_info, session_origin = load_session_info(session_dir)
    lap_index, lap_warnings, all_lap_rows = load_laptime_index(session_dir, driver_code)
    telemetry_count, telemetry_quality, telemetry_warnings = process_telemetry(
        event, session, session_dir, output_dir, driver_code, session_info, session_origin, lap_index
    )

    # Full session laptime table is retained so all drivers remain available for context/benchmarking.
    if all_lap_rows:
        normalized_laps, normalization_warnings = normalize_laptime_rows(event, session, all_lap_rows)
        write_dynamic_csv(output_dir / "session_laptimes.csv", normalized_laps,
                          ["event_name", "session_name", "source_row_index"])
    else:
        normalized_laps, normalization_warnings = [], []

    weather_count, weather_warnings = process_weather(event, session, session_dir, output_dir, session_origin)
    rcm_count, rcm_warnings = process_race_control(event, session, session_dir, output_dir, session_origin)
    driver_count, driver_warnings = process_drivers(event, session, session_dir, output_dir)
    radio_count, radio_warnings = process_team_radio(event, session, session_dir, output_dir, session_origin)
    track_status_count, session_status_count, status_warnings = process_status_tables(session_info, event, session, output_dir)
    track_geometry = process_track_geometry(session_dir, output_dir, event, session)
    track_marker_count = process_legacy_cor(session_dir, output_dir, event, session)
    section_count, section_warning = process_sections(raw_root, event, session, output_dir)

    summary = {
        "event_name": event,
        "session_name": session,
        "driver_code_processed": driver_code.upper(),
        "session_clock_origin_utc": iso_utc(session_origin),
        "session_start_time_s": number(session_info.get("session_start_time")) if session_info else None,
        "total_laps": session_info.get("total_laps") if session_info else None,
        "session_info": session_info.get("session_info") if session_info else None,
        "outputs": {
            "kimi_telemetry_rows": telemetry_count,
            "session_laptime_rows_all_drivers": len(normalized_laps),
            "weather_rows": weather_count,
            "race_control_rows": rcm_count,
            "driver_rows": driver_count,
            "team_radio_clip_rows": radio_count,
            "track_status_rows": track_status_count,
            "session_status_rows": session_status_count,
            "track_marker_rows": track_marker_count,
            "track_section_rows": section_count,
            "track_section_reference_rows": track_geometry.get("section_band_count", 0),
            "track_minisector_rows": track_geometry.get("mini_sector_count", 0),
            "lap_timing_audit_rows": telemetry_quality.get("lap_timing_audit_rows", 0),
        },
        "track_geometry": track_geometry,
        "telemetry_quality": telemetry_quality,
        "warnings": lap_warnings + telemetry_warnings + weather_warnings + rcm_warnings + driver_warnings + radio_warnings + normalization_warnings + status_warnings + track_geometry.get("warnings", []) + ([section_warning] if section_warning else []),
        "timing_note": "session_time_s = lST + lap_time_s, where lST is read from the matched driver/lap record in session_laptimes.json.",
    }
    write_json(output_dir / "session_summary.json", summary)
    return summary


def main() -> int:
    args = parse_args()
    project_root = args.root.resolve()
    raw_root = project_root / "data" / "raw" / "tracinginsights_2026"
    out_root = project_root / "data" / "processed"
    report_root = project_root / "reports"
    if not raw_root.exists():
        raise FileNotFoundError(f"Raw data folder not found: {raw_root}. Run fetch_data.py first.")

    requested_events = {event.casefold() for event in args.event}
    requested_sessions = {session.casefold() for session in args.session}
    summaries = []
    errors = []

    for event_dir in sorted(p for p in raw_root.iterdir() if p.is_dir() and p.name != "references" and p.name != "sections"):
        if requested_events and event_dir.name.casefold() not in requested_events:
            continue
        for session_dir in sorted(p for p in event_dir.iterdir() if p.is_dir()):
            if requested_sessions and session_dir.name.casefold() not in requested_sessions:
                continue
            has_driver_dir = any(p.is_dir() and folder_is_driver(p.name, args.driver_code) for p in session_dir.iterdir())
            has_metadata = any((session_dir / name).exists() for name in ("session_info.json", "session_laptimes.json", "weather.json", "rcm.json", "corners.json", "drivers.json", "team_radio.json"))
            if not has_driver_dir and not has_metadata:
                continue
            print(f"Processing {event_dir.name} / {session_dir.name}...")
            try:
                summary = process_one_session(event_dir, session_dir, raw_root, out_root, args.driver_code)
                summaries.append(summary)
                print(f"  telemetry rows: {summary['outputs']['kimi_telemetry_rows']}")
            except Exception as exc:
                errors.append({"event": event_dir.name, "session": session_dir.name, "error": str(exc)})
                print(f"  [ERROR] {exc}", file=sys.stderr)

    report = {
        "project": "Slipstream-Lab",
        "processed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "driver_code": args.driver_code.upper(),
        "raw_root": "data/raw/tracinginsights_2026",
        "processed_root": "data/processed",
        "session_count": len(summaries),
        "error_count": len(errors),
        "sessions": summaries,
        "errors": errors,
    }
    report_root.mkdir(parents=True, exist_ok=True)
    report_path = report_root / "preprocessing_report.json"
    write_json(report_path, report)
    print(f"\nPreprocessing complete: {len(summaries)} session(s), {len(errors)} error(s).")
    print(f"Report: {report_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        raise SystemExit(2)
