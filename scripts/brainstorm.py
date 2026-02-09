#!/usr/bin/env python3
"""
brainstorm.py - Mode 1: Parallel brainstorming mode

Runs multiple AI models in parallel to generate diverse ideas,
then synthesizes the results.
"""

import sys
import json
import re
import asyncio
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Bootstrap: Add project root to path for direct script execution
# Per Council: lib/__init__.py bootstrap_module_context pattern
import sys
from pathlib import Path
current_path = Path(__file__).resolve()
root = current_path
for marker in ['pyproject.toml', '.git', 'requirements.txt']:
    while root != root.parent:
        if (root / marker).exists():
            break
        root = root.parent
    if (root / marker).exists():
        break
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
# Add scripts directory for sibling imports
scripts_dir = Path(__file__).parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

# Use absolute imports (relative imports don't work when script run directly)
from gateway import get_gateway, sanitize_output, print_safe
from models import BRAINSTORMING_MODELS
from schemas import IdeaSchema, QualityGate

# Dashboard tracking (optional, gracefully degrades if not available)
try:
    dashboard_path = Path(__file__).parent.parent.parent.parent / "dashboard" / "backend"
    if str(dashboard_path) not in sys.path:
        sys.path.insert(0, str(dashboard_path))
    from council_tracker import track_call, get_session_id, TASK_BRAINSTORM
    TRACKING_AVAILABLE = True
except ImportError:
    TRACKING_AVAILABLE = False


async def brainstorm_parallel(
    prompt: str,
    max_ideas: int = 20,
) -> List[Dict[str, Any]]:
    """
    Run brainstorming in parallel across multiple models.

    Args:
        prompt: The brainstorming prompt
        max_ideas: Maximum ideas to generate per model

    Returns:
        List of idea dictionaries
    """
    gateway = get_gateway()
    models = BRAINSTORMING_MODELS["models"]
    synthesizer = BRAINSTORMING_MODELS["synthesizer"]

    print_safe(f"\n=== Brainstorming: {len(models)} models in parallel ===\n")

    # Create tasks for parallel execution
    async def call_model_task(model_config):
        model = model_config["id"]
        print_safe(f"  -> {model_config['name']}: Generating...")

        system_prompt = f"""You are a brainstorming assistant. Generate {max_ideas} diverse, creative ideas in response to the user's request.

Your task:
- Generate {max_ideas} unique ideas
- Be creative and think outside the box
- Consider different angles and perspectives
- Format as a numbered list

Focus on QUANTITY and DIVERSITY of ideas."""

        # Track start time for dashboard
        call_start = time.time()

        result = gateway.call_model(
            model=model,
            system_prompt=system_prompt,
            user_prompt=prompt,
            timeout=model_config.get("timeout", 60),
        )

        # Track to dashboard if available
        if TRACKING_AVAILABLE:
            duration = time.time() - call_start
            try:
                track_call(
                    model=model,
                    task_type=TASK_BRAINSTORM,
                    response=result,
                    duration_seconds=duration,
                    session_id=get_session_id()
                )
            except Exception:
                pass  # Silently fail to not disrupt brainstorming

        if result["success"]:
            content = result["content"]
            print_safe(f" [{len(content)} chars]")
            return {
                "model": model,
                "content": content,
                "tokens": result["tokens"],
            }
        else:
            print_safe(f" [ERROR: {result['error']}]")
            return None

    # Run all models in parallel
    tasks = [call_model_task(m) for m in models]
    results_raw = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    all_ideas = []
    for i, result in enumerate(results_raw):
        if result is None:
            continue

        model = result["model"]
        content = result["content"]

        # Parse ideas from the content
        ideas = parse_ideas_from_content(content, model)
        all_ideas.extend(ideas)

        print_safe(f"\n  {models[i]['name']}: Generated {len(ideas)} ideas\n")

    # Now synthesize
    print_safe(f"[Synthesizing {len(all_ideas)} ideas from {len(models)} models...]")

    synthesis_prompt = f"""You are a synthesizer. Your task is to organize, categorize, and prioritize the following brainstorming ideas.

TOPIC: {prompt[:500]}

IDEAS FROM MULTIPLE MODELS:
{format_ideas_list(all_ideas[:50])}

Your task:
1. Remove duplicates and very similar ideas
2. Group related ideas into categories
3. Rank by quality and feasibility
4. Return the top {min(max_ideas, len(all_ideas))} ideas

Format your response as a numbered list:
## Category: [category name]
1. [Idea title] - [brief description]
2. ...

Be concise but thorough."""

    # Track synthesis call
    synthesis_start = time.time()

    synthesis_result = gateway.call_model(
        synthesizer["id"],
        system_prompt="You are a synthesizer. Organize, categorize, and prioritize ideas from multiple sources.",
        user_prompt=synthesis_prompt,
        timeout=synthesizer.get("timeout", 90),
    )

    # Track synthesis to dashboard
    if TRACKING_AVAILABLE:
        synthesis_duration = time.time() - synthesis_start
        try:
            track_call(
                model=synthesizer["id"],
                task_type=TASK_BRAINSTORM,
                response=synthesis_result,
                duration_seconds=synthesis_duration,
                session_id=get_session_id()
            )
        except Exception:
            pass  # Silently fail

    if synthesis_result["success"]:
        print_safe(f"\n✓ Synthesis complete ({synthesis_result['tokens']} tokens)")
        return parse_synthesized_ideas(synthesis_result["content"])
    else:
        # Fallback: return raw ideas without synthesis
        print_safe("\n⚠ Synthesis failed, returning raw ideas")
        return all_ideas[:max_ideas]


