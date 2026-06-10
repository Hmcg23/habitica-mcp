# habitica-mcp

An MCP (Model Context Protocol) server for [Habitica](https://habitica.com) — connect your AI assistant to your habits, dailies, todos, and stats.

Built with [FastMCP](https://github.com/modelcontextprotocol/python-sdk) and the [Habitica API v3](https://habitica.com/apiv3/).

---

## What it does

Once connected, your AI assistant can:

- **Read** all your tasks — habits, dailies, todos, rewards
- **Score** habits and check off dailies/todos
- **Create, update, and delete** tasks
- **Manage checklist items** on dailies and todos
- **View your stats** — level, HP, XP, gold, streaks

---

## Setup

### 1. Get your Habitica credentials

Go to **Habitica → Settings → API** and copy your:
- **User ID**
- **API Token**

### 2. Install dependencies

```bash
pip install mcp httpx pydantic
```

### 3. Add to your Claude Desktop config

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "habitica": {
      "command": "python",
      "args": ["/absolute/path/to/habitica_mcp.py"],
      "env": {
        "HABITICA_USER_ID": "your-user-id-here",
        "HABITICA_API_KEY": "your-api-token-here"
      }
    }
  }
}
```

Restart Claude Desktop. The Habitica tools will appear automatically.

---

## Available tools

| Tool | Description |
|------|-------------|
| `habitica_get_tasks` | List tasks, optionally filtered by type (habits/dailys/todos/rewards) |
| `habitica_get_task` | Get full details for a single task by ID |
| `habitica_get_user_stats` | View your level, HP, XP, gold, and login streak |
| `habitica_score_task` | Score a task up or down (check off todos, click habits) |
| `habitica_create_task` | Create a new habit, daily, todo, or reward |
| `habitica_update_task` | Update a task's title, notes, priority, or due date |
| `habitica_delete_task` | Permanently delete a task |
| `habitica_add_checklist_item` | Add a sub-item to a daily or todo |
| `habitica_score_checklist_item` | Toggle a checklist sub-item complete/incomplete |

---

## Example prompts

Once connected to Claude, try:

- *"What habits do I have? Score my morning routine."*
- *"Show me all my incomplete todos sorted by due date."*
- *"Create a new daily called 'Read for 20 minutes' with medium difficulty."*
- *"What's my current level and HP?"*
- *"Check off 'Drink water' on my dailies."*

---

## Building something similar

Want to build an MCP for a different todo or productivity app? The pattern is the same:

1. Create a `FastMCP` server
2. Add environment-variable-based auth
3. Wrap each API endpoint as a `@mcp.tool`
4. Add to your Claude Desktop config

Good starting points:
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP documentation](https://modelcontextprotocol.io)
- [Habitica API docs](https://habitica.com/apiv3/)

---

## Contributing

PRs welcome. Some ideas:
- Party/group quest support
- Inventory and equipment tools
- Challenge management
- Webhook support for real-time scoring

---

## License

MIT
