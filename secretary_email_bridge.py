#!/usr/bin/env python3
"""
secretary_email_bridge.py -- Turnover Titans

Connects the real SecretaryAgent brain (northfraim-job77/secretary_agent.py)
to the real turnover-titans@northfraim.com inbox via IMAP. Pulls unread
messages, runs each through handle_communication(), prints the real
triage result, and logs LEAD messages via log_lead().

Credentials come from environment variables -- never hardcoded here:
  IONOS_TT_EMAIL     e.g. turnover-titans@northfraim.com
  IONOS_TT_PASSWORD  the mailbox password
  SILICONFLOW_API_KEY  (optional -- falls back to keyword logic if unset)

IONOS IMAP server: imap.ionos.com, port 993, SSL.
"""

import email
import imaplib
import os
import sys
from email.header import decode_header

sys.path.insert(0, os.path.expanduser("~/northfraim-job77"))
from secretary_agent import SecretaryAgent

IMAP_HOST = "imap.ionos.com"
IMAP_PORT = 993


def _decode(value):
    if value is None:
        return ""
    parts = decode_header(value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            out.append(text.decode(enc or "utf-8", errors="ignore"))
        else:
            out.append(text)
    return "".join(out)


def _get_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                charset = part.get_content_charset() or "utf-8"
                return part.get_payload(decode=True).decode(charset, errors="ignore")
        return ""
    charset = msg.get_content_charset() or "utf-8"
    return msg.get_payload(decode=True).decode(charset, errors="ignore")


def fetch_unread(email_addr, password):
    """Connects to the real inbox, returns a list of (sender, subject, body)
    for every unread message. Does not mark anything as read."""
    messages = []
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    conn.login(email_addr, password)
    conn.select("INBOX")

    status, data = conn.search(None, "UNSEEN")
    if status != "OK":
        conn.logout()
        return messages

    ids = data[0].split()
    for msg_id in ids:
        status, msg_data = conn.fetch(msg_id, "(BODY.PEEK[])")
        if status != "OK":
            continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        sender = _decode(msg.get("From"))
        subject = _decode(msg.get("Subject"))
        body = _get_body(msg)
        messages.append((sender, subject, body))

    conn.logout()
    return messages


def run_bridge(company_name="Turnover Titans", owner_name="Derrick"):
    email_addr = os.environ.get("IONOS_TT_EMAIL")
    password = os.environ.get("IONOS_TT_PASSWORD")
    api_key = os.environ.get("SILICONFLOW_API_KEY")

    if not email_addr or not password:
        print("ERROR: IONOS_TT_EMAIL and IONOS_TT_PASSWORD must be set in the environment.")
        return 1

    secretary = SecretaryAgent(api_key=api_key, company_name=company_name, owner_name=owner_name)

    print("[BRIDGE] Connecting to " + email_addr + " ...")
    try:
        messages = fetch_unread(email_addr, password)
    except imaplib.IMAP4.error as e:
        print("ERROR: IMAP login/connection failed - " + str(e))
        return 1

    print("[BRIDGE] " + str(len(messages)) + " unread message(s) found.\n")

    for sender, subject, body in messages:
        print("--- From: " + sender + " | Subject: " + subject + " ---")
        result = secretary.handle_communication(body, sender)
        print("  Category: " + str(result["category"]))
        print("  Note: " + result["note"])
        if result["draft_reply"]:
            print("  Draft reply:\n    " + result["draft_reply"].replace("\n", "\n    "))
        if result["needs_human_review"]:
            print("  ** FLAGGED FOR " + owner_name.upper() + " -- DO NOT AUTO-REPLY **")
        if result["category"] == "LEAD":
            secretary.log_lead(sender, sender, "email")
        print("")

    if secretary.attention_queue:
        print("=== ATTENTION QUEUE (" + str(len(secretary.attention_queue)) + ") ===")
        for flag in secretary.attention_queue:
            print("  [" + flag["urgency"] + "] " + flag["item"] + " -- " + flag["reason"])

    return 0


if __name__ == "__main__":
    sys.exit(run_bridge())
