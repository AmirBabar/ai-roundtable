# AI Roundtable Architecture

**Version:** 3.0.0
**Last Updated:** 2026-02-09

---

## Executive Summary

AI Roundtable is a **minimalist, self-contained skill** for Claude Code that provides seven specialized AI collaboration modes. The architecture follows a **core + optional** pattern where the core functionality works entirely with Claude Code's native capabilities, while enhanced features are available through optional components.

---

## Design Principles

### 1. Minimalist Core

The core skill requires **ZERO external dependencies**. All seven collaboration modes work with Claude Code's built-in model access.

### 2. Optional Enhancement

Features like multi-model routing, persistent memory, and web dashboard are **optional** add-ons that users can choose to install.

### 3. Graceful Degradation

The skill detects when optional components are unavailable and falls back to simpler behavior without errors.

### 4. Security by Default

All operations are confined to the repository directory. No auto-execution, no telemetry, no external network access unless explicitly configured.

---

## Component Triage

### Core Components (Required)

These components form the minimum viable skill:

| Component | Location | Purpose | Dependencies |
|-----------|----------|---------|--------------|
| **SKILL.md** | `/` | Skill entry point for Claude Code | None |
| **scripts/skill.py** | `scripts/` | Main router for all 7 modes | None |
| **scripts/brainstorm.py** | `scripts/` | Parallel idea generation | None |
| **scripts/refine.py** | `scripts/` | Sequential refinement | None |
| **scripts/build_planner.py** | `scripts/` | Build specification generation | None |
| **scripts/build_reviewer.py** | `scripts/` | Post-build validation | None |
| **scripts/opus_gatekeeper.py** | `scripts/` | Cost optimization | None |
| **scripts/parallel_executor.py** | `scripts/` | Diamond debate workflows | None |
| **lib/paths.py** | `lib/` | Path resolution | None |
| **lib/schemas.py** | `lib/` | Data structures | None |

**Total Dependencies:** 0 (uses Claude Code native APIs only)

### Optional Components (Enhanced Features)

These components provide additional functionality but are **not required** for basic operation:

| Component | Location | Purpose | Dependencies |
|-----------|----------|---------|--------------|
| **LiteLLM Gateway** | `litellm/` | Multi-model routing | `litellm` package |
| **Dashboard** | `dashboard/` | Web UI for monitoring | Flask, sqlite3 |
| **Memory Subsystem** | `memory/` | Cross-session persistence | sqlite3 (stdlib) |

**Distribution Policy:** Optional components are **documented**, not bundled. Users install them separately if needed.

---

## Distribution Boundary

### What's IN the Repository

```
ai-roundtable/
├── SKILL.md                  # Core skill definition
├── scripts/                  # All 7 mode implementations
├── lib/                      # Utility modules (no external deps)
├── docs/                     # Documentation
├── config/                   # Configuration examples
├── examples/                 # Sample usage
├── hooks/examples/           # Hook examples (opt-in only)
└── skill_manifest.yaml       # Permissions and metadata
```

### What's OUT (External/Documented)

These components are **documented but not bundled**:

| Component | Distribution Method | Documentation |
|-----------|---------------------|---------------|
| LiteLLM | User installs: `pip install litellm` | `docs/INSTALLATION.md#litellm` |
| Model API Keys | User configures in `litellm/config.yaml` | `docs/CONFIGURATION.md#models` |
| Virtual Environment | User creates: `python -m venv .venv` | `docs/INSTALLATION.md#venv` |

**Rationale:** Keeping external dependencies out of the repository:
- Reduces security surface area
- Simplifies installation for basic users
- Allows users to choose their enhancement level
- Avoids version conflicts with user's environment

---

## Mode Architecture

### The Seven Modes

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI Roundtable Modes                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PARALLEL MODES (Fast, Diverse Perspectives)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Brainstorming │  │Diamond Debate │  │              │          │
│  │ 3 models →    │  │4-stage →      │  │  (future)    │          │
│  │ Synthesizer   │  │Final Verdict  │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
│  SEQUENTIAL MODES (Thorough, Step-by-Step)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Refinement    │  │Build Planning │  │Team Debate   │          │
│  │ 3-stage →     │  │4-stage →      │  │4-stage →     │          │
│  │ Quality Gates │  │Build Artifact │  │Final Decree  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
│  VALIDATION MODES (Review and Optimization)                     │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │Build Reviewer │  │Opus Gatekeeper│                           │
│  │Check criteria │  │Cost decision   │                           │
│  └──────────────┘  └──────────────┘                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Mode Decision Tree

