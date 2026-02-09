---
name: roundtable
description: This skill should be used when the user asks to "run roundtable", "roundtable brainstorm", "roundtable debate", "roundtable build plan", "roundtable review", "team debate", "diamond debate", or mentions multi-agent collaboration, Diamond Architecture, or AI Roundtable workflow. Provides seven specialized AI collaboration modes for different problem types including brainstorming, refinement, build planning, build review, Opus gatekeeping, diamond debate, and team debate.
version: 3.0.0
run: python scripts/skill.py $MODE "$@" 2>&1
timeout: 300000
---

# AI Roundtable - Multi-Model AI Collaboration Platform

**Version:** 3.0.0
**Repository:** https://github.com/yourusername/ai-roundtable
**License:** MIT

A sophisticated multi-agent orchestration system that routes requests to specialized AI workflows based on intent detection. Seven distinct collaboration modes for different problem types.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/ai-roundtable.git
cd ai-roundtable

# Install dependencies (optional - core skill works with Claude Code only)
pip install -r requirements.txt

# Copy to your Claude skills directory
# Windows:
copy SKILL.md %USERPROFILE%\.claude\skills\roundtable\
xcopy /E /I scripts %USERPROFILE%\.claude\skills\roundtable\scripts
xcopy /E /I lib %USERPROFILE%\.claude\skills\roundtable\lib

# macOS/Linux:
cp -r SKILL.md scripts lib ~/.claude/skills/roundtable/
```

## Usage

```bash
# Via Claude Code Skill tool (recommended)
/roundtable brainstorm <prompt>
/roundtable refine <input_text>
/roundtable build-plan <topic>
/roundtable build-review <summary>
/roundtable opus-gatekeeper <query>
/roundtable diamond-debate <topic>
/roundtable team-debate <topic>

# Via Python (direct entry point)
python scripts/skill.py brainstorm "Ways to improve API performance"
python scripts/skill.py diamond-debate "Should we use PostgreSQL or MongoDB?"
```

## Seven Collaboration Modes

| Mode | Purpose | Execution Pattern | Output |
|------|---------|-------------------|--------|
| **Brainstorming** | Generate diverse ideas | Parallel light models → Synthesizer | List of prioritized ideas |
| **Refinement** | Critical review & improvement | Series with quality gates | Refined output with critiques |
| **Build Planning** | Detailed technical specifications | Sequential 4-step workflow | Build plan artifact |
| **Build Reviewer** | Post-build validation | Review against criteria | Pass/Fail verdict with findings |
| **Opus Gatekeeper** | Cost optimization | Category/budget check | INVOKE/SKIP/BUDGET_BLOCK decision |
| **Diamond Debate** | Complex architectural decisions | PARALLEL Diamond Architecture | Comprehensive decision analysis |
| **Team Debate** | Build specifications (alias) | SEQUENTIAL 4-step workflow | Final decree with phases |

## Mode 1: Brainstorming (Parallel Idea Generation)

**Use for:** Generating diverse options, exploring possibilities, creative ideation

**Workflow:**
```
Gemini Flash ─┐
DeepSeek Chat ─┼─→ Claude Sonnet (Synthesizer) → Prioritized Ideas
Claude Haiku ──┘
```

**Example:**
```bash
/roundtable brainstorm "Ways to improve memory context injection in Claude Code"
```

## Mode 6: Diamond Debate (PARALLEL Diamond Architecture)

**Use for:** Complex architectural decisions, cross-domain analysis

**Workflow:**
```
Stage 1 (PARALLEL): kimi + perplexity → context gathering
Stage 2 (PARALLEL): deepseek + gemini-flash + sonnet → deliberation
Stage 3 (SEQUENTIAL): gemini-pro → synthesis
Stage 4 (CONDITIONAL): opus → ratification
```

**Example:**
```bash
/roundtable diamond-debate "Should we use PostgreSQL or MongoDB for this project?"
```

## Mode 7: Team Debate (Sequential 4-Step Workflow)

**Use for:** Creating build specifications, iterative refinement

**Workflow:**
```
Step 1: gemini-architect → proposes solution
Step 2: deepseek-v3 → critiques proposal
Step 3: kimi-researcher → codebase-aware analysis
Step 4: opus-synthesis → final decree
```

**Example:**
```bash
/roundtable team-debate "Design a new authentication system"
```

## Optional Components

The core skill works with Claude Code's native capabilities. For enhanced functionality:

### LiteLLM Gateway (Optional)

Enables multi-model routing:

```bash
# Install LiteLLM
pip install litellm

# Copy example config
cp litellm/config.yaml.example litellm/config.yaml

# Start gateway
litellm --config litellm/config.yaml --port 4000
```

### Dashboard (Optional)

Web UI for monitoring debates and memory:

```bash
cd dashboard
pip install -r requirements.txt
python start_dashboard.py
```

### Memory Subsystem (Optional)

Persistent context across sessions:

```bash
cd memory
python init_db.py
```

## Configuration

Model configurations are in `config/models.yaml` (create from `models.yaml.example`):

```yaml
models:
  brainstorm:
    - gemini-flash
    - deepseek-chat
    - claude-haiku
  build_planning:
    architect: gemini-architect
    auditor: deepseek-v3
    contextualist: kimi-researcher
    judge: opus-synthesis
```

## Documentation

- **`docs/ARCHITECTURE.md`** - Complete system architecture
- **`docs/INSTALLATION.md`** - Detailed installation guide
- **`docs/CONFIGURATION.md`** - Configuration reference
- **`docs/TROUBLESHOOTING.md`** - Common issues and solutions

## Version History

| Version | Date | Changes |
|---------|------|---------|
| **3.0.0** | 2026-02-09 | Public distribution release |
| **2.1.2** | 2026-02-06 | Hallucination Safeguards |
| **2.1.0** | 2026-01-30 | diamond-debate and team-debate modes |
| **2.0.0** | 2026-01-28 | Diamond Architecture v2 |
| **1.0.0** | 2025-01-15 | Initial release |

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please see CONTRIBUTING.md for guidelines.

---

*AI Roundtable - Multi-Model AI Collaboration Platform*
