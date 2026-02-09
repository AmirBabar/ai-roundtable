# AI Roundtable Configuration Guide

This guide explains all configuration options for AI Roundtable, including mode settings, model assignments, and optional components.

## Table of Contents

- [Overview](#overview)
- [Quick Configuration](#quick-configuration)
- [Main Configuration (roundtable.yaml)](#main-configuration-roundtableyaml)
- [Model Configuration (models.yaml)](#model-configuration-modelsyaml)
- [LiteLLM Gateway Configuration](#litellm-gateway-configuration)
- [Memory Configuration](#memory-configuration)
- [Mode-Specific Settings](#mode-specific-settings)
- [Environment Variables](#environment-variables)

---

## Overview

AI Roundtable uses two main configuration files:

| File | Purpose | Required |
|------|---------|----------|
| `config/roundtable.yaml` | General settings, timeouts, paths | No (has defaults) |
| `config/models.yaml` | Model assignments and fallbacks | No (has defaults) |
| `litellm/config.yaml` | LiteLLM gateway settings | Yes, for multi-model |

### Configuration Loading Order

AI Roundtable loads configuration in this order (later overrides earlier):

1. Built-in defaults
2. `config/roundtable.yaml` (if exists)
3. `config/models.yaml` (if exists)
4. Environment variables (override all)

---

## Quick Configuration

### Minimal Setup (No Configuration File)

The core skill works without any configuration files:

```
Just use Claude Code's native model:
/roundtable brainstorm "Generate ideas"
```

### With LiteLLM (Recommended for Full Features)

```bash
# 1. Copy example configuration
cp config/roundtable.example.yaml config/roundtable.yaml
cp config/models.yaml.example config/models.yaml
cp litellm/config.yaml.example litellm/config.yaml

# 2. Edit litellm/config.yaml with your API keys
# 3. Start the gateway
litellm --config litellm/config.yaml --port 4000
```

---

## Main Configuration (roundtable.yaml)

The main configuration file controls general behavior, timeouts, and optional components.

### Copy the Example

```bash
cp config/roundtable.example.yaml config/roundtable.yaml
```

### Configuration Sections

#### General Settings

```yaml
general:
  # Default timeout for AI model calls (milliseconds)
  default_timeout: 120000

  # Whether to save all build plans to build-plans/ directory
  save_artifacts: true

  # Verbose logging (useful for debugging)
  verbose: false

  # Default mode to use when auto-detection is uncertain
  fallback_mode: "brainstorm"
```

#### LiteLLM Gateway Settings

```yaml
litellm:
  # Enable LiteLLM gateway for multi-model routing
  # If false, uses Claude Code's native model (fallback mode)
  enabled: true

  # Gateway location
  host: "localhost"
  port: 4000

  # Configuration file location
  config_path: "litellm/config.yaml"

  # Auto-start gateway if not running (experimental)
  auto_start: false
```

#### Mode-Specific Settings

```yaml
modes:
  # Brainstorming Mode
  brainstorm:
    # Number of ideas to generate per model
    ideas_per_model: 10

    # Models to use (if LiteLLM enabled)
    models:
      - "gemini-flash"
      - "deepseek-chat"
      - "claude-haiku"

    # Synthesizer model
    synthesizer: "claude-sonnet-4"

  # Refinement Mode
  refine:
    # Number of refinement passes
    passes: 3

    # Quality gate strictness (1-5, higher = stricter)
    quality_gate_level: 3

    # Models for each pass
    models:
      - "claude-haiku"
      - "claude-sonnet-4"
      - "claude-opus-4"

  # Build Planning Mode
  build_plan:
    # Architect model
    architect: "gemini-architect"

    # Auditor model (critical review)
    auditor: "deepseek-v3"

    # Contextualist model (codebase integration)
    contextualist: "kimi-researcher"

    # Judge model (final decision)
    judge: "opus-synthesis"

    # Enable verification requirements
    require_verification: true

  # Diamond Debate Mode
  diamond_debate:
    # Stage 1: Context gathering models
    stage1_models:
      - "kimi-researcher"
      - "perplexity-online"

    # Stage 2: Deliberation models
    stage2_models:
      - "deepseek-v3"
      - "gemini-flash"
      - "claude-sonnet-4"

    # Stage 3: Semi-final synthesis
    stage3_model: "gemini-pro"

    # Stage 4: Final ratification (conditional)
    stage4_model: "claude-opus-4"

    # Require ratification only if disagreement exists
    conditional_ratification: true
```

#### Memory Subsystem Settings

```yaml
memory:
  # Enable persistent memory across sessions
  enabled: true

  # Database location
  db_path: "memory/data/council_memory.db"

  # Memory tier (CRITICAL, SAFE, FULL)
  # CRITICAL: Core constraints only
  # SAFE: Decisions and preferences (default)
  # FULL: Everything including error patterns
  default_tier: "SAFE"

  # Context injection (add memory to Council prompts)
  inject_context: true

  # Maximum context items to inject
  max_context_items: 10
```

#### Dashboard Settings

```yaml
dashboard:
  # Enable web dashboard
  enabled: true

  # Dashboard server settings
  host: "localhost"
  port: 5000

  # Auto-open browser on start
  auto_open: true

  # Update frequency (milliseconds)
  update_interval: 1000
```

#### Security Settings

```yaml
security:
  # Enforce path jail (prevent directory traversal)
  enforce_jail: true

  # Allowed file operations
  allow_read: true
  allow_write: true

  # Write restrictions (only these directories)
  write_allowed_dirs:
    - "build-plans"
    - "memory/data"
    - "dashboard/data"
    - "litellm/logs"

  # Network access (default: none)
  allow_network: false

  # Subprocess execution (default: none)
  allow_subprocess: false
```

---

## Model Configuration (models.yaml)

The models configuration file defines which AI models to use for each collaboration mode.

### Copy the Example

```bash
cp config/models.yaml.example config/models.yaml
```

### Model Definitions

```yaml
models:
  # Fast, cost-effective models for ideation
  kimi-researcher:
    provider: "moonshot"
    model: "moonshot-v1-auto"
    tier: 3
    timeout: 60
    description: "Cost-effective with thinking capabilities"

  gemini-flash:
    provider: "google"
    model: "gemini-2.5-flash-exp"
    tier: 3
    timeout: 60
    description: "Fast ideation"

  deepseek-v3:
    provider: "deepseek"
    model: "deepseek-chat"
    tier: 2
    timeout: 180
    description: "Deep reasoning and analysis"

  claude-haiku:
    provider: "anthropic"
    model: "claude-3-5-haiku-20241022"
    tier: 3
    timeout: 60
    description: "Fast and lightweight"

  claude-sonnet-4:
    provider: "anthropic"
    model: "claude-sonnet-4-20250514"
    tier: 2
    timeout: 180
    description: "Latest Sonnet model"

  claude-opus-4:
    provider: "anthropic"
    model: "claude-opus-4-20250514"
    tier: 1
    timeout: 300
    description: "Highest quality, highest cost"
```

### Model Tiers

Models are organized into tiers based on cost and capability:

| Tier | Description | Use Case |
|------|-------------|----------|
| **1** | Highest quality, highest cost | Final decisions, critical reviews |
| **2** | Balanced performance | Most operations |
| **3** | Fast, cost-effective | Ideation, drafts |

### Mode Assignments

```yaml
mode_assignments:
  # Brainstorming Mode - Parallel ideation
  brainstorm:
    parallel_models:
      - "kimi-researcher"
      - "deepseek-v3"
      - "gemini-flash"
    synthesizer: "claude-sonnet-4"
    max_ideas: 20

  # Build Planning Mode - Four-step workflow
  build_plan:
    sequential_models:
      - model: "kimi-researcher"
        role: "Cost Architect"
      - model: "deepseek-v3"
        role: "Auditor - CRITICAL REVIEW"
      - model: "claude-sonnet-4"
        role: "Contextualist"
      - model: "gemini-pro"
        role: "Semi-Final Judge"
      - model: "opus-synthesis"
        role: "Final Judge"
```

---

## LiteLLM Gateway Configuration

The LiteLLM gateway enables multi-model routing. Configure it in `litellm/config.yaml`.

### Copy the Example

```bash
cp litellm/config.yaml.example litellm/config.yaml
```

### Basic Configuration

```yaml
model_list:
  # Kimi / Moonshot
  - model_name: kimi-researcher
    litellm_params:
      model: "moonshot/moonshot-v1-auto"
      api_key: "YOUR_MOONSHOT_API_KEY"

  # Google Gemini
  - model_name: gemini-flash
    litellm_params:
      model: "google/gemini-2.5-flash-exp"
      api_key: "YOUR_GOOGLE_API_KEY"

  - model_name: gemini-pro
    litellm_params:
      model: "google/gemini-2.5-pro"
      api_key: "YOUR_GOOGLE_API_KEY"

  # DeepSeek
  - model_name: deepseek-v3
    litellm_params:
      model: "deepseek/deepseek-chat"
      api_key: "YOUR_DEEPSEEK_API_KEY"

  # Anthropic Claude
  - model_name: claude-haiku
    litellm_params:
      model: "anthropic/claude-3-5-haiku-20241022"
      api_key: "YOUR_ANTHROPIC_API_KEY"

  - model_name: claude-sonnet-4
    litellm_params:
      model: "anthropic/claude-sonnet-4-20250514"
      api_key: "YOUR_ANTHROPIC_API_KEY"

  - model_name: claude-opus-4
    litellm_params:
      model: "anthropic/claude-opus-4-20250514"
      api_key: "YOUR_ANTHROPIC_API_KEY"

# Optional: Environment variables instead of hardcoded keys
environment_variables:
  OPENAI_API_KEY: "your-openai-key"
  ANTHROPIC_API_KEY: "your-anthropic-key"
  GOOGLE_API_KEY: "your-google-key"
  DEEPSEEK_API_KEY: "your-deepseek-key"

# LiteLLM settings
litellm_settings:
  drop_params: true  # Drop extra params for non-Anthropic models
  success_callback: [...]  # Optional: logging callbacks
```

### Setting API Keys

**Option 1: Environment Variables (Recommended)**

```bash
# Linux/macOS
export ANTHROPIC_API_KEY="your-key"
export GOOGLE_API_KEY="your-key"
export DEEPSEEK_API_KEY="your-key"

# Windows PowerShell
$env:ANTHROPIC_API_KEY="your-key"
$env:GOOGLE_API_KEY="your-key"
$env:DEEPSEEK_API_KEY="your-key"

# Windows Command Prompt
set ANTHROPIC_API_KEY=your-key
set GOOGLE_API_KEY=your-key
set DEEPSEEK_API_KEY=your-key
```

**Option 2: In Configuration File**

Add keys directly in `litellm/config.yaml` (not recommended for shared systems).

### Start the Gateway

```bash
# Basic start
litellm --config litellm/config.yaml --port 4000

# With debug output
litellm --config litellm/config.yaml --port 4000 --debug

# In background (Linux/macOS)
litellm --config litellm/config.yaml --port 4000 &

# In background (Windows PowerShell)
Start-Process -WindowStyle Hidden litellm --config litellm/config.yaml --port 4000
```

### Verify Gateway is Running

```bash
# Check if gateway responds
curl http://localhost:4000/health

# Or in PowerShell
Test-NetConnection -ComputerName localhost -Port 4000
```

---

## Memory Configuration

Configure the memory subsystem for cross-session context persistence.

### Initialize Memory

```bash
python memory/init_db.py
```

This creates the database at `memory/data/council_memory.db`.

### Memory Settings

Edit `memory/config/memory_settings.json`:

```json
{
  "tier": "SAFE",
  "max_context_items": 10,
  "inject_context": true,
  "context_injection_mode": "recent",
  "enable_semantic_search": false,
  "enable_insights": true
}
```

### Memory Tiers

| Tier | Access | What's Included |
|------|--------|-----------------|
| **CRITICAL** | Always | Core constraints, security mandates |
| **SAFE** | Default (tier 2) | Decisions, preferences, insights |
| **FULL** | Requires env var | Everything including error patterns |

To access FULL tier:

```bash
export COUNCIL_MEMORY_FULL_ACCESS=true  # Linux/macOS
set COUNCIL_MEMORY_FULL_ACCESS=true     # Windows
```

---

## Mode-Specific Settings

### Brainstorming

```yaml
brainstorm:
  ideas_per_model: 10          # Ideas per model
  max_ideas: 30                # Total maximum ideas
  synthesizer: "claude-sonnet-4"  # Model that combines results
  parallel: true               # Run models in parallel
```

### Refinement

```yaml
refine:
  passes: 3                    # Number of refinement rounds
  quality_gate_level: 3        # Strictness (1-5)
  rollback_enabled: true       # Rollback on quality gate failure
  models:
    - "claude-haiku"           # Round 1: Draft
    - "claude-sonnet-4"         # Round 2: Improve
    - "claude-opus-4"           # Round 3: Final polish
```

### Build Planning

```yaml
build_plan:
  architect: "gemini-architect"        # Design architecture
  auditor: "deepseek-v3"               # Critical review
  contextualist: "claude-sonnet-4"      # Codebase integration
  judge: "opus-synthesis"              # Final decision
  require_verification: true           # Verify components exist
```

### Diamond Debate

```yaml
diamond_debate:
  stage1_models:               # Context gathering
    - "kimi-researcher"
    - "perplexity-online"
  stage2_models:               # Deliberation
    - "deepseek-v3"
    - "gemini-flash"
    - "claude-sonnet-4"
  stage3_model: "gemini-pro"   # Semi-final synthesis
  stage4_model: "claude-opus-4"  # Final ratification
  conditional_ratification: true   # Only use Opus if needed
```

---

## Environment Variables

Environment variables override configuration file settings.

### General

| Variable | Purpose | Default |
|----------|---------|---------|
| `ROUNDTABLE_CONFIG_PATH` | Path to config file | `config/roundtable.yaml` |
| `ROUNDTABLE_VERBOSE` | Enable verbose logging | `false` |
| `ROUNDTABLE_TIMEOUT` | Default timeout (ms) | `120000` |

### LiteLLM Gateway

| Variable | Purpose | Default |
|----------|---------|---------|
| `LITELLM_PORT` | Gateway port | `4000` |
| `LITELLM_HOST` | Gateway host | `localhost` |
| `LITELLM_CONFIG_PATH` | Config file path | `litellm/config.yaml` |

### Memory

| Variable | Purpose | Default |
|----------|---------|---------|
| `COUNCIL_MEMORY_DB_PATH` | Database path | `memory/data/council_memory.db` |
| `COUNCIL_MEMORY_FULL_ACCESS` | Enable FULL tier | `false` |
| `COUNCIL_MEMORY_DEFAULT_TIER` | Default tier | `SAFE` |

### API Keys (Recommended)

```bash
# Set these instead of putting keys in config files
export ANTHROPIC_API_KEY="your-key"
export GOOGLE_API_KEY="your-key"
export DEEPSEEK_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
```

---

## Troubleshooting Configuration

### Configuration Not Loading

**Problem:** Settings aren't being applied

**Solutions:**
1. Check file path is correct
2. Verify YAML syntax (no tabs, proper indentation)
3. Enable verbose logging: `export ROUNDTABLE_VERBOSE=true`
4. Check for environment variable overrides

### Model Not Found

**Problem:** Model name not recognized

**Solutions:**
1. Verify model name matches `litellm/config.yaml`
2. Check provider is configured correctly
3. Test model directly: `curl http://localhost:4000/v1/models`

### Gateway Timeout

**Problem:** Requests to gateway timeout

**Solutions:**
1. Increase timeout in `config/roundtable.yaml`
2. Check gateway is running: `curl http://localhost:4000/health`
3. Verify network connectivity

For more troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## Best Practices

1. **Use Environment Variables for API Keys** - Never commit keys to git
2. **Start with Default Settings** - Only customize what you need
3. **Test Each Mode** - Verify configurations work as expected
4. **Monitor Costs** - Use Opus Gatekeeper for expensive modes
5. **Keep Backups** - Save working configurations before making changes

---

*Last Updated: 2026-02-09*