```
User Request
     │
     ├── "ideas", "brainstorm", "list possible"
     │   └─→ Brainstorming (Parallel, 60s)
     │
     ├── "review", "improve", "refine"
     │   └─→ Refinement (Sequential, quality gates)
     │
     ├── "build", "implement", "create spec"
     │   └─→ Build Planning (4-step sequential)
     │
     ├── "validate", "check", "verify build"
     │   └─→ Build Reviewer (Criteria-based)
     │
     ├── "should I use Opus", "cost check"
     │   └─→ Opus Gatekeeper (Category-based)
     │
     ├── "should we use X or Y", "explore options"
     │   └─→ Diamond Debate (4-stage parallel)
     │       │
     │       ├── LiteLLM available → Full multi-model
     │       └── No LiteLLM → Fallback to Claude native
     │
     └── "design system", "create specification"
         └─→ Team Debate (4-step sequential)
             │
             ├── LiteLLM available → Full multi-model
             └── No LiteLLM → Fallback to Claude native
```

---

## Data Flow

### Core Skill Flow (No Optional Components)

```
┌─────────────┐
│ User Input  │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│ Claude Code Native  │◄──────┐
│ Model Access        │       │
└──────────┬──────────┘       │
           │                  │
           ▼                  │
┌─────────────────────┐       │
│ Council Mode Script │       │
│ (skill.py routes)   │       │
└──────────┬──────────┘       │
           │                  │
           ▼                  │
┌─────────────────────┐       │
│ Generate Prompt     │       │
│ (Mode-specific)     │       │
└──────────┬──────────┘       │
           │                  │
           ▼                  │
┌─────────────────────┐       │
│ Call Claude API      │───────┘ (uses Claude Code's built-in model)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Save Artifact       │
│ (build-plans/*.md)  │
└─────────────────────┘
```

### Enhanced Flow (With Optional LiteLLM)

```
┌─────────────┐
│ User Input  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────┐
│ LiteLLM Gateway Running?    │
└──────────┬──────────────────┘
           │
     ┌─────┴─────┐
     │           │
    NO          YES
     │           │
     ▼           ▼
┌──────────┐  ┌──────────────┐
│ Fallback │  │ Multi-Model  │
│ to Claude │  │ Execution    │
│ Native    │  │ (Per mode)   │
└─────┬────┘  └──────┬───────┘
      │              │
      └──────┬───────┘
             ▼
┌─────────────────────┐
│ Save Artifact       │
│ (build-plans/*.md)  │
└─────────────────────┘
```

---

## Directory Structure

```
ai-roundtable/                    # Repository root
│
├── SKILL.md                      # Claude Code skill entry point
├── skill_manifest.yaml           # Permissions and metadata
├── LICENSE                       # MIT license
├── README.md                     # User-facing documentation
├── requirements.txt              # Optional Python dependencies
├── .gitignore                    # Git ignore patterns
│
├── scripts/                      # Core skill implementation
│   ├── skill.py                  # Main entry point / router
│   ├── brainstorm.py             # Mode 1: Parallel ideation
│   ├── refine.py                 # Mode 2: Sequential refinement
│   ├── build_planner.py          # Mode 3: Build specifications
│   ├── build_reviewer.py         # Mode 4: Post-build validation
│   ├── opus_gatekeeper.py        # Mode 5: Cost optimization
│   ├── parallel_executor.py      # Mode 6: Diamond debate engine
│   ├── gateway.py                # LiteLLM interface (optional)
│   ├── models.py                 # Model configuration
│   ├── schemas.py                # Data structures
│   ├── paths.py                  # Path utilities
│   ├── intent_detector.py        # Auto-routing logic
│   ├── perplexity_wrapper.py     # Perplexity API (optional)
│   └── review_metacognition.py   # Review analysis
│
├── lib/                          # Shared utilities (no external deps)
│   ├── paths.py                  # Cross-platform path handling
│   └── schemas.py                # Shared data structures
│
├── config/                       # Configuration templates
│   ├── roundtable.example.yaml   # Main configuration
│   └── models.yaml.example       # Model definitions
│
├── litellm/                      # Optional LiteLLM gateway
│   ├── config.yaml.example       # Gateway configuration template
│   ├── launch_gateway.py         # Gateway launcher
│   └── logs/                     # Gateway logs (gitignored)
│
├── memory/                       # Optional memory subsystem
│   ├── init_db.py                # Database initialization
│   ├── migrations/               # Database schema migrations
│   │   └── init_schema.sql       # Initial schema
│   ├── config/                   # Memory configuration
│   │   └── memory_settings.json  # Memory settings
│   ├── lib/                      # Memory utilities
│   │   └── enhanced_recall.py    # Context retrieval
│   └── data/                     # Database files (gitignored)
│       └── council_memory.db     # SQLite database
│
├── dashboard/                    # Optional web dashboard
│   ├── start_dashboard.py        # Dashboard launcher
│   ├── backend/                  # Flask backend
│   │   ├── server.py             # Main server
│   │   ├── councilmemoryapi.py   # Memory API endpoints
│   │   └── ...                   # Other backend modules
│   ├── frontend/                 # Web UI
│   │   └── index.html            # Main dashboard page
│   └── data/                     # Dashboard cache (gitignored)
│
├── hooks/                        # Optional hook examples
│   └── examples/                 # Example hooks (opt-in)
│       ├── SessionStart.py.example
│       ├── PreToolUse.py.example
│       └── PostToolUse.py.example
│
├── examples/                     # Sample usage and outputs
│   ├── sample-brainstorm.md
│   ├── sample-debate.md
│   └── screenshots/
│
├── docs/                         # Documentation
│   ├── ARCHITECTURE.md           # This file
│   ├── SECURITY.md               # Security model and threat analysis
│   ├── INSTALLATION.md           # Installation guide
│   ├── CONFIGURATION.md          # Configuration reference
│   └── TROUBLESHOOTING.md        # Common issues and solutions
│
└── build-plans/                  # Generated artifacts (gitignored)
    └── *.md                      # Build plan outputs
```

