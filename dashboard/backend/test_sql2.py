#!/usr/bin/env python3
"""Debug SQL datetime comparison."""
import sqlite3

db_path = r"C:\Users\amirk\.claude\dashboard\data\dashboard.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get the latest record
cursor.execute("SELECT timestamp, datetime(timestamp) as dt, datetime('now') as now FROM api_calls ORDER BY timestamp DESC LIMIT 1")
row = cursor.fetchone()

print("=== Latest record ===")
print(f"Raw timestamp: {row['timestamp']}")
print(f"datetime(timestamp): {row['dt']}")
print(f"datetime('now'): {row['now']}")

# Check if the comparison works
cursor.execute("SELECT datetime(timestamp) >= datetime('now', '-1 hour') as is_recent FROM api_calls ORDER BY timestamp DESC LIMIT 1")
row2 = cursor.fetchone()
print(f"\nIs recent (1 hour): {row2['is_recent']}")

# Check with seconds
cursor.execute("SELECT datetime(timestamp) >= datetime('now', '-3600 seconds') as is_recent FROM api_calls ORDER BY timestamp DESC LIMIT 1")
row3 = cursor.fetchone()
print(f"Is recent (3600 seconds): {row3['is_recent']}")

# Direct timestamp comparison
cursor.execute("SELECT timestamp >= datetime('now', '-3600 seconds') as is_recent FROM api_calls ORDER BY timestamp DESC LIMIT 1")
row4 = cursor.fetchone()
print(f"Is recent (direct timestamp): {row4['is_recent']}")

conn.close()
