#!/usr/bin/env python3
"""
outreach_scheduler.py -- Turnover Titans

The missing piece: takes a real lead already sitting in leads.db,
sends it a REAL outbound email (real SMTP via email_sender.py, reusing
pitch_engine's persuasive copy) that proposes a concrete cleaning-job
date and time slot for the next real calendar day, and -- only on a
real successful send -- writes a real row into scheduled_jobs.json.

Honest by design, same posture as everything else in this codebase:
this does NOT claim a "confirmed" booking. There is no real inbound-
reply-processing anywhere in this business (no IMAP/webhook that reads
a lead's reply and marks it accepted), so a job this writes is always
status "proposed_pending_confirmation" -- a real, concrete proposal
that really went out, not a fabricated confirmed appointment nobody
actually agreed to. If a real confirmation channel is ever built, that
piece would be responsible for flipping the status to "confirmed".

Email is the only real outbound channel here -- there is no telephony/
call capability (no Twilio or similar) anywhere in this codebase, so a
lead with no real email on file cannot actually be reached by this
function; it reports that plainly rather than pretending to place a
call that doesn't exist.

Conflict-aware over a small fixed set of daily slots (no existing
availability/calendar concept exists anywhere else to build on) --
picks the first slot not already proposed/booked for the target date
in scheduled_jobs.json, rather than colliding two leads into the same
slot.
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pitch_engine import load_json_dict, build_pitch
import email_sender

AVAILABLE_SLOTS = ["09:00", "11:00", "13:00", "15:00"]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load(store_path):
    if not os.path.exists(store_path):
        return {"scheduled": {}}
    try:
        with open(store_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"scheduled": {}}
    if not isinstance(data, dict) or not isinstance(data.get("scheduled"), dict):
        return {"scheduled": {}}
    return data


def _save(store_path, data):
    directory = os.path.dirname(os.path.abspath(store_path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = store_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, store_path)


def fetch_lead(db_path, lead_id):
    """Real read of one lead row from the real leads.db -- same table
    agent_53_sniper.py's drop_lead() writes into."""
    if not os.path.exists(db_path):
        print(f"ERROR: leads database not found at {db_path}")
        return None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, name, business, email, phone, message FROM leads WHERE id = ?", (lead_id,)
    ).fetchone()
    conn.close()
    if row is None:
        print(f"ERROR: no lead with id {lead_id} in {db_path}")
        return None
    return dict(row)


def _next_available_slot(store_path, date_str):
    """First fixed daily slot not already proposed/booked for this date
    in scheduled_jobs.json. Returns None if every slot for that date is
    already taken (a real, honest signal to try the next day instead of
    silently double-booking)."""
    data = _load(store_path)
    taken = {
        entry["scheduled_time"]
        for entry in data["scheduled"].values()
        if entry.get("scheduled_date") == date_str and entry.get("status") != "cancelled"
    }
    for slot in AVAILABLE_SLOTS:
        if slot not in taken:
            return slot
    return None


def _build_scheduling_message(lead_name, lead_business, date_str, time_str, winners_path, losers_path):
    """Reuses pitch_engine's real persuasive copy as the body, then
    appends a concrete scheduling proposal -- the part pitch_engine
    itself never had (its generated pitch only ever ended with a vague
    "want a walkthrough?", no real date/time)."""
    winners = load_json_dict(winners_path, "winners") if winners_path else {}
    losers = load_json_dict(losers_path, "losers") if losers_path else {}
    pitch = build_pitch(winners, losers, lead_name, lead_business)
    if pitch is None:
        # No winners/losers data available -- still a real, honest
        # scheduling message, just without the pattern-matched pitch copy.
        pitch = f"Hi {lead_name},\n\nTurnover Titans handles short-term rental turnover cleaning for {lead_business}."

    proposal = (
        f"\n\nI'd like to get {lead_business}'s first turnover cleaned this week. "
        f"I have {date_str} at {time_str} open -- if that works, just reply YES and it's booked. "
        f"If not, reply with a day/time that works better and I'll move it."
    )
    return pitch + proposal


