import os
import sys
import sqlite3

# Add parent dir to path to import agent_54
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.agent_54_compliance import validate_lead

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'leads.db')

def drop_lead(lead_data):
    is_valid, msg = validate_lead(lead_data)
    if not is_valid:
        print(f"SNIPER: Lead rejected by compliance - {msg}")
        return None

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO leads (name, business, email, phone)
            VALUES (?, ?, ?, ?)
        ''', (
            lead_data.get('name', ''),
            lead_data.get('business', ''),
            lead_data.get('email', ''),
            lead_data.get('phone', '')
        ))
        conn.commit()
        lead_id = cursor.lastrowid
        conn.close()
        print(f"SNIPER: Lead dropped in Ledger. ID: {lead_id}")
        return lead_id
    except Exception as e:
        print(f"SNIPER: Error dropping lead - {e}")
        return None

if __name__ == "__main__":
    test_lead = {
        "name": "Derrick",
        "business": "Turnover Titans",
        "email": "governor@titans.com",
        "phone": "555-0100"
    }
    drop_lead(test_lead)
