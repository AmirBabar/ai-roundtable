# Security Model

**Version:** 1.0.0
**Last Updated:** 2026-02-09
**Project:** AI Roundtable

---

## Executive Summary

AI Roundtable is a **user-installed skill** for Claude Code, not a third-party plugin marketplace distribution. The primary threat model focuses on **accidental damage to the parent environment** rather than malicious code injection, as users explicitly clone and install this repository.

---

## Threat Model

### Distribution Context

| Aspect | Description | Security Implications |
|--------|-------------|----------------------|
| **Installation Method** | User explicitly clones repository via git | User has implicit trust by choosing to install |
| **Code Visibility** | All source code is visible on GitHub | Users can review before installation |
| **Execution Context** | Runs within Claude Code's permission model | Bound by Claude Code's tool permissions |
| **Data Handling** | All data stays local by default | No telemetry or external data transmission |

### Primary Threats

#### 1. Accidental File System Damage

**Risk Level:** MEDIUM

Users may accidentally:
- Overwrite important files when using brainstorm/refinement modes
- Create artifacts in unexpected locations
- Modify configuration files incorrectly

**Mitigations:**
- All writes are scoped to `./data/` and `./build-plans/` directories
- Artifact filenames are sanitized for platform compatibility
- Configuration files use `.example` pattern (must be manually copied)

#### 2. Unintended Network Exposure

**Risk Level:** LOW

The LiteLLM gateway (optional component) could:
- Bind to all interfaces instead of localhost
- Expose internal model configurations

**Mitigations:**
- Gateway defaults to `localhost:4000` only
- No external API keys stored in repository
- Network access is optional (core skill works without it)

#### 3. Path Traversal via User Input

**Risk Level:** LOW

Malicious prompts could attempt to escape the skill directory.

**Mitigations:**
- All path operations use `pathlib.Path` with resolution
- Path validation enforces jail to repo root
- Filename sanitization removes illegal characters

### Out of Scope Threats

The following are **NOT** in scope because they're handled by Claude Code:

- Malicious prompt injection (Claude Code's responsibility)
- Tool permission violations (Claude Code's permission system)
- Memory exhaustion attacks (Claude Code's resource limits)
- Credential leakage in prompts (Claude Code's PII handling)

---

## Principle of Least Privilege

### Filesystem Access

```
READ:   . (entire repo - for context)
WRITE:  ./data/           (user-generated artifacts)
WRITE:  ./build-plans/    (council output artifacts)
WRITE:  ./memory/data/    (optional memory database)
WRITE:  ./dashboard/data/ (optional dashboard cache)

READ:   ~/.claude/memory/data/council_memory.db (shared memory, optional)
```

### Network Access

```
DEFAULT: none (core skill works offline)

OPTIONAL (LiteLLM gateway):
- localhost:4000 only
- outbound to model APIs (configured by user)
- no inbound connections from external sources
```

### Subprocess Execution

```
DEFAULT: none

OPTIONAL (user-initiated only):
- litellm --config (gateway launcher)
- python dashboard/start_dashboard.py (dashboard)
- All subprocess calls are user-triggered, not automatic
```

---

## Code Execution Policy

### 1. Hooks Must Be Opt-In

**Rule:** All hook files MUST be named with `.example` extension.

**Rationale:** Hooks execute automatically on Claude Code events. Users must manually opt-in by:
1. Reviewing the hook code
2. Understanding what it does
3. Renaming to remove `.example` extension
4. Placing in their Claude Code hooks directory

**Example:**
```
hooks/examples/SessionStart.py.example  ← Safe (won't execute)
hooks/SessionStart.py                   ← Executes automatically
```

### 2. No Auto-Execution of Downloaded Code

**Rule:** Installation scripts (`install.py`, `setup.py`) MUST:
- Only create directories and copy files
- NEVER modify system-wide configurations
- NEVER register hooks automatically
- NEVER start background services

**Rationale:** Users should have full visibility into what runs on their system.

### 3. All Data Stays Local

**Rule:** AI Roundtable MUST NOT:
- Send telemetry or analytics
- Upload conversation content
- Contact external services (except user-configured model APIs)
- Store credentials in repository

**Rationale:** Privacy by default. Users control their data.

---

## Dependency Security

### Python Dependencies

Core skill requires **ZERO Python dependencies** - it uses only Claude Code's native capabilities.

Optional components have dependencies:

| Component | Dependencies | Purpose | Security Review |
|-----------|-------------|---------|-----------------|
| Dashboard | Flask, sqlite3 | Web UI for monitoring | Standard libs, no known CVEs |
| Memory Subsystem | sqlite3 (stdlib) | Persistent context | Built-in Python library |
| LiteLLM Gateway | litellm package | Model routing | User-installed, review upstream |

### Dependency Isolation

**Recommendation:** Users should create a virtual environment for optional components:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

---

## Update/Patch Process

### Recommended User Workflow

1. **Check changelog:** Review `CHANGELOG.md` for security updates
2. **Pull changes:** `git pull origin main`
3. **Review diff:** `git diff HEAD~1` to see what changed
4. **Update deps:** `pip install -U -r requirements.txt` (if using optional components)
5. **Test:** Run a simple `/roundtable brainstorm` to verify functionality

### Security Vulnerability Reporting

If you find a security vulnerability:

1. **DO NOT** open a public issue
2. Email: security@[your-domain].com
3. Include: Description, steps to reproduce, impact assessment
4. We will respond within 7 days with mitigation plan

---

## Compliance and Privacy

### Data Collection

**We collect ZERO data.** AI Roundtable:
- Does not use analytics or tracking
- Does not phone home
- Does not create unique identifiers
- Stores all data locally on your machine

### PII (Personally Identifiable Information)

- **No PII collection:** We don't ask for names, emails, or identifiers
- **Local storage only:** Any PII in your conversations stays on your machine
- **No transmission:** PII is never sent externally (except to model APIs per your configuration)

### Model API Usage

When using LiteLLM gateway, your prompts are sent to configured model APIs (OpenAI, Anthropic, Google, etc.). This is:
- Configured by you in `litellm/config.yaml`
- Subject to each provider's privacy policy
- Outside our control

**Recommendation:** Review each model provider's privacy policy before use.

---

## Security Checklist for Users

Before using AI Roundtable, verify:

- [ ] Repository is cloned from official source: github.com/yourusername/ai-roundtable
- [ ] You have reviewed the SKILL.md to understand what it does
- [ ] Optional components (LiteLLM, dashboard) are understood before installation
- [ ] LiteLLM API keys are stored securely (not in repository)
- [ ] Hooks are reviewed before enabling (remove .example extension)
- [ ] Virtual environment is used for optional Python dependencies

---

## Security Checklist for Contributors

Before submitting code:

- [ ] No hardcoded credentials or API keys
- [ ] All user input is sanitized (path traversal, command injection)
- [ ] File operations use pathlib.Path (not string concatenation)
- [ ] Network operations default to localhost only
- [ ] Hooks are documented with .example extension
- [ ] Dependencies are minimal and well-maintained
- [ ] Changelog is updated with security-relevant changes

---

*This security model is a living document. Please report any concerns or suggestions.*
