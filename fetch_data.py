#!/usr/bin/env python3
"""Fetch Kimi Antonelli telemetry and relevant session/track source files.

Source: https://github.com/TracingInsights/2026

Raw JSON is saved unchanged under data/raw/tracinginsights_2026/.
The script uses only the Python standard library.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

OWNER = "TracingInsights"
REPO = "2026"
API_BASE = f"https://api.github.com/repos/{OWNER}/{REPO}"
USER_AGENT = "Slipstream-Lab/0.1 (public research data fetcher)"

# Session-level data required for timing, conditions, flags and circuit context.
SESSION_FILES = {
    "session_info.json",
    "session_laptimes.json",
    "weather.json",
    "rcm.json",
    "corners.json",
    "cor.json",            # Optional legacy marker file.
    "drivers.json",            # Optional static session driver metadata.
    "team_radio.json",     # Optional radio index; audio files are not downloaded here.
}
OPTIONAL_SESSION_FILES = {"cor.json", "drivers.json", "team_radio.json"}
REFERENCE_FILES = ("DATA_REFERENCE.md", "data_dictionary.json")
KIMI_FOLDER_ALIASES = {"ant", "kim", "kimi", "kimi antonelli", "andrea kimi antonelli"}
TELEMETRY_PATTERN = re.compile(r"^(\d+)_tel\.json$", re.IGNORECASE)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def is_target_driver_folder(name: str, driver_code: str) -> bool:
    value = norm(name)
    target = norm(driver_code)
    if target in {norm(x) for x in KIMI_FOLDER_ALIASES} or target.replace(" ", "") in {"ant", "kim", "kimiantonelli", "andrekimiantonelli"}:
        return value in {norm(x) for x in KIMI_FOLDER_ALIASES} or value.replace(" ", "") in {
            "ant", "kim", "kimiantonelli", "andrekimiantonelli"
        }
    return value == target or value.replace(" ", "") == target.replace(" ", "")


def request_bytes(url: str, *, api: bool = False, attempts: int = 5) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Connection": "close"}
    if api:
        headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=60) as response:
                return response.read()
        except HTTPError as exc:
            last_error = exc
            retryable = exc.code in {403, 429, 500, 502, 503, 504}
            if exc.code == 404:
                raise FileNotFoundError(f"Source file not found (HTTP 404): {url}") from exc
            if not retryable or attempt == attempts - 1:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
                raise RuntimeError(f"HTTP {exc.code} for {url}: {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt == attempts - 1:
                raise RuntimeError(f"Network failure for {url}: {exc}") from exc
        delay = min(2 ** attempt, 20)
        print(f"[RETRY] {type(last_error).__name__}: {last_error}; waiting {delay}s", file=sys.stderr)
        time.sleep(delay)
    raise RuntimeError(f"Could not fetch {url}: {last_error}")


def api_json(url: str) -> dict[str, Any]:
    return json.loads(request_bytes(url, api=True).decode("utf-8"))


def raw_url(commit_sha: str, repo_path: str) -> str:
    encoded = "/".join(quote(part, safe="") for part in repo_path.split("/"))
    return f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{commit_sha}/{encoded}"


def tree_entries(tree_sha: str, prefix: str = "") -> list[dict[str, Any]]:
    """Read a Git tree recursively; fall back to per-directory requests if truncated."""
    recursive_url = f"{API_BASE}/git/trees/{tree_sha}?recursive=1"
    payload = api_json(recursive_url)
    if not payload.get("truncated", False):
        result = []
        for entry in payload.get("tree", []):
            item = dict(entry)
            item["path"] = str(PurePosixPath(prefix, item.get("path", ""))) if prefix else item.get("path", "")
            result.append(item)
        return result

    # GitHub truncates very large recursive trees. Enumerate one level at a time.
    shallow = api_json(f"{API_BASE}/git/trees/{tree_sha}")
    result: list[dict[str, Any]] = []
    for entry in shallow.get("tree", []):
        name = entry.get("path", "")
        full = str(PurePosixPath(prefix, name)) if prefix else name
        if entry.get("type") == "tree":
            result.extend(tree_entries(entry["sha"], full))
        else:
            item = dict(entry)
            item["path"] = full
            result.append(item)
    return result


def extract_section_mapping(sq_text: str) -> dict[str, str]:
    match = re.search(r"(?ms)^EVENT_SECTIONS_FILE\s*=\s*(\{.*?^\})", sq_text)
    if not match:
        raise ValueError("EVENT_SECTIONS_FILE mapping was not found in SQ.py")
    mapping = ast.literal_eval(match.group(1))
    if not isinstance(mapping, dict):
        raise ValueError("EVENT_SECTIONS_FILE is not a dictionary")
    return {
        str(event).strip(): str(stem).strip()
        for event, stem in mapping.items()
        if isinstance(event, str) and isinstance(stem, str)
    }


def safe_output_path(root: Path, repo_path: str) -> Path:
    relative = PurePosixPath(repo_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Unsafe repository path: {repo_path}")
    return root.joinpath(*relative.parts)


def write_download(
    commit_sha: str,
    repo_path: str,
    raw_repo_root: Path,
    force: bool,
    destination_relative: str | None = None,
) -> dict[str, Any]:
    output_path = safe_output_path(raw_repo_root, destination_relative or repo_path)
    source = raw_url(commit_sha, repo_path)
    local_relative = output_path.relative_to(raw_repo_root.parents[2]).as_posix()
    if output_path.exists() and not force:
        payload_hash = hashlib.sha256(output_path.read_bytes()).hexdigest()
        return {
            "repository_path": repo_path,
            "local_path": local_relative,
            "source_url": source,
            "status": "already_present",
            "bytes": output_path.stat().st_size,
            "sha256": payload_hash,
        }

    payload = request_bytes(source)
    if repo_path.lower().endswith(".json"):
        # Validate JSON but write the original bytes unchanged.
        json.loads(payload.decode("utf-8-sig"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temp_path.write_bytes(payload)
    temp_path.replace(output_path)
    return {
        "repository_path": repo_path,
        "local_path": local_relative,
        "source_url": source,
        "source_commit": commit_sha,
        "status": "downloaded",
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Kimi telemetry and F1 session context from TracingInsights/2026")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent,
                        help="Slipstream-Lab repository root (defaults to this script's directory)")
    parser.add_argument("--driver", default="ANT", help="Driver abbreviation/folder (default: ANT for Kimi Antonelli)")
    parser.add_argument("--event", action="append", default=[],
                        help="Limit to an event folder name; may be supplied more than once")
    parser.add_argument("--force", action="store_true", help="Re-download and replace existing raw files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.root.resolve()
    raw_root = project_root / "data" / "raw" / "tracinginsights_2026"
    report_root = project_root / "reports"
    raw_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    manifest_path = report_root / "fetch_manifest.json"
    existing_raw_files = [path for path in raw_root.rglob("*") if path.is_file() and path.name != ".gitkeep"]

    print(f"Connecting to {OWNER}/{REPO}...")
    repo_meta = api_json(API_BASE)
    branch = repo_meta.get("default_branch", "main")
    branch_data = api_json(f"{API_BASE}/branches/{quote(branch, safe='')}")
    commit_sha = branch_data["commit"]["sha"]
    previous_manifest: dict[str, Any] = {}
    previous_file_records: dict[str, dict[str, Any]] = {}
    source_commit_changed = False
    if manifest_path.exists():
        previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        previous_commit = previous_manifest.get("source_commit")
        if existing_raw_files and previous_commit != commit_sha:
            if not args.force:
                raise RuntimeError(
                    f"Raw data was fetched from commit {previous_commit}, but the source is now {commit_sha}. "
                    "Use --force for a full refresh to avoid mixing source versions."
                )
            if args.event:
                raise RuntimeError(
                    "A source-commit change requires a full refresh. Remove --event and run fetch_data.py --force "
                    "so selected event folders cannot be mixed with older raw files."
                )
            source_commit_changed = True
        elif previous_commit == commit_sha:
            previous_file_records = {
                item.get("repository_path"): item
                for item in previous_manifest.get("files", [])
                if item.get("repository_path")
            }
    elif existing_raw_files:
        raise RuntimeError(
            "Raw files already exist but no fetch_manifest.json can verify their source commit. "
            "Move or remove data/raw/tracinginsights_2026/ first, then run fetch_data.py. "
            "Do not use --force to overwrite untracked raw data because its source revision is unknown."
        )
    if source_commit_changed:
        # A full refresh must not leave files that belonged only to the older commit.
        shutil.rmtree(raw_root)
        raw_root.mkdir(parents=True, exist_ok=True)
        previous_file_records = {}
        print("Source commit changed: cleared the previous fetched raw snapshot before refreshing.")

    root_tree_sha = branch_data["commit"]["commit"]["tree"]["sha"]
    root_tree = api_json(f"{API_BASE}/git/trees/{root_tree_sha}").get("tree", [])

    event_dirs = [
        entry for entry in root_tree
        if entry.get("type") == "tree" and "grand prix" in norm(entry.get("path", ""))
    ]
    if not event_dirs:
        raise RuntimeError("No Grand Prix folders found at repository root; source layout may have changed.")

    if args.event:
        requested = [norm(item) for item in args.event]
        event_dirs = [entry for entry in event_dirs if any(norm(entry["path"]) == name for name in requested)]
        if not event_dirs:
            raise ValueError(f"No matching event folder found for: {args.event}")

    # Keep the upstream mapping source and its parsed form for reproducible track-section lookup.
    mapping_record: dict[str, Any] = {"status": "unavailable", "error": None}
    section_mapping: dict[str, str] = {}
    try:
        sq_path = "SQ.py"
        sq_bytes = request_bytes(raw_url(commit_sha, sq_path))
        sq_text = sq_bytes.decode("utf-8-sig")
        section_mapping = extract_section_mapping(sq_text)
        sq_out = raw_root / "references" / "SQ.py"
        sq_out.parent.mkdir(parents=True, exist_ok=True)
        sq_out.write_bytes(sq_bytes)
        mapping_out = raw_root / "references" / "event_section_mapping.json"
        mapping_out.write_text(json.dumps(section_mapping, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        mapping_record = {
            "status": "downloaded",
            "local_path": mapping_out.relative_to(project_root).as_posix(),
            "source_path": sq_path,
            "source_commit": commit_sha,
            "sha256_sq_py": hashlib.sha256(sq_bytes).hexdigest(),
            "mapping_entries": len(section_mapping),
        }
    except Exception as exc:
        mapping_record["error"] = str(exc)
        print(f"[WARN] Circuit section mapping unavailable: {exc}", file=sys.stderr)

    downloaded: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    reference_records: list[dict[str, Any]] = []
    for reference_name in REFERENCE_FILES:
        try:
            record = write_download(
                commit_sha, reference_name, raw_root, args.force,
                destination_relative=f"references/{reference_name}",
            )
            reference_records.append(record)
            print(f"  [{record['status']}] reference {reference_name}")
        except Exception as exc:
            failures.append({"repository_path": reference_name, "error": str(exc)})
            print(f"  [FAILED] reference {reference_name}: {exc}", file=sys.stderr)
    for event_index, event_entry in enumerate(event_dirs, start=1):
        event_name = event_entry["path"]
        print(f"\n[{event_index}/{len(event_dirs)}] Scanning {event_name}...")
        try:
            entries = tree_entries(event_entry["sha"], event_name)
        except Exception as exc:
            failures.append({"repository_path": event_name, "error": str(exc)})
            print(f"[ERROR] Could not scan {event_name}: {exc}", file=sys.stderr)
            continue

        chosen_paths: set[str] = set()
        session_names: set[str] = set()
        for entry in entries:
            if entry.get("type") != "blob":
                continue
            repo_path = entry.get("path", "")
            parts = PurePosixPath(repo_path).parts
            if len(parts) < 3:
                continue
            session_names.add(parts[1])
            filename = parts[-1]
            parent_name = parts[-2] if len(parts) >= 2 else ""

            # Session-level context. This includes the two files missing from the old fetcher.
            if len(parts) == 3 and filename in SESSION_FILES:
                chosen_paths.add(repo_path)

            # Kimi's per-driver lap timing and per-lap telemetry JSON.
            if is_target_driver_folder(parent_name, args.driver):
                if filename == "laptimes.json":
                    chosen_paths.add(repo_path)
                if TELEMETRY_PATTERN.match(filename):
                    chosen_paths.add(repo_path)

        print(f"  Session folders found: {len(session_names)}; selected source files: {len(chosen_paths)}")
        for repo_path in sorted(chosen_paths):
            try:
                record = write_download(commit_sha, repo_path, raw_root, args.force)
                downloaded.append(record)
                print(f"  [{record['status']}] {repo_path}")
            except FileNotFoundError as exc:
                if PurePosixPath(repo_path).name in OPTIONAL_SESSION_FILES:
                    downloaded.append({
                        "repository_path": repo_path,
                        "source_url": raw_url(commit_sha, repo_path),
                        "status": "not_found_optional",
                        "source_commit": commit_sha,
                    })
                    print(f"  [OPTIONAL-MISSING] {repo_path}")
                else:
                    failures.append({"repository_path": repo_path, "error": str(exc)})
                    print(f"  [FAILED] {repo_path}: {exc}", file=sys.stderr)
            except Exception as exc:
                failures.append({"repository_path": repo_path, "error": str(exc)})
                print(f"  [FAILED] {repo_path}: {exc}", file=sys.stderr)

        # Fetch one circuit-section definition for this event when the source mapping has one.
        if event_name in section_mapping:
            section_path = f"sections/{section_mapping[event_name]}.json"
            try:
                record = write_download(commit_sha, section_path, raw_root, args.force)
                # Avoid duplicate records when multiple events share a section file.
                if not any(item["repository_path"] == section_path for item in downloaded):
                    downloaded.append(record)
                print(f"  [{record['status']}] {section_path}")
            except Exception as exc:
                failures.append({"repository_path": section_path, "error": str(exc)})
                print(f"  [FAILED] {section_path}: {exc}", file=sys.stderr)
        else:
            print(f"  [WARN] No EVENT_SECTIONS_FILE mapping for {event_name}")

    merged_files = dict(previous_file_records)
    for item in downloaded:
        merged_files[item["repository_path"]] = item
    all_file_records = [merged_files[key] for key in sorted(merged_files)]

    manifest = {
        "project": "Slipstream-Lab",
        "source_repository": f"https://github.com/{OWNER}/{REPO}",
        "source_branch": branch,
        "source_commit": commit_sha,
        "fetched_at_utc": utc_now(),
        "driver_requested": args.driver,
        "event_filter": args.event,
        "raw_root": "data/raw/tracinginsights_2026",
        "section_mapping": mapping_record,
        "reference_files": reference_records,
        "selected_session_files": sorted(SESSION_FILES),
        "team_radio_audio_downloaded": False,
        "files": all_file_records,
        "failures": failures,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nFetch complete: {len(downloaded)} file records; {len(failures)} failures.")
    print(f"Manifest: {manifest_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        raise SystemExit(2)
