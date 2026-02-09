#!/usr/bin/env python3
"""Test SSE endpoint by simulating a client connection"""

import sys
import time
import urllib.request
import json
from urllib.parse import urlencode

# Get auth token
token_path = "../data/.auth-token"
try:
    with open(token_path, "r") as f:
        TOKEN = f.read().strip()
except:
    print("[ERROR] No auth token found. Start dashboard server first.")
    sys.exit(1)

print("=== SSE Endpoint Test ===")
print(f"Token: {TOKEN[:8]}...")
print()

# Build SSE URL
base_url = "http://127.0.0.1:8080"
params = {"token": TOKEN}
url = f"{base_url}/api/events?{urlencode(params)}"

print(f"Connecting to: {base_url}/api/events")
print()

try:
    # Create request with streaming
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache"
        }
    )

    # Open connection (5 second timeout for initial response)
    with urllib.request.urlopen(req, timeout=5) as response:
        print(f"Connected! Status: {response.status}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        print()
        print("Receiving events (5 second timeout)...")
        print("-" * 50)

        # Read events
        start_time = time.time()
        events_received = 0

        while time.time() - start_time < 5:
            try:
                # Read a line
                line = response.readline().decode('utf-8').strip()

                if line:
                    if line.startswith("event:"):
                        event_type = line.split(":", 1)[1].strip()
                    elif line.startswith("data:"):
                        data = line.split(":", 1)[1].strip()
                        try:
                            event_data = json.loads(data)
                            print(f"[{event_type}] {event_data.get('type', 'unknown')}")
                            events_received += 1
                        except:
                            print(f"[{data}]")
                    elif line == ":keepalive":
                        print("[keepalive]")
                    else:
                        print(f"[{line}]")
            except TimeoutError:
                break
            except Exception as e:
                print(f"[ERROR] {e}")
                break

        print("-" * 50)
        print(f"Total events received: {events_received}")
        print("[SUCCESS] SSE endpoint working!")

except urllib.error.HTTPError as e:
    print(f"[HTTP ERROR] {e.code} - {e.reason}")
    print("Make sure the dashboard server is running on port 8080")
except Exception as e:
    print(f"[ERROR] {e}")
