#!/usr/bin/env python3
"""
job_queue.py — Turnover Titans

Real job system built directly from the uploaded SOP documents.
Pending -> Cleaning -> Completed. Real checklist. Real inspection
gate. Pay only triggers on a passed inspection - coded, not just
promised in pitch copy.
"""

import json
import os
import sys
from datetime import datetime, timezone

CHECKLIST_ITEMS = [
    "pre_check_walkthrough_damage_scan",
    "bedroom_strip_replace_wipe_vacuum",
    "bathroom_scrub_mop",
    "kitchen_sanitize_trash",
    "living_areas_wipe_vacuum_reset",
    "restock_essentials",
    "final_reset_lock_up",
]

INSPECTION_ITEMS = ["beds", "bathroom", "kitchen", "floors", "final_reset"]


def _now():
    return datetime.now(timezone.utc).isoformat()


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
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = store_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, store_path)


def create_job(store_path, job_id, property_name):
    data = _load(store_path)
    if job_id in data["jobs"]:
        print(f"WARNING: job '{job_id}' already exists. Not overwritten.")
        return False
    data["jobs"][job_id] = {
        "property_name": property_name,
        "state": "Pending",
        "checklist": {item: False for item in CHECKLIST_ITEMS},
        "inspection": {"result": None, "notes": None, "inspected_at": None},
        "pay_status": "unpaid",
        "created_at": _now(),
        "started_at": None,
        "completed_at": None,
    }
    _save(store_path, data)
    print(f"[QUEUE] Created '{job_id}' for {property_name} — state: Pending")
    return True


def start_job(store_path, job_id):
    data = _load(store_path)
    job = data["jobs"].get(job_id)
    if job is None:
        print(f"WARNING: job '{job_id}' does not exist.")
        return False
    if job["state"] != "Pending":
        print(f"WARNING: job '{job_id}' is '{job['state']}', not Pending. Cannot start.")
        return False
    job["state"] = "Cleaning"
    job["started_at"] = _now()
    _save(store_path, data)
    print(f"[QUEUE] '{job_id}' moved: Pending -> Cleaning")
    return True


def check_item(store_path, job_id, item_key):
    data = _load(store_path)
    job = data["jobs"].get(job_id)
    if job is None:
        print(f"WARNING: job '{job_id}' does not exist.")
        return False
    if job["state"] != "Cleaning":
        print(f"WARNING: job '{job_id}' is '{job['state']}', must be Cleaning to check items.")
        return False
    if item_key not in CHECKLIST_ITEMS:
        print(f"WARNING: '{item_key}' is not a real checklist item. Valid items: {CHECKLIST_ITEMS}")
        return False

    idx = CHECKLIST_ITEMS.index(item_key)
    for earlier_item in CHECKLIST_ITEMS[:idx]:
        if not job["checklist"][earlier_item]:
            print(f"REJECTED: '{earlier_item}' must be checked before '{item_key}'. No skipped steps.")
            return False

    job["checklist"][item_key] = True
    _save(store_path, data)
    print(f"[QUEUE] '{job_id}': checked off '{item_key}'")

    if all(job["checklist"].values()):
        print(f"[QUEUE] '{job_id}': ALL checklist items complete. Ready for inspection.")
    return True


def inspect_job(store_path, job_id, result, notes=""):
    data = _load(store_path)
    job = data["jobs"].get(job_id)
    if job is None:
        print(f"WARNING: job '{job_id}' does not exist.")
        return False
    if job["state"] != "Cleaning":
        print(f"WARNING: job '{job_id}' is '{job['state']}', must be Cleaning to inspect.")
        return False
    if not all(job["checklist"].values()):
        missing = [k for k, v in job["checklist"].items() if not v]
        print(f"REJECTED: checklist incomplete, cannot inspect. Missing: {missing}")
        return False
    if result not in ("pass", "fail"):
        print("WARNING: result must be 'pass' or 'fail'.")
        return False

    job["inspection"] = {"result": result, "notes": notes, "inspected_at": _now()}

    if result == "pass":
        job["state"] = "Completed"
        job["completed_at"] = _now()
        job["pay_status"] = "approved_for_payment"
        print(f"[QUEUE] '{job_id}': INSPECTION PASS — job Completed, payment approved.")
    else:
        job["pay_status"] = "not_paid_failed_inspection"
        print(f"[QUEUE] '{job_id}': INSPECTION FAIL — documented, NOT paid, NOT marked Completed.")
        if notes:
            print(f"  Notes: {notes}")

    _save(store_path, data)
    return True


def board(store_path):
    data = _load(store_path)
    states = {"Pending": [], "Cleaning": [], "Completed": []}
    for job_id, job in data["jobs"].items():
        if "state" not in job or "property_name" not in job:
            continue  # not a job_queue-tracked job (foreman.py's schema shares this file)
        if job["state"] in states:
            states[job["state"]].append((job_id, job))

    print("=== JOB BOARD ===")
    for state in ["Pending", "Cleaning", "Completed"]:
        print(f"\n[{state.upper()}] ({len(states[state])})")
        if not states[state]:
            print("  (none)")
        for job_id, job in states[state]:
            pay = job.get("pay_status", "unpaid")
            print(f"  - {job_id} ({job['property_name']}) — pay: {pay}")


def _usage():
    print("Usage:")
    print("  python3 job_queue.py <store_path> create <job_id> <property_name>")
    print("  python3 job_queue.py <store_path> start <job_id>")
    print("  python3 job_queue.py <store_path> check-item <job_id> <item_key>")
    print(f"  Valid items in order: {CHECKLIST_ITEMS}")
    print("  python3 job_queue.py <store_path> inspect <job_id> <pass|fail> [notes]")
    print("  python3 job_queue.py <store_path> board")


def main(argv):
    if len(argv) < 3:
        _usage()
        return 2

    store_path, command = argv[1], argv[2]
    rest = argv[3:]

    if command == "create":
        if len(rest) != 2:
            _usage()
            return 2
        return 0 if create_job(store_path, rest[0], rest[1]) else 1

    if command == "start":
        if len(rest) != 1:
            _usage()
            return 2
        return 0 if start_job(store_path, rest[0]) else 1

    if command == "check-item":
        if len(rest) != 2:
            _usage()
            return 2
        return 0 if check_item(store_path, rest[0], rest[1]) else 1

    if command == "inspect":
        if len(rest) not in (2, 3):
            _usage()
            return 2
        notes = rest[2] if len(rest) == 3 else ""
        return 0 if inspect_job(store_path, rest[0], rest[1], notes) else 1

    if command == "board":
        board(store_path)
        return 0

    print(f"Unknown command '{command}'.")
    _usage()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