---

## Security Boundaries

### Filesystem Jail

All operations are confined to the repository root:

```
ai-roundtable/              # Jail boundary
├── build-plans/           # WRITE allowed (artifacts)
├── memory/data/           # WRITE allowed (optional DB)
├── dashboard/data/        # WRITE allowed (optional cache)
└── litellm/logs/          # WRITE allowed (gateway logs)
```

**Path Enforcement:** `lib/paths.py` validates all paths before operations.

### Network Boundary

```
DEFAULT: No network access
OPTIONAL: localhost:4000 (LiteLLM gateway only)
```

**Gateway Isolation:** LiteLLM binds to `localhost` only, never to `0.0.0.0`.

### Code Execution Boundary

```
DEFAULT: No subprocess execution
OPTIONAL: User-initiated only (explicit commands)
```

**Hook Policy:** All hooks are `.example` files requiring manual opt-in.

---

## Extension Points

### Adding a New Mode

1. Create `scripts/new_mode.py`
2. Implement the mode function
3. Add routing in `scripts/skill.py`
4. Update intent detection in `scripts/intent_detector.py`
5. Add documentation to `SKILL.md`

### Adding a New Optional Component

1. Create component directory
2. Add to `skill_manifest.yaml` under `components.optional`
3. Document installation in `docs/INSTALLATION.md`
4. Add graceful degradation logic

### Adding Configuration Options

1. Update `config/roundtable.example.yaml`
2. Document in `docs/CONFIGURATION.md`
3. Add loading logic to appropriate script
4. Handle missing config with defaults

---

## Version Compatibility

| Component | Version | Notes |
|-----------|---------|-------|
| Claude Code | >= 1.0.0 | Minimum supported version |
| Python | >= 3.8 | For optional components only |
| litellm | Latest | User-installed, no pinning |
| Flask | Latest | Dashboard only |

---

## Performance Characteristics

| Mode | Duration | Cost (with LiteLLM) | Cost (fallback) |
|------|----------|-------------------|-----------------|
| Brainstorming | ~60s | $0.05 | $0 (native) |
| Refinement | ~90s | $0.10 | $0 (native) |
| Build Planning | ~5min | $0.25 | $0 (native) |
| Build Reviewer | ~2min | $0.08 | $0 (native) |
| Opus Gatekeeper | ~10s | $0.01 | $0 (native) |
| Diamond Debate | ~3min | $0.30 | $0 (native) |
| Team Debate | ~4min | $0.20 | $0 (native) |

*Costs are estimates with 2026 pricing. Fallback uses Claude Code's native model (no additional cost).*

---

## Future Roadmap

### Phase 1: Core Distribution (Current)

- ✅ Core 7 modes working with Claude Code native
- ✅ Security model documented
- ✅ Graceful degradation implemented
- 🔄 Public GitHub release in progress

### Phase 2: Enhanced Documentation (Next)

- [ ] Interactive tutorials
- [ ] Video demonstrations
- [ ] Example gallery
- [ ] Community contribution guide

### Phase 3: Advanced Features (Future)

- [ ] Custom model providers
- [ ] Distributed execution (multiple Claude Code instances)
- [ ] Plugin system for third-party modes
- [ ] Integration with other skills

---

*This architecture document is maintained alongside the codebase. For implementation details, see the source code and comments.*
