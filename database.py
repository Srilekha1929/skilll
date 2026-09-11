import sqlite3

DATABASE = "skilling.db"

conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS trainees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    district TEXT,
    education TEXT,
    course TEXT,
    provider TEXT,
    attendance REAL,
    assessment REAL,
    certification TEXT,
    status TEXT DEFAULT 'Training Completed',
    created_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trainee_id INTEGER,
    outcome_type TEXT,
    employer TEXT,
    job_role TEXT,
    salary REAL,
    location TEXT,
    joining_date TEXT,
    retention_months INTEGER,
    training_relevance INTEGER,
    verified TEXT DEFAULT 'Pending',
    FOREIGN KEY (trainee_id) REFERENCES trainees(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS followups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trainee_id INTEGER,
    followup_period TEXT,
    employment_status TEXT,
    salary REAL,
    job_role TEXT,
    difficulties TEXT,
    remarks TEXT,
    followup_date TEXT,
    FOREIGN KEY (trainee_id) REFERENCES trainees(id)
)
""")

conn.commit()
conn.close()

print("skilling.db created successfully!")