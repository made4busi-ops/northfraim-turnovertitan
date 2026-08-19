"""
agent_53_sniper.py -- Turnover Titans

Real function only. The old fake Agent53Sniper class (claimed to find
undervalued Airbnb deals, actually returned an empty list) has been
removed - it never scraped or found anything real. What is left is
the ONE real thing this file ever actually did: take a lead someone
hands it, validate it, and drop it into the leads database.

This is a lead-intake function, not a deal-finder.
"""

import os
import sys
import sqlite3

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.agent_54_compliance import validate_lead

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'leads.db')


def drop_lead(lead_data):
    is_valid, msg = validate_lead(lead_data)
    if not is_valid:
        print("SNIPER: Lead rejected by compliance - " + msg)
        return None

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO leads (name, business, email, phone, message)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            lead_data.get('name', ''),
            lead_data.get('business', ''),
            lead_data.get('email', ''),
            lead_data.get('phone', ''),
            lead_data.get('message', '')
        ))
        conn.commit()
        lead_id = cursor.lastrowid
        conn.close()
        print("SNIPER: Lead dropped in Ledger. ID: " + str(lead_id))
        return lead_id
    except Exception as e:
        print("SNIPER: Error dropping lead - " + str(e))
        return None


if __name__ == "__main__":
    test_lead = {
        "name": "Derrick",
        "business": "Turnover Titans",
        "email": "governor@titans.com",
        "phone": "555-0100"
    }
    drop_lead(test_lead)
