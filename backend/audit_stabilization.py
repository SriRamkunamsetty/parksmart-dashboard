import sqlite3
import os

db_path = "parksmart.db"
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found.")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- YOLO Vehicle Counts ---")
cursor.execute("SELECT timestamp, message FROM system_events WHERE message LIKE '[YOLO] vehicles detected:%' ORDER BY id DESC LIMIT 5")
rows = cursor.fetchall()
for row in rows:
    print(f"[{row[0]}] {row[1]}")

print("\n--- Slot State Transitions ---")
cursor.execute("SELECT timestamp, message FROM system_events WHERE event_type='slot_state' ORDER BY id DESC LIMIT 10")
rows = cursor.fetchall()
for row in rows:
    print(f"[{row[0]}] {row[1]}")

print("\n--- Current Slot Status ---")
cursor.execute("SELECT id, number, status FROM parking_slots")
rows = cursor.fetchall()
for row in rows:
    print(f"Slot {row[1]} ({row[0]}): {row[2]}")

conn.close()
