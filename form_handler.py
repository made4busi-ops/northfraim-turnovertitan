#!/usr/bin/env python3
"""
form_handler.py -- Turnover Titans

Real server that catches the landing page's /submit form POST and
drops the lead into the real leads.db (same database lead_watcher.py
and pitch_engine.py already read from). This is the missing piece --
the landing page form pointed at /submit with nothing listening.

Runs a plain http.server -- no new dependency, matches the "one boss
one worker" / supervisor pattern already used by Commercial Genie's
form_handler.py.
"""

import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "leads.db")


def _init_db_if_needed(db_path):
    directory = os.path.dirname(db_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            business TEXT,
            email TEXT,
            phone TEXT
        )
    """)
    conn.commit()
    conn.close()


def insert_lead(db_path, name, business, email, phone):
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "INSERT INTO leads (name, business, email, phone) VALUES (?, ?, ?, ?)",
        (name, business, email, phone),
    )
    conn.commit()
    lead_id = cur.lastrowid
    conn.close()
    return lead_id


class SubmitHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/submit":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        fields = parse_qs(body)

        name = fields.get("name", [""])[0].strip()
        business = fields.get("business", [""])[0].strip()
        email = fields.get("email", [""])[0].strip()
        phone = fields.get("phone", [""])[0].strip()

        if not name:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "name is required"}).encode())
            return

        lead_id = insert_lead(DB_PATH, name, business, email, phone)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "SUCCESS", "lead_id": lead_id}).encode())
        print("[FORM] New lead #" + str(lead_id) + ": " + name + " (" + business + ")")

    def log_message(self, format, *args):
        pass


def run(port=8090):
    _init_db_if_needed(DB_PATH)
    server = HTTPServer(("0.0.0.0", port), SubmitHandler)
    print("[FORM HANDLER] Listening on port " + str(port) + ", writing to " + DB_PATH)
    server.serve_forever()


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    run(port)
