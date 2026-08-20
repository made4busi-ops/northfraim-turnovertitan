#!/usr/bin/env python3
"""
lead_watcher.py -- Turnover Titans
The autonomous piece. Watches the real leads database. Any lead not
yet processed gets a real pitch drafted automatically using
pitch_engine's logic. Drafts land in a pending-approval file - nothing
sends itself, but nothing requires you to remember to type a command
for each new lead either.
"""

import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pitch_engine import load_json_dict, build_pitch


def load_pending(pending_path):
    if not os.path.exists(pending_path):
        return {"pending": [], "processed_lead_ids": []}
    try:
        with open(pending_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"pending": [], "processed_lead_ids": []}
    if not isinstance(data, dict):
        return {"pending": [], "processed_lead_ids": []}
    data.setdefault("pending", [])
    data.setdefault("processed_lead_ids", [])
    return data


def save_pending(pending_path, data):
    directory = os.path.dirname(os.path.abspath(pending_path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = pending_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, pending_path)


def fetch_leads(db_path):
    if not os.path.exists(db_path):
        print("WARNING: leads database not found at " + db_path)
        return []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, business, email, phone FROM leads")
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        print("WARNING: could not read leads database: " + str(e))
        return []
    return [
        {"id": r[0], "name": r[1], "business": r[2], "email": r[3], "phone": r[4]}
        for r in rows
    ]


def run_watch_cycle(db_path, winners_path, losers_path, pending_path):
    winners = load_json_dict(winners_path, "winners")
    losers = load_json_dict(losers_path, "losers")
    pending_data = load_pending(pending_path)

    leads = fetch_leads(db_path)
    new_count = 0

    for lead in leads:
        if lead["id"] in pending_data["processed_lead_ids"]:
            continue

        pitch = build_pitch(winners, losers, lead["name"], lead["business"])
        if pitch is None:
            print("SKIPPED lead " + str(lead["id"]) + " - no data to draft from.")
            continue

        pending_data["pending"].append({
            "lead_id": lead["id"],
            "name": lead["name"],
            "business": lead["business"],
            "email": lead.get("email"),
            "phone": lead.get("phone"),
            "drafted_pitch": pitch,
            "status": "awaiting_approval",
        })
        pending_data["processed_lead_ids"].append(lead["id"])
        new_count += 1
        print("[WATCHER] Drafted pitch for lead " + str(lead["id"]) + " (" + lead["name"] + ", " + lead["business"] + ") - awaiting your approval")

    save_pending(pending_path, pending_data)

    total_pending = len([p for p in pending_data["pending"] if p["status"] == "awaiting_approval"])
    print("")
    print("[WATCHER] Cycle complete. " + str(new_count) + " new draft(s) this run. " + str(total_pending) + " total awaiting approval.")
    return new_count


def main(argv):
    if len(argv) != 5:
        print("Usage: python3 lead_watcher.py <leads_db_path> <winners_path> <losers_path> <pending_path>")
        return 2

    db_path, winners_path, losers_path, pending_path = argv[1], argv[2], argv[3], argv[4]
    run_watch_cycle(db_path, winners_path, losers_path, pending_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
