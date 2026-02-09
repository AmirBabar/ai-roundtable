#!/usr/bin/env python3
"""Test SQL query."""
import sqlite3
from datetime import datetime, timedelta

db_path = r"C:\Users\amirk\.claude\dashboard\data\dashboard.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Test with 1h range
seconds = 3600
sql = f"""
    SELECT timestamp, model, task_type, total_tokens, cost_usd
    FROM api_calls
    WHERE datetime(timestamp) >= datetime('now', '-{seconds} seconds')
    ORDER BY timestamp DESC
    LIMIT 10
"""

cursor.execute(sql)
rows = cursor.fetchall()

print(f"=== Records in last 1 hour (3600 seconds) ===")
print(f"Query time (SQLite 'now'): {datetime.now().isoformat()}")
print(f"Records found: {len(rows)}\n")

for r in rows:
    ts = r['timestamp']
    print(f"  {ts} | {r['model']:20} | {r['total_tokens']} tokens")

# Also check raw count
cursor.execute("SELECT COUNT(*) as total FROM api_calls")
total = cursor.fetchone()['total']
print(f"\nTotal records in database: {total}")

conn.close()
