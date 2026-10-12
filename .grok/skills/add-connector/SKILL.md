---
name: add-connector
description: Give a Voice Stack agent access to an external system as an HTTP tool, an MCP server, or a Python code plugin. Use when asked to connect an API, CRM, database, or MCP server to an agent.
---

# Add a connector

Options and formats are in `docs/tools-and-mcp.md` and `docs/extending.md`. Pick the lightest option that works:

| The system offers | Use |
|---|---|
| A public MCP server | MCP, hosted by xAI |
| An MCP server on a private network or stdio | MCP, run by Voice Stack |
| A REST endpoint | HTTP tool |
| Only an SDK, or needs logic | Code plugin (`@voice_tool` in `PLUGINS_DIR`) |

1. Store credentials as secrets (`PUT /api/secrets`) and reference them as `{{secret:NAME}}` or as MCP auth secrets. Never put credential values in YAML or code.
2. Create the tool (`POST /api/tools` or `POST /api/mcp`), or write the plugin file and restart.
3. Test it for real: `POST /api/tools/{id}/test` with sample arguments, or `POST /api/mcp/{id}/discover`. Shape HTTP output with `response_fields` so results are short enough to speak.
4. Attach it to the agent (`PATCH /api/agents/{id}` with `tool_ids` or `mcp_ids`) and mention it by exact name in the agent's Conversation Flow.
5. Check `POST /api/agents/{id}/prompt/lint` reports no `unknown_tool` findings. Then try it in a preview call.