def parse_ideas_from_content(content: str, model: str) -> List[Dict[str, Any]]:
    """Parse ideas from model output."""
    ideas = []

    # Try JSON format first
    try:
        data = json.loads(content)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    idea = {"title": item.get("title", ""), "description": item.get("description", ""), "source_model": model}
                    valid, _ = IdeaSchema.validate(idea)
                    if valid:
                        ideas.append(idea)
    except json.JSONDecodeError:
        pass

    # Parse as numbered list
    if not ideas:
        lines = content.split("\n")
        current_idea = {}

        for line in lines:
            line = line.strip()

            # Numbered list item
            match = re.match(r'^(\d+)[.\)]\s*(.+)', line)
            if match:
                if current_idea:
                    ideas.append(current_idea)
                current_idea = {"source_model": model, "description": match.group(1)}
            elif line.startswith(('-', "*")):
                if current_idea:
                    ideas.append(current_idea)
                current_idea = {"source_model": model, "description": line.lstrip("-*").strip()}
            elif current_idea:
                # Continuation of description
                current_idea["description"] += " " + line

        if current_idea:
            ideas.append(current_idea)

    return ideas


def parse_synthesized_ideas(content: str) -> List[Dict[str, Any]]:
    """Parse synthesized ideas from synthesizer output."""
    ideas = []

    # Look for numbered list under categories
    current_category = None
    lines = content.split("\n")

    for line in lines:
        line = line.strip()

        # Category header
        if line.startswith("##") or line.startswith("###"):
            current_category = line.lstrip("#").strip()
            continue

        # Numbered item
        match = re.match(r'^(\d+)[.\)]\s*(.+)', line)
        if match:
            title_desc = match.group(2)  # Fixed: group(2) is content, group(1) is number
            parts = title_desc.split(" - ", 1)
            title = parts[0].strip()
            description = parts[1].strip() if len(parts) > 1 else ""

            ideas.append({
                "title": title,
                "description": description,
                "category": current_category or "General",
                "synthesized": True,
            })

    return ideas


def format_ideas_list(ideas: List[Dict[str, Any]]) -> str:
    """Format ideas as a markdown list."""
    if not ideas:
        return "* (no ideas generated)"

    lines = []
    for i, idea in enumerate(ideas, 1):
        category_prefix = f"[{idea.get('category', 'General')}] " if idea.get('category') != "General" else ""
        source = f" ({idea.get('source_model', 'unknown')})" if not idea.get("synthesized") else " (synthesized)"
        lines.append(f"{i}. {category_prefix}{idea.get('title', 'Untitled')}{source} - {idea.get('description', '')[:100]}")

    return "\n".join(lines)


def brainstorm(prompt: str, max_ideas: int = 20) -> Dict[str, Any]:
    """
    Run brainstorming mode.

    Args:
        prompt: Brainstorming prompt
        max_ideas: Maximum ideas per model

    Returns:
        Dictionary with results
    """
    print_safe(f"\n=== Council Brainstorming Mode ===")
    print_safe(f"Prompt: {prompt[:100]}...\n")

    # Run parallel brainstorming
    try:
        ideas = asyncio.run(brainstorm_parallel(prompt, max_ideas))
    except Exception as e:
        return {
            "success": False,
            "error": f"Parallel execution failed: {str(e)[:100]}",
        }

    print_safe(f"\n✓ Generated {len(ideas)} total ideas")

    return {
        "success": True,
        "ideas": ideas,
        "count": len(ideas),
        "error": None,
    }


# For standalone testing
if __name__ == "__main__":
    import io
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    result = brainstorm("Ways to improve memory context injection in Claude Code", max_ideas=15)

    if result["success"]:
        print("\n=== Results ===")
        print(f"Generated {result['count']} ideas:")
        print(format_ideas_list(result["ideas"][:10]))
    else:
        print(f"Error: {result['error']}")
