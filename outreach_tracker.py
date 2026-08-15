#!/usr/bin/env python3
"""
outreach_tracker.py -- Turnover Titans

The piece that finally uses acquisition.json. Turns each real channel
into a trackable action: started or not, done or not, with a real
outcome logged.
"""

import json
import os
import sys
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).isoformat()


def load_json_dict(path, label):
    if not os.path.exists(path):
        print("WARNING: " + label + " not found at " + path)
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print("WARNING: could not read " + label + ": " + str(e))
        return {}
    return data if isinstance(data, dict) else {}


def load_status(status_path):
    if not os.path.exists(status_path):
        return {"channels": {}}
    try:
        with open(status_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"channels": {}}
    if not isinstance(data, dict) or not isinstance(data.get("channels"), dict):
        return {"channels": {}}
    return data


def save_status(status_path, data):
    directory = os.path.dirname(os.path.abspath(status_path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = status_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, status_path)


def init_tracker(acquisition_path, status_path):
    acquisition = load_json_dict(acquisition_path, "acquisition data")
    if not acquisition:
        print("NO CHANNELS TO TRACK - acquisition.json empty or missing.")
        return False

    status = load_status(status_path)
    added = 0
    for key, entry in acquisition.items():
        if key in status["channels"]:
            continue
        status["channels"][key] = {
            "name": entry.get("name", key),
            "action_for_titans": entry.get("action_for_titans", ""),
            "status": "not_started",
            "started_at": None,
            "completed_at": None,
            "outcome_notes": None,
        }
        added += 1

    save_status(status_path, status)
    print("[TRACKER] Initialized " + str(added) + " real channel(s) from acquisition data.")
    return True


def start_channel(status_path, channel_key):
    status = load_status(status_path)
    channel = status["channels"].get(channel_key)
    if channel is None:
        print("WARNING: '" + channel_key + "' not found. Run init first.")
        return False
    channel["status"] = "in_progress"
    channel["started_at"] = _now()
    save_status(status_path, status)
    print("[TRACKER] '" + channel_key + "' -> in_progress")
    return True


def complete_channel(status_path, channel_key, outcome_notes):
    status = load_status(status_path)
    channel = status["channels"].get(channel_key)
    if channel is None:
        print("WARNING: '" + channel_key + "' not found. Run init first.")
        return False
    channel["status"] = "done"
    channel["completed_at"] = _now()
    channel["outcome_notes"] = outcome_notes
    save_status(status_path, status)
    print("[TRACKER] '" + channel_key + "' -> done. Outcome: " + outcome_notes)
    return True


def board(status_path):
    status = load_status(status_path)
    if not status["channels"]:
        print("NO CHANNELS TRACKED YET - run init first.")
        return
    print("=== OUTREACH CHANNEL BOARD ===")
    for key, channel in status["channels"].items():
        print("")
        print("[" + channel["status"].upper() + "] " + channel["name"] + " (" + key + ")")
        print("  Action: " + channel["action_for_titans"])
        if channel["outcome_notes"]:
            print("  Outcome: " + channel["outcome_notes"])


def _usage():
    print("Usage:")
    print("  python3 outreach_tracker.py <acquisition_path> <status_path> init")
    print("  python3 outreach_tracker.py <acquisition_path> <status_path> start <channel_key>")
    print("  python3 outreach_tracker.py <acquisition_path> <status_path> complete <channel_key> <outcome_notes>")
    print("  python3 outreach_tracker.py <acquisition_path> <status_path> board")


def main(argv):
    if len(argv) < 4:
        _usage()
        return 2

    acquisition_path, status_path, command = argv[1], argv[2], argv[3]
    rest = argv[4:]

    if command == "init":
        return 0 if init_tracker(acquisition_path, status_path) else 1

    if command == "start":
        if len(rest) != 1:
            _usage()
            return 2
        return 0 if start_channel(status_path, rest[0]) else 1

    if command == "complete":
        if len(rest) < 2:
            _usage()
            return 2
        notes = " ".join(rest[1:])
        return 0 if complete_channel(status_path, rest[0], notes) else 1

    if command == "board":
        board(status_path)
        return 0

    print("Unknown command '" + command + "'.")
    _usage()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
