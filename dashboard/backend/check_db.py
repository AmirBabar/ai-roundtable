#!/usr/bin/env python3
"""Quick check of dashboard database."""
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / "data" / "dashboard.db"
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute('SELECT * FROM api_calls ORDER BY timestamp DESC LIMIT 10')
rows = cursor.fetchall()

print("=== Recent Dashboard Records ===\n")
for r in rows:
    print(f"{r['timestamp'][:19]} | {r['model']:20} | {r['task_type']:15} | {r['total_tokens']:6} tokens | ${r['cost_usd']:6f} | {r['status']}")

conn.close()
