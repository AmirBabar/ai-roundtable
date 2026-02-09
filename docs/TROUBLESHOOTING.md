# AI Roundtable Troubleshooting Guide

This guide covers common issues and their solutions when using AI Roundtable.

## Table of Contents

- [Installation Issues](#installation-issues)
- [LiteLLM Gateway Issues](#litellm-gateway-issues)
- [Mode-Specific Issues](#mode-specific-issues)
- [Memory Issues](#memory-issues)
- [Dashboard Issues](#dashboard-issues)
- [Path and File Issues](#path-and-file-issues)
- [Performance Issues](#performance-issues)
- [Getting Help](#getting-help)

---

## Installation Issues

### Skill Not Found

**Symptom:** `/roundtable` command doesn't work in Claude Code

**Diagnosis:**
```bash
# Check if skill files exist
# Windows PowerShell
Test-Path "$env:USERPROFILE\.claude\skills\roundtable\SKILL.md"

# macOS/Linux
ls ~/.claude/skills/roundtable/SKILL.md
```

**Solutions:**

1. **Verify installation location:**
   - Windows: `C:\Users\YOUR_USERNAME\.claude\skills\roundtable\`
   - macOS/Linux: `~/.claude/skills/roundtable/`

2. **Check SKILL.md exists:**
   ```bash
   # If missing, copy from repository
   cp ai-roundtable/SKILL.md ~/.claude/skills/roundtable/
   ```

3. **Restart Claude Code** after copying files

### Import Errors

**Symptom:** `ModuleNotFoundError: No module named 'paths'`

**Diagnosis:**
```bash
# Check lib directory exists
ls ~/.claude/skills/roundtable/lib/paths.py
```

**Solutions:**

1. **Copy lib directory:**
   ```bash
   cp -r ai-roundtable/lib ~/.claude/skills/roundtable/
   ```

2. **Check Python path** (if running scripts directly):
   ```python
   import sys
   print(sys.path)
   ```

### Permission Denied

**Symptom:** `PermissionError: [Errno 13] Permission denied`

**Solutions:**

1. **Check file permissions:**
   ```bash
   # macOS/Linux
   chmod +x ~/.claude/skills/roundtable/scripts/*.py

   # Windows: Run as Administrator if needed
   ```

2. **Verify write access:**
   ```bash
   # Check you can write to build-plans directory
   mkdir -p ~/.claude/skills/roundtable/build-plans
   echo "test" > ~/.claude/skills/roundtable/build-plans/test.txt
   ```

---

## LiteLLM Gateway Issues

### Gateway Won't Start

**Symptom:** `litellm --config litellm/config.yaml` fails

**Diagnosis:**
```bash
# Check if port is already in use
# Windows PowerShell
Test-NetConnection -ComputerName localhost -Port 4000

# macOS/Linux
lsof -i :4000
```

**Solutions:**

1. **Port already in use:**
   ```bash
   # Kill existing process
   # macOS/Linux
   kill -9 $(lsof -t -i:4000)

   # Windows: Find and kill process in Task Manager
   # Or use different port:
   litellm --config litellm/config.yaml --port 4001
   ```

2. **Missing dependencies:**
   ```bash
   pip install litellm
   ```

3. **Config file error:**
   ```bash
   # Validate YAML syntax
   litellm --config litellm/config.yaml --dry-run
   ```

### Gateway Connection Refused

**Symptom:** `Connection refused` error when skill tries to use gateway

**Diagnosis:**
```bash
# Check if gateway is running
curl http://localhost:4000/health
```

**Solutions:**

1. **Start the gateway:**
   ```bash
   litellm --config litellm/config.yaml --port 4000
   ```

2. **Check firewall settings:**
   - Ensure localhost connections are allowed
   - Windows: Allow in Windows Defender
   - macOS: Allow in firewall preferences

3. **Verify port number:**
   - Check skill config matches gateway port
   - Default: `localhost:4000`

### API Key Errors

**Symptom:** `401 Unauthorized` or `API key not found`

**Diagnosis:**
```bash
# Check if API keys are set
echo $ANTHROPIC_API_KEY  # macOS/Linux
echo $env:ANTHROPIC_API_KEY  # Windows PowerShell
```

**Solutions:**

1. **Set API key as environment variable:**
   ```bash
   export ANTHROPIC_API_KEY="your-key"  # macOS/Linux
   set ANTHTROPIC_API_KEY=your-key  # Windows
   ```

2. **Or add to litellm/config.yaml:**
   ```yaml
   environment_variables:
     ANTHROPIC_API_KEY: "your-key"
   ```

3. **Verify key is valid:**
   - Check API provider dashboard
   - Generate new key if needed

### Model Not Found

**Symptom:** `Model 'xyz' not found in model list`

**Solutions:**

1. **Check model name in config:**
   - Verify name matches `litellm/config.yaml`
   - Model names are case-sensitive

2. **Test model directly:**
   ```bash
   curl http://localhost:4000/v1/models
   ```

3. **Add model to config:**
   ```yaml
   model_list:
     - model_name: your-model
       litellm_params:
         model: "provider/model-name"
         api_key: "your-api-key"
   ```

---

## Mode-Specific Issues

### Brainstorming Returns Few Ideas

**Symptom:** Only getting 1-2 ideas instead of expected 10+

**Solutions:**

1. **Check ideas_per_model setting:**
   ```yaml
   brainstorm:
     ideas_per_model: 10  # Increase this
   ```

2. **Verify models are working:**
   ```bash
   /roundtable brainstorm "test"  # Should return multiple ideas
   ```

3. **Check synthesizer model:**
   - May be filtering duplicates aggressively
   - Try different synthesizer model

### Refinement Mode Stuck

**Symptom:** Refinement mode seems to hang or loop

**Solutions:**

1. **Check quality gate settings:**
   ```yaml
   refine:
     quality_gate_level: 3  # Lower if too strict
   ```

2. **Increase timeout:**
   ```yaml
   general:
     default_timeout: 180000  # 3 minutes instead of 2
   ```

3. **Check model availability:**
   - Verify all refinement models are accessible
   - Fallback to Claude native if needed

### Diamond Debate Timeout

**Symptom:** Diamond debate times out after 2-3 minutes

**Solutions:**

1. **Increase mode-specific timeout:**
   ```yaml
   diamond_debate:
     timeout: 300000  # 5 minutes
   ```

2. **Reduce model complexity:**
   ```yaml
   diamond_debate:
     stage2_models:
       - "gemini-flash"  # Use faster models
       - "deepseek-chat"
   ```

3. **Skip conditional ratification:**
   ```yaml
   diamond_debate:
     conditional_ratification: false  # Always skip Opus
   ```

### Build Plan Missing Components

**Symptom:** Build plan doesn't include verification table

**Solutions:**

1. **Enable verification requirements:**
   ```yaml
   build_plan:
     require_verification: true
   ```

2. **Provide codebase context:**
   ```
   /roundtable build-plan "Implement feature X"
   Context: The relevant files are src/auth.py and src/models.py
   ```

3. **Check contextualist model:**
   - Needs access to codebase for verification
   - May be failing to read files

---

## Memory Issues

### Database Not Found

**Symptom:** `sqlite3.OperationalError: no such table: insights`

**Diagnosis:**
```bash
# Check if database exists
ls memory/data/council_memory.db
```

**Solutions:**

1. **Initialize database:**
   ```bash
   python memory/init_db.py
   ```

2. **Check database path:**
   ```yaml
   memory:
     db_path: "memory/data/council_memory.db"
   ```

### Memory Permission Denied

**Symptom:** `PermissionError: unable to open database file`

**Solutions:**

1. **Check database permissions:**
   ```bash
   chmod 644 memory/data/council_memory.db  # macOS/Linux
   ```

2. **Ensure directory exists:**
   ```bash
   mkdir -p memory/data
   ```

3. **Check write access:**
   - Verify user has write permission to memory/data/

### FULL Tier Access Denied

**Symptom:** `PermissionError: FULL tier access requires COUNCIL_MEMORY_FULL_ACCESS=true`

**Solutions:**

1. **Set environment variable:**
   ```bash
   export COUNCIL_MEMORY_FULL_ACCESS=true  # macOS/Linux
   set COUNCIL_MEMORY_FULL_ACCESS=true  # Windows
   ```

2. **Or use SAFE tier:**
   ```yaml
   memory:
     default_tier: "SAFE"  # Works without env var
   ```

---

## Dashboard Issues

### Dashboard Won't Start

**Symptom:** `python dashboard/start_dashboard.py` fails

**Diagnosis:**
```bash
# Check if port is already in use
# Windows PowerShell
Test-NetConnection -ComputerName localhost -Port 5000

# macOS/Linux
lsof -i :5000
```

**Solutions:**

1. **Install dependencies:**
   ```bash
   pip install flask
   ```

2. **Port already in use:**
   ```bash
   # Kill existing process or use different port
   python dashboard/start_dashboard.py --port 5001
   ```

3. **Check database exists:**
   ```bash
   python memory/init_db.py  # Dashboard needs memory database
   ```

### Dashboard Shows No Data

**Symptom:** Dashboard loads but shows empty tables

**Solutions:**

1. **Run a Council session first:**
   ```
   /roundtable brainstorm "test"
   ```

2. **Check database has data:**
   ```bash
   sqlite3 memory/data/council_memory.db "SELECT COUNT(*) FROM sessions;"
   ```

3. **Verify dashboard config:**
   - Check `dashboard/backend/config.py` for correct database path

### Dashboard Not Auto-Opening

**Symptom:** Dashboard starts but browser doesn't open

**Solutions:**

1. **Manually open browser:**
   ```
   Navigate to: http://localhost:5000
   ```

2. **Check auto_open setting:**
   ```yaml
   dashboard:
     auto_open: true  # Enable this
   ```

3. **Check browser default:**
   - Set default browser in OS settings

---

## Path and File Issues

### Path Traversal Warning

**Symptom:** `SecurityError: Path escape attempt detected`

**Diagnosis:**
```bash
# Check if paths are being validated
grep "enforce_jail" config/roundtable.yaml
```

**Solutions:**

1. **This is expected security behavior** - the jail is working

2. **If you need legitimate access:**
   - Use paths within the repository
   - Add directory to `write_allowed_dirs`

3. **Disable jail (not recommended):**
   ```yaml
   security:
     enforce_jail: false  # Only for trusted environments
   ```

### Invalid Filename Characters

**Symptom:** File creation fails on Windows

**Diagnosis:**
```bash
# Check for illegal characters in filename
# Windows illegal: < > : " / \ | ? *
```

**Solutions:**

1. **Let path sanitization handle it:**
   - Filenames are automatically sanitized
   - Illegal chars replaced with `_`

2. **Use simpler filenames:**
   - Avoid special characters
   - Use alphanumeric and hyphens only

### Git Bash Path Issues (Windows)

**Symptom:** Paths like `/c/Users/...` don't work

**Solutions:**

1. **Use path_resolver:**
   ```python
   from lib.paths import convert_posix_to_windows
   windows_path = convert_posix_to_windows("/c/Users/file.txt")
   ```

2. **Or use native Windows paths:**
   - Use `C:\Users\...` instead of `/c/Users/...`

---

## Performance Issues

### Slow Mode Execution

**Symptom:** Modes take much longer than expected

**Diagnosis:**
```bash
# Check gateway response time
curl -w "@curl-format.txt" http://localhost:4000/v1/models
```

**Solutions:**

1. **Use faster models:**
   ```yaml
   brainstorm:
     models:
       - "gemini-flash"  # Fast instead of deepseek-v3
   ```

2. **Reduce parallelism:**
   ```yaml
   brainstorm:
     models:
       - "gemini-flash"  # Use 1 model instead of 3
   ```

3. **Check network latency:**
   - Test gateway connectivity
   - Use local models when possible

### High API Costs

**Symptom:** Unexpectedly high usage costs

**Solutions:**

1. **Use Opus Gatekeeper:**
   ```
   /roundtable opus-gatekeeper "Should I use Opus for this query?"
   ```

2. **Set cost limits:**
   ```yaml
   opus_gatekeeper:
     max_budget: 0.50  # Lower the limit
   ```

3. **Monitor dashboard:**
   - Check cost tracking in dashboard
   - Review expensive modes

---

## Getting Help

If none of these solutions work:

### 1. Enable Debug Mode

```bash
export ROUNDTABLE_VERBOSE=true  # macOS/Linux
set ROUNDTABLE_VERBOSE=true  # Windows
```

### 2. Check Logs

```bash
# Gateway logs
cat litellm/logs/litellm.log

# Tool usage logs (if hooks enabled)
cat ~/.claude/logs/tool_usage.log
```

### 3. Verify Installation

```bash
# Run test
python -c "from lib.paths import get_repo_root; print(get_repo_root())"

# Expected: /path/to/ai-roundtable
```

### 4. Get Community Help

- **GitHub Issues:** https://github.com/yourusername/ai-roundtable/issues
- **GitHub Discussions:** https://github.com/yourusername/ai-roundtable/discussions
- **Documentation:** [docs/](.) directory

### 5. Report a Bug

When reporting bugs, include:

1. **Platform and OS version**
   ```
   Windows 11, macOS 14, Ubuntu 22.04, etc.
   ```

2. **Claude Code version**
   ```
   Check in Claude Code: /help or About
   ```

3. **Error message (full output)**
   ```
   Paste the complete error traceback
   ```

4. **Steps to reproduce**
   ```
   1. Run: /roundtable brainstorm "test"
   2. Expected: List of ideas
   3. Actual: Error message
   ```

5. **Configuration files**
   ```
   Attach sanitized versions of:
   - config/roundtable.yaml
   - litellm/config.yaml (remove API keys!)
   ```

---

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `ModuleNotFoundError: No module named 'paths'` | lib/ not copied | Copy lib/ directory |
| `Connection refused` | Gateway not running | Start LiteLLM gateway |
| `401 Unauthorized` | Invalid API key | Check API key settings |
| `PermissionError: FULL tier access` | Missing env var | Set `COUNCIL_MEMORY_FULL_ACCESS=true` |
| `Path escape attempt` | Security jail working | Use paths within repo |
| `Model not found` | Model not in config | Add to litellm/config.yaml |
| `timeout` | Request too slow | Increase timeout setting |
| `no such table` | Database not initialized | Run `python memory/init_db.py` |

---

*Last Updated: 2026-02-09*
