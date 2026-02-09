# AI Roundtable Installation Guide

This guide will walk you through installing AI Roundtable for Claude Code on Windows, macOS, and Linux.

## Table of Contents

- [Quick Start](#quick-start)
- [Platform-Specific Instructions](#platform-specific-instructions)
- [Optional Components](#optional-components)
- [Verification](#verification)
- [Uninstallation](#uninstallation)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

AI Roundtable requires **ZERO Python dependencies** for core functionality. The basic installation takes less than 5 minutes.

### Prerequisites

- **Claude Code** installed and working
- **Git** for cloning the repository
- Python 3.8+ (only for optional components)

### Basic Installation (All Platforms)

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/ai-roundtable.git
cd ai-roundtable

# 2. Copy to your Claude skills directory
# See platform-specific commands below
```

That's it! You can now use all 7 collaboration modes with Claude Code's native model.

---

## Platform-Specific Instructions

### Windows

#### Claude Code Skills Directory

```
C:\Users\YOUR_USERNAME\.claude\skills\
```

#### Installation Steps

**Option 1: Using PowerShell (Recommended)**

```powershell
# Clone the repository
git clone https://github.com/yourusername/ai-roundtable.git
cd ai-roundtable

# Create skills directory if it doesn't exist
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\skills\roundtable"

# Copy skill files
Copy-Item -Path SKILL.md -Destination "$env:USERPROFILE\.claude\skills\roundtable\"
Copy-Item -Path scripts\ -Destination "$env:USERPROFILE\.claude\skills\roundtable\scripts\" -Recurse
Copy-Item -Path lib\ -Destination "$env:USERPROFILE\.claude\skills\roundtable\lib\" -Recurse
```

**Option 2: Using Command Prompt**

```cmd
git clone https://github.com/yourusername/ai-roundtable.git
cd ai-roundtable

mkdir %USERPROFILE%\.claude\skills\roundtable
copy SKILL.md %USERPROFILE%\.claude\skills\roundtable\
xcopy /E /I /Y scripts %USERPROFILE%\.claude\skills\roundtable\scripts
xcopy /E /I /Y lib %USERPROFILE%\.claude\skills\roundtable\lib
```

**Option 3: Manual Copy**

1. Open File Explorer
2. Navigate to `C:\Users\YOUR_USERNAME\.claude\skills\`
3. Create a new folder named `roundtable`
4. Copy these from `ai-roundtable/`:
   - `SKILL.md`
   - `scripts/` folder
   - `lib/` folder

#### Verify Installation

```powershell
# Check files exist
Test-Path "$env:USERPROFILE\.claude\skills\roundtable\SKILL.md"
Test-Path "$env:USERPROFILE\.claude\skills\roundtable\scripts\skill.py"
Test-Path "$env:USERPROFILE\.claude\skills\roundtable\lib\paths.py"
```

### macOS

#### Claude Code Skills Directory

```
~/.claude/skills/
```

#### Installation Steps

```bash
# Clone the repository
git clone https://github.com/yourusername/ai-roundtable.git
cd ai-roundtable

# Create skills directory if it doesn't exist
mkdir -p ~/.claude/skills/roundtable

# Copy skill files
cp SKILL.md ~/.claude/skills/roundtable/
cp -r scripts ~/.claude/skills/roundtable/
cp -r lib ~/.claude/skills/roundtable/
```

#### Verify Installation

```bash
# Check files exist
ls -la ~/.claude/skills/roundtable/SKILL.md
ls -la ~/.claude/skills/roundtable/scripts/skill.py
ls -la ~/.claude/skills/roundtable/lib/paths.py
```

### Linux

#### Claude Code Skills Directory

```
~/.claude/skills/
```

#### Installation Steps

```bash
# Clone the repository
git clone https://github.com/yourusername/ai-roundtable.git
cd ai-roundtable

# Create skills directory if it doesn't exist
mkdir -p ~/.claude/skills/roundtable

# Copy skill files
cp SKILL.md ~/.claude/skills/roundtable/
cp -r scripts ~/.claude/skills/roundtable/
cp -r lib ~/.claude/skills/roundtable/
```

#### Verify Installation

```bash
# Check files exist
ls -la ~/.claude/skills/roundtable/SKILL.md
ls -la ~/.claude/skills/roundtable/scripts/skill.py
ls -la ~/.claude/skills/roundtable/lib/paths.py
```

---

## Optional Components

AI Roundtable includes optional components that enhance functionality but are **not required** for basic operation.

### 1. LiteLLM Gateway (Multi-Model Routing)

Enables access to diverse AI models (Gemini, DeepSeek, etc.) for enhanced collaboration modes.

#### Why Install It?

- **Diamond Debate** uses 5 different models in parallel
- **Team Debate** uses specialized models for each role
- More diverse perspectives and better cost optimization

#### Installation

```bash
# Install LiteLLM
pip install litellm

# Copy configuration example
cp litellm/config.yaml.example litellm/config.yaml

# Edit config.yaml with your API keys
# See CONFIGURATION.md for details
```

#### Start the Gateway

```bash
# From the ai-roundtable directory
litellm --config litellm/config.yaml --port 4000
```

**Gateway runs on:** http://localhost:4000

#### Configure Your API Keys

Edit `litellm/config.yaml` and add your API keys:

```yaml
environment_variables:
  OPENAI_API_KEY: "your-openai-key"
  ANTHROPIC_API_KEY: "your-anthropic-key"
  GOOGLE_API_KEY: "your-google-key"
```

### 2. Dashboard (Web UI)

Monitor your AI Roundtable sessions with a web interface.

#### Why Install It?

- Visual representation of debates
- Real-time cost tracking
- Memory inspection
- Session history

#### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# The dashboard requires:
# - Flask
# - sqlite3 (built-in)
```

#### Start the Dashboard

```bash
# From the ai-roundtable directory
python dashboard/start_dashboard.py
```

**Dashboard runs on:** http://localhost:5000

### 3. Memory Subsystem (Persistent Context)

Maintain context across sessions with a local SQLite database.

#### Why Install It?

- Remembers decisions and preferences
- Provides context to new sessions
- Stores insights and learnings
- Cross-session continuity

#### Installation

```bash
# Initialize the database
python memory/init_db.py
```

The database will be created at `memory/data/council_memory.db`

#### Configure Memory

Edit `memory/config/memory_settings.json` to customize behavior:

```json
{
  "tier": "SAFE",
  "max_context_items": 10,
  "inject_context": true
}
```

### Virtual Environment (Recommended for Optional Components)

If you're installing optional components, we recommend using a virtual environment:

#### Windows

```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

#### macOS/Linux

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Deactivate When Done

```bash
deactivate
```

---

## Verification

After installation, verify AI Roundtable is working correctly.

### Test Basic Functionality

In Claude Code, run:

```
/roundtable brainstorm "Test installation with 3 ideas"
```

**Expected Output:** A list of 3-5 brainstormed ideas

### Test With LiteLLM (If Installed)

```
/roundtable diamond-debate "Test query"
```

**Expected Output:** Multi-stage analysis with different model perspectives

### Test Dashboard (If Installed)

Visit http://localhost:5000 in your browser after running:

```bash
python dashboard/start_dashboard.py
```

**Expected Output:** Dashboard interface showing session history

### Test Memory (If Installed)

```bash
# Check database was created
ls memory/data/council_memory.db  # macOS/Linux
dir memory\data\council_memory.db  # Windows
```

---

## Uninstallation

If you want to remove AI Roundtable:

### Remove Skill Files

**Windows:**
```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\.claude\skills\roundtable"
```

**macOS/Linux:**
```bash
rm -rf ~/.claude/skills/roundtable
```

### Remove Optional Components

```bash
# Stop any running services
# (Ctrl+C in terminal where they're running)

# Remove repository
cd ..
rm -rf ai-roundtable

# Remove virtual environment (if created)
rm -rf .venv
```

### Remove Memory Database (Optional)

```bash
# Windows
Remove-Item -Force "$env:USERPROFILE\.claude\memory\data\council_memory.db"

# macOS/Linux
rm -f ~/.claude/memory/data/council_memory.db
```

---

## Troubleshooting

### Skill Not Found

**Problem:** `/roundtable` command doesn't work

**Solutions:**
1. Verify files were copied to the correct location
2. Check `SKILL.md` exists in `~/.claude/skills/roundtable/`
3. Restart Claude Code

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'paths'`

**Solutions:**
1. Ensure `lib/` folder was copied
2. Check `lib/paths.py` exists
3. Verify Python path includes the skill directory

### LiteLLM Gateway Won't Start

**Problem:** Gateway fails to start

**Solutions:**
1. Check API keys are set in `litellm/config.yaml`
2. Verify port 4000 is not already in use
3. Run `litellm --config litellm/config.yaml --port 4000 --debug`

For more troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

## Next Steps

After successful installation:

1. Read [CONFIGURATION.md](CONFIGURATION.md) to customize your setup
2. Try the [examples](../examples/) directory for sample usage
3. Explore the 7 collaboration modes
4. Consider setting up the optional components for enhanced functionality

---

## Getting Help

- **Issues:** [GitHub Issues](https://github.com/yourusername/ai-roundtable/issues)
- **Discussions:** [GitHub Discussions](https://github.com/yourusername/ai-roundtable/discussions)
- **Documentation:** [docs/](.) directory

---

*Last Updated: 2026-02-09*
