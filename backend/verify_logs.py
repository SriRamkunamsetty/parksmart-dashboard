import sqlite3
import os

db_path = "parksmart.db"
if not os.path.exists(db_path):
    print(f"Database not found: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check for specific logs
patterns = [
    "[STARTUP] default video source",
    "[WORKER] using video source",
    "[WORKER] video capture initialized",
    "[WORKER] stream connected"
]

for p in patterns:
    cursor.execute("SELECT event_type, message FROM system_events WHERE message LIKE ? ORDER BY id DESC LIMIT 5", (f"%{p}%",))
    rows = cursor.fetchall()
    for row in rows:
        print(f"[{row[0]}] {row[1]}")

conn.close()
