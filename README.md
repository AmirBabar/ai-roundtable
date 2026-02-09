# AI Roundtable

> Multi-model AI orchestration platform for Claude Code

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Claude_Code-Compatible-blue.svg)](https://code.claude.com)
[![Version](https://img.shields.io/badge/version-3.0.0-brightgreen.svg)](https://github.com/yourusername/ai-roundtable)

AI Roundtable brings the power of multi-agent AI collaboration to Claude Code. Run sophisticated AI workflows with seven specialized collaboration modes—from brainstorming to architectural debates—all within your favorite AI coding assistant.

## ✨ Features

### Seven Collaboration Modes

| Mode | Best For | Duration |
|------|----------|----------|
| 🧠 **Brainstorming** | Generating diverse ideas | ~60s |
| 🔍 **Refinement** | Critical review & improvement | ~90s |
| 📋 **Build Planning** | Technical specifications | ~5min |
| ✅ **Build Reviewer** | Validating implementations | ~2min |
| 💰 **Opus Gatekeeper** | Cost optimization | ~10s |
| 💎 **Diamond Debate** | Complex architectural decisions | ~3min |
| 👥 **Team Debate** | Build specifications | ~4min |

### Key Highlights

- 🚀 **Zero Dependencies** - Core works with Claude Code's native capabilities
- 🔌 **Optional Enhancements** - Multi-model routing, dashboard, memory
- 🛡️ **Security First** - All operations confined to repo, no telemetry
- 📦 **Self-Contained** - Simple git clone to install
- 🌐 **Cross-Platform** - Works on Windows, macOS, Linux

## 🎯 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/ai-roundtable.git
cd ai-roundtable
```

### 2. Install as Claude Code Skill

```bash
# Windows
xcopy /E /I SKILL.md scripts lib %USERPROFILE%\.claude\skills\roundtable\

# macOS/Linux
cp -r SKILL.md scripts lib ~/.claude/skills/roundtable/
```

### 3. Start Using

In Claude Code, simply type:

```
/roundtable brainstorm "Ways to improve API performance"
/roundtable diamond-debate "PostgreSQL vs MongoDB for this project?"
/roundtable build-plan "Implement a caching system"
```

## 📖 Usage Examples

### Brainstorming

Generate diverse ideas with parallel AI models:

```
/roundtable brainstorm "Features for a developer dashboard"
```

**Output:** 15-20 categorized and prioritized ideas

### Diamond Debate

Make complex architectural decisions:

```
/roundtable diamond-debate "Should we use GraphQL or REST for our API?"
```

**Output:** Comprehensive analysis with recommendation

### Build Planning

Create detailed technical specifications:

```
/roundtable build-plan "Add user authentication to the web app"
```

**Output:** Full build plan with phases, tasks, and verification criteria

## 🔧 Optional Enhancements

### LiteLLM Gateway (Multi-Model Routing)

Enable access to diverse AI models (Gemini, DeepSeek, etc.):

```bash
pip install litellm
cp litellm/config.yaml.example litellm/config.yaml
# Edit config.yaml with your API keys
litellm --config litellm/config.yaml --port 4000
```

### Dashboard (Web UI)

Monitor your AI Roundtable sessions:

```bash
pip install flask
python dashboard/start_dashboard.py
# Visit http://localhost:5000
```

### Memory Subsystem

Maintain context across sessions:

```bash
python memory/init_db.py
```

## 📁 Project Structure

```
ai-roundtable/
├── SKILL.md              # Skill entry point
├── scripts/              # All 7 collaboration modes
├── lib/                  # Shared utilities
├── config/               # Configuration templates
├── docs/                 # Documentation
│   ├── ARCHITECTURE.md
│   ├── SECURITY.md
│   └── INSTALLATION.md
└── examples/             # Sample outputs
```

## 🛡️ Security

AI Roundtable is designed with security in mind:

- ✅ **Jailed Execution** - All operations confined to repo directory
- ✅ **No Telemetry** - Zero data collection or analytics
- ✅ **Opt-In Hooks** - Hooks require manual activation
- ✅ **Local Only** - All data stays on your machine
- ✅ **Open Source** - Full code visibility and review

See [docs/SECURITY.md](docs/SECURITY.md) for the complete security model.

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture and design |
| [SECURITY.md](docs/SECURITY.md) | Security model and threat analysis |
| [INSTALLATION.md](docs/INSTALLATION.md) | Detailed installation guide |
| [CONFIGURATION.md](docs/CONFIGURATION.md) | Configuration reference |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues and solutions |

## 🤝 Contributing

Contributions are welcome! Please see our contributing guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built for [Claude Code](https://code.claude.com) by Anthropic
- Inspired by multi-agent AI research and Diamond Architecture patterns
- Powered by diverse AI models through LiteLLM integration

## 📮 Contact

- **Issues:** [GitHub Issues](https://github.com/yourusername/ai-roundtable/issues)
- **Discussions:** [GitHub Discussions](https://github.com/yourusername/ai-roundtable/discussions)
- **Security:** security@your-domain.com

---

<div align="center">

**Made with ❤️ by the AI Roundtable Contributors**

[⭐ Star us on GitHub](https://github.com/yourusername/ai-roundtable) · [🐛 Report a Bug](https://github.com/yourusername/ai-roundtable/issues) · [💡 Suggest a Feature](https://github.com/yourusername/ai-roundtable/issues)

</div>
