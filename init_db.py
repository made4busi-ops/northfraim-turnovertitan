import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'leads.db')

os.makedirs(DATA_DIR, exist_ok=True)

def init_ledger():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            business TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Safety net added 2026-09-05 after a real lead (id 1, captured
    # 2026-09-04 18:56:29) was permanently lost to an untracked manual
    # `DELETE FROM leads` with no backup in place. Any future delete --
    # accidental or otherwise -- now gets copied here first, so it's
    # recoverable instead of silently gone.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads_deleted_audit (
            id INTEGER,
            name TEXT,
            business TEXT,
            email TEXT,
            phone TEXT,
            message TEXT,
            created_at TIMESTAMP,
            deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS leads_before_delete
        BEFORE DELETE ON leads
        BEGIN
            INSERT INTO leads_deleted_audit (id, name, business, email, phone, message, created_at)
            VALUES (OLD.id, OLD.name, OLD.business, OLD.email, OLD.phone, OLD.message, OLD.created_at);
        END
    ''')
    conn.commit()
    conn.close()
    print(f"LEDGER INITIALIZED: {DB_PATH}")

if __name__ == "__main__":
    init_ledger()
