import sqlite3
import os
from datetime import datetime

# Was os.path.expanduser('~/northfraim-job77/logs/central_decisions.db') --
# that directory has never existed on this machine (the real checkout is
# ~/northfraim-job77-full), the same recurring path bug hit twice earlier
# tonight elsewhere in this codebase. Made self-contained within this
# project instead of guessing at another machine's directory layout, so
# it can never depend on a directory this project doesn't own.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'central_decisions.db')

class CentralBrain:
    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
        # No CREATE TABLE existed anywhere in this codebase for `decisions`
        # -- log_decision()/log_outcome() have never actually run
        # end-to-end against a fresh database before. Schema inferred
        # directly from the columns those two methods and
        # form_catcher.py's _render_decisions_page() actually use.
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                agent_name TEXT,
                template_used TEXT,
                task_description TEXT,
                reasoning TEXT,
                decision TEXT,
                confidence REAL,
                outcome TEXT,
                actual_time REAL,
                template_accuracy REAL
            )
        ''')
        self.conn.commit()

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
