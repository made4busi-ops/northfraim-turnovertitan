import sqlite3
import os
import sys
import json
import logging

# Add agents dir to path to find agent_54
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from agent_54_compliance import check_compliance

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(BASE_DIR, "logs", "titans.log")

logging.basicConfig(filename=LOG_PATH, level=logging.INFO, 
                    format='%asctime%s - %levelname - %message')

def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        print("ERROR: config.json not found.")
        exit(1)

config = load_config()
DB_PATH = os.path.join(BASE_DIR, config.get("db_path", "data/leads.db"))

def drop_lead(lead_data):
    # 1. Check compliance first
    passed, reason = check_compliance(lead_data)
    if not passed:
        logging.error(f"Lead rejected: {"reason}")
        return None
    
    # 2. Insert into DB
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO leads (name, business, platform, details) VALUES (?, ?, ?, ?)",
                  (lead_data.get('name'), lead_data.get('business'), lead_data.get('platform', 'Unknown'), lead_data.get('details', '')))
        conn.commit()
        lead_id = c.lastrowid
        conn.close()
        logging.info(f"Lead dropped in Ledger. ID: {lead_id}")
        return lead_id
    except Exception as e:
        logging.error(f"Database error: {e}")
        return None

if __name__ == "__main__":
    test_lead = {"name": "Test Host", "business": "Airbnb Rental", "platform": "Airbnb", "details": "Found by Sniper"}
    lead_id = drop_lead(test_lead)
    if lead_id:
        print(f"SNIPER: Lead dropped in Ledger. ID: {lead_id}")
    else:
        print("SNIPER: Failed to drop lead.")
