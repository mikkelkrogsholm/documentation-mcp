"""Claude Code documentation configuration."""

BASE_URL = "https://code.claude.com/docs/en"
LLMS_TXT_URL = "https://code.claude.com/docs/llms.txt"

# Markdown suffix - append to URL to get raw markdown
MARKDOWN_SUFFIX = ".md"

# All known documentation pages (from llms.txt)
DOC_PAGES = [
    ("Claude Code on Amazon Bedrock", "amazon-bedrock"),
    ("Analytics", "analytics"),
    ("Checkpointing", "checkpointing"),
    ("Use Claude Code with Chrome (beta)", "chrome"),
    ("Claude Code on the web", "claude-code-on-the-web"),
    ("CLI reference", "cli-reference"),
    ("Common workflows", "common-workflows"),
    ("Manage costs effectively", "costs"),
    ("Data usage", "data-usage"),
    ("Claude Code on desktop", "desktop"),
    ("Development containers", "devcontainer"),
    ("Discover and install prebuilt plugins", "discover-plugins"),
    ("Claude Code GitHub Actions", "github-actions"),
    ("Claude Code GitLab CI/CD", "gitlab-ci-cd"),
    ("Claude Code on Google Vertex AI", "google-vertex-ai"),
    ("Run Claude Code programmatically", "headless"),
    ("Hooks reference", "hooks"),
    ("Get started with Claude Code hooks", "hooks-guide"),
    ("Identity and Access Management", "iam"),
    ("Interactive mode", "interactive-mode"),
    ("JetBrains IDEs", "jetbrains"),
    ("Legal and compliance", "legal-and-compliance"),
    ("LLM gateway configuration", "llm-gateway"),
    ("Connect Claude Code to tools via MCP", "mcp"),
    ("Manage Claude's memory", "memory"),
    ("Claude Code on Microsoft Foundry", "microsoft-foundry"),
    ("Model configuration", "model-config"),
    ("Monitoring", "monitoring-usage"),
    ("Enterprise network configuration", "network-config"),
    ("Output styles", "output-styles"),
    ("Claude Code overview", "overview"),
    ("Create and distribute a plugin marketplace", "plugin-marketplaces"),
    ("Create plugins", "plugins"),
    ("Plugins reference", "plugins-reference"),
    ("Quickstart", "quickstart"),
    ("Sandboxing", "sandboxing"),
    ("Security", "security"),
    ("Claude Code settings", "settings"),
    ("Set up Claude Code", "setup"),
    ("Agent Skills", "skills"),
    ("Claude Code in Slack", "slack"),
    ("Slash commands", "slash-commands"),
    ("Status line configuration", "statusline"),
    ("Subagents", "sub-agents"),
    ("Optimize your terminal setup", "terminal-config"),
    ("Enterprise deployment overview", "third-party-integrations"),
    ("Troubleshooting", "troubleshooting"),
    ("Use Claude Code in VS Code", "vs-code"),
]
