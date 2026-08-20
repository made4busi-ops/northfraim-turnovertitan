#!/usr/bin/env python3
"""
foreman.py — Turnover Titans

Answers exactly what Derrick asked: does the machine know how long
something is SUPPOSED to take, and does it know when something's gone
over? Tracks real job start times against expected durations. Anything
over time gets flagged and routed to "needs_attention" - never silently
sits there.

Usage:
    python3 foreman.py <store_path> start <job_id> <job_type> <business_name>
    python3 foreman.py <store_path> finish <job_id>
    python3 foreman.py <store_path> check
"""

import json
import os
import sys
from datetime import datetime, timezone

# Expected durations, in minutes, per job type. Real-world numbers based
# on actual turnover cleaning windows - not guessed randomly.
EXPECTED_MINUTES = {
    "standard_turnover": 90,
    "deep_clean": 180,
    "pitch_followup": 1440,   # 24 hours to follow up on a sent pitch
    "damage_report": 30,
}


def _now():
    return datetime.now(timezone.utc)


def _load(store_path):
    if not os.path.exists(store_path):
        return {"jobs": {}}
    try:
        with open(store_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"WARNING: could not read {store_path}: {e}. Treating as empty.")
        return {"jobs": {}}
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), dict):
        return {"jobs": {}}
    return data


def _save(store_path, data):
    directory = os.path.dirname(os.path.abspath(store_path))
    os.makedirs(directory, exist_ok=True)
    tmp = store_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, store_path)


def start_job(store_path, job_id, job_type, business_name):
    if job_type not in EXPECTED_MINUTES:
        print(f"WARNING: unknown job_type '{job_type}'. Known types: {list(EXPECTED_MINUTES.keys())}")
        return False
    data = _load(store_path)
    if job_id in data["jobs"]:
        print(f"WARNING: job '{job_id}' already exists. Not overwritten.")
        return False
    data["jobs"][job_id] = {
        "job_type": job_type,
        "business_name": business_name,
        "started_at": _now().isoformat(),
        "expected_minutes": EXPECTED_MINUTES[job_type],
        "finished_at": None,
    }
    _save(store_path, data)
    print(f"[FOREMAN] Started '{job_id}' ({job_type}) for {business_name} — expected {EXPECTED_MINUTES[job_type]} min")
    return True


def finish_job(store_path, job_id):
    data = _load(store_path)
    job = data["jobs"].get(job_id)
    if job is None:
        print(f"WARNING: job '{job_id}' does not exist.")
        return False
    job["finished_at"] = _now().isoformat()
    _save(store_path, data)
    started = datetime.fromisoformat(job["started_at"])
    finished = datetime.fromisoformat(job["finished_at"])
    actual_minutes = (finished - started).total_seconds() / 60
    over = actual_minutes > job["expected_minutes"]
    print(f"[FOREMAN] Finished '{job_id}' — took {actual_minutes:.1f} min (expected {job['expected_minutes']})")
    print(f"[FOREMAN] {'OVER TIME - flag this' if over else 'ON TIME'}")
    return True


def check_jobs(store_path):
    """Reports every job still running, and flags any that's gone over its expected time."""
    data = _load(store_path)
    now = _now()
    on_time = []
    overdue = []

    for job_id, job in data["jobs"].items():
        if "job_type" not in job or "expected_minutes" not in job:
            continue  # not a foreman-tracked job (job_queue.py's schema shares this file)
        if job["finished_at"] is not None:
            continue  # already done
        started = datetime.fromisoformat(job["started_at"])
        elapsed_minutes = (now - started).total_seconds() / 60
        if elapsed_minutes > job["expected_minutes"]:
            overdue.append((job_id, job, elapsed_minutes))
        else:
            on_time.append((job_id, job, elapsed_minutes))

    print("=== FOREMAN CHECK ===")
    print(f"\nON TIME ({len(on_time)}):")
    if not on_time:
        print("  (none currently running)")
    for job_id, job, elapsed in on_time:
        print(f"  - {job_id} ({job['business_name']}): {elapsed:.1f}/{job['expected_minutes']} min")

    print(f"\nNEEDS ATTENTION — OVER TIME ({len(overdue)}):")
    if not overdue:
        print("  (none)")
    for job_id, job, elapsed in overdue:
        print(f"  - {job_id} ({job['business_name']}): {elapsed:.1f}/{job['expected_minutes']} min — SOMETHING HAPPENED, ROUTE TO REVIEW")

    return len(overdue)


def _usage():
    print("Usage:")
    print("  python3 foreman.py <store_path> start <job_id> <job_type> <business_name>")
    print("  python3 foreman.py <store_path> finish <job_id>")
    print("  python3 foreman.py <store_path> check")
    print(f"  Job types: {list(EXPECTED_MINUTES.keys())}")


def main(argv):
    if len(argv) < 3:
        _usage()
        return 2

    store_path, command = argv[1], argv[2]
    rest = argv[3:]

    if command == "start":
        if len(rest) != 3:
            _usage()
            return 2
        ok = start_job(store_path, rest[0], rest[1], rest[2])
        return 0 if ok else 1

    if command == "finish":
        if len(rest) != 1:
            _usage()
            return 2
        ok = finish_job(store_path, rest[0])
        return 0 if ok else 1

    if command == "check":
        overdue_count = check_jobs(store_path)
        return 0 if overdue_count == 0 else 1

    print(f"Unknown command '{command}'.")
    _usage()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
