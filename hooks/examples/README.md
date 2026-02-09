# AI Roundtable Hook Examples

This directory contains example hooks for AI Roundtable. Hooks are **opt-in** - they will NOT execute automatically.

## Security Notice

⚠️ **IMPORTANT**: All hooks in this directory have the `.example` extension. This prevents automatic execution.

Before enabling any hook:
1. **Review the code** to understand what it does
2. **Verify it's safe** for your environment
3. **Remove the `.example` extension** to activate
4. **Place in your Claude Code hooks directory**

## Available Hooks

### SessionStart.py.example

Runs at the start of each Claude Code session. Useful for:
- Loading previous session context
- Initializing memory subsystem
- Displaying session information

### PreToolUse.py.example

Runs before each tool execution. Useful for:
- Logging tool usage
- Validating tool parameters
- Security checks

### PostToolUse.py.example

Runs after each tool execution. Useful for:
- Capturing tool results
- Error handling
- Updating memory

## Installation

1. Copy the example hook you want to use:
   ```bash
   cp hooks/examples/SessionStart.py.example ~/.claude/hooks/SessionStart.py
   ```

2. Edit the hook to customize for your needs

3. Restart Claude Code

## Hook Development

When creating custom hooks:
- Keep them simple and focused
- Add clear comments explaining behavior
- Handle errors gracefully
- Respect user privacy (no sensitive data logging)
- Use `.example` extension for distribution

## See Also

- [Claude Code Hooks Documentation](https://code.claude.com/hooks)
- [docs/SECURITY.md](../../docs/SECURITY.md) - Security policies