def propose_and_schedule(db_path, store_path, lead_id, winners_path=None, losers_path=None, target_date=None):
    """The real, missing piece: lead -> real outbound message -> real
    scheduled_jobs.json row, only on an actual successful send.

    Returns a dict:
      {"success": bool, "reason": str, ...}
    "success" is only True when a real email was actually sent AND a
    real row was written -- never when either step was skipped or faked.
    """
    lead = fetch_lead(db_path, lead_id)
    if lead is None:
        return {"success": False, "reason": f"No lead with id {lead_id} in {db_path} -- nothing to contact."}

    email = (lead.get("email") or "").strip()
    if not email or "@" not in email:
        return {
            "success": False,
            "reason": (
                f"Lead {lead_id} ({lead['name']}, {lead['business']}) has no real email on file "
                f"(phone: {lead.get('phone') or 'none'}). This codebase has no telephony/call "
                f"capability (no Twilio or similar) -- there is no real way to reach this lead right now."
            ),
        }

    if target_date is None:
        target_date = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()

    slot = _next_available_slot(store_path, target_date)
    if slot is None:
        return {
            "success": False,
            "reason": f"Every available slot for {target_date} is already proposed/booked. Try the next day.",
        }

    message = _build_scheduling_message(lead["name"], lead["business"], target_date, slot, winners_path, losers_path)
    subject = f"Turnover Titans -- {target_date} at {slot} for {lead['business']}?"

    try:
        email_sender.send_email(email, subject, message)
    except email_sender.EmailSendError as e:
        return {"success": False, "reason": f"Real SMTP send failed: {e}"}

    data = _load(store_path)
    entry_id = f"sched-{lead_id}-{target_date}-{slot.replace(':', '')}"
    data["scheduled"][entry_id] = {
        "lead_id": lead_id,
        "name": lead["name"],
        "business": lead["business"],
        "email": email,
        "scheduled_date": target_date,
        "scheduled_time": slot,
        "status": "proposed_pending_confirmation",
        "message_sent": message,
        "sent_at": _now(),
    }
    _save(store_path, data)

    print(f"[SCHEDULER] Real email sent to {email} proposing {target_date} {slot} for {lead['business']}.")
    print(f"[SCHEDULER] Real row written: {entry_id} (status: proposed_pending_confirmation)")
    return {
        "success": True,
        "reason": "Real outbound email sent; real scheduled_jobs.json row written.",
        "entry_id": entry_id,
        "scheduled_date": target_date,
        "scheduled_time": slot,
        "email": email,
    }


def board(store_path):
    data = _load(store_path)
    if not data["scheduled"]:
        print("NO SCHEDULED/PROPOSED JOBS YET.")
        return
    print("=== SCHEDULED JOBS BOARD ===")
    for entry_id, entry in sorted(data["scheduled"].items(), key=lambda kv: (kv[1]["scheduled_date"], kv[1]["scheduled_time"])):
        print(f"  [{entry['status'].upper()}] {entry_id}: {entry['name']} ({entry['business']}) "
              f"-- {entry['scheduled_date']} {entry['scheduled_time']} -- {entry['email']}")


def _usage():
    print("Usage:")
    print("  python3 outreach_scheduler.py <leads_db_path> <scheduled_store_path> propose <lead_id> [winners_path] [losers_path] [target_date YYYY-MM-DD]")
    print("  python3 outreach_scheduler.py <scheduled_store_path> board")


def main(argv):
    if len(argv) == 3 and argv[2] == "board":
        board(argv[1])
        return 0

    if len(argv) < 5 or argv[3] != "propose":
        _usage()
        return 2

    db_path, store_path = argv[1], argv[2]
    rest = argv[4:]

    lead_id = int(rest[0])
    winners_path = rest[1] if len(rest) > 1 else None
    losers_path = rest[2] if len(rest) > 2 else None
    target_date = rest[3] if len(rest) > 3 else None

    result = propose_and_schedule(db_path, store_path, lead_id, winners_path, losers_path, target_date)
    print(json.dumps(result, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
