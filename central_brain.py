import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.expanduser('~/northfraim-job77/logs/central_decisions.db')

class CentralBrain:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()

    def log_decision(self, agent_name, template_used, task_description, reasoning, decision, confidence):
        self.cursor.execute('''
            INSERT INTO decisions (agent_name, template_used, task_description, reasoning, decision, confidence, outcome)
            VALUES (?, ?, ?, ?, ?, ?, 'PENDING')
        ''', (agent_name, template_used, task_description, reasoning, decision, confidence))
        self.conn.commit()
        return self.cursor.lastrowid

    def log_outcome(self, decision_id, outcome, actual_time, template_accuracy):
        self.cursor.execute('''
            UPDATE decisions
            SET outcome = ?, actual_time = ?, template_accuracy = ?
            WHERE id = ?
        ''', (outcome, actual_time, template_accuracy, decision_id))
        self.conn.commit()

    def allocate_resources(self):
        # Basic 80/20 logic placeholder for now
        return {"priority": "high", "focus": "hot_leads"}
        
print("central_brain.py loaded successfully.")
