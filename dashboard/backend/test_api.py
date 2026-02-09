#!/usr/bin/env python3
"""Test dashboard API."""
import requests
import json

TOKEN = "064dbe76-7476-4e1b-a31d-57f7b0e8d618"
URL = "http://127.0.0.1:8080/api/metrics"

params = {"token": TOKEN, "range": "1h"}
response = requests.get(URL, params=params)

if response.status_code == 200:
    data = response.json()
    print(f"Total records: {len(data)}")
    print("\nRecent records:")
    for r in data[:8]:
        print(f"  {r['model']:20} | {r['task_type']:15} | {r['total_tokens']:6} tokens | ${r['cost_usd']:.6f}")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
