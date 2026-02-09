#!/usr/bin/env python3
"""Add test data to dashboard."""
import sys
import time
import random

sys.path.insert(0, str(__file__).replace(r'\add_test_data.py', ''))

from tracker import track_api_call

models = [
    "gemini-architect",
    "deepseek-v3",
    "kimi-synthesis",
    "claude-sonnet",
    "opus-synthesis",
    "gemini-flash"
]

task_types = [
    "quick-verify",
    "security-audit",
    "brainstorm",
    "team-debate",
    "repo-map",
    "refinement"
]

print("Adding test data to dashboard...")

for i in range(20):
    model = random.choice(models)
    task_type = random.choice(task_types)

    prompt_tokens = random.randint(500, 5000)
    completion_tokens = random.randint(200, 3000)
    total_tokens = prompt_tokens + completion_tokens

    duration = random.uniform(1.0, 30.0)

    track_api_call(
        model=model,
        task_type=task_type,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        duration_seconds=duration,
        status="success"
    )

    print(f"  {i+1}. {model:20} | {task_type:15} | {total_tokens:6} tokens")

print("\nFlushing to database...")
from tracker import get_tracker
tracker = get_tracker()
tracker.shutdown()

print("Done!")
