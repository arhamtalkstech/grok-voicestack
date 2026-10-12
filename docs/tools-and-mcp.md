# Tools and MCP

Tools an agent can use fall into two groups. **Server-side tools** run at xAI. **Function tools** run in Voice Stack and are executed by the LangGraph runtime.

| Tool | Runs at | Set up in |
|---|---|---|
| `web_search` (allowed or excluded domains, up to 5) | xAI | Agent → Tools |
| `x_search` (allowed or excluded handles, up to 20; date range) | Voice Stack → xAI Responses API | Agent → Tools |
| `file_search` (xAI Collections) | xAI | Knowledge (collections mode) |
| MCP, hosted by xAI | xAI | Integrations → MCP servers |
| HTTP tools | Voice Stack | Integrations → HTTP tools |
| Code plugins (any LangChain tool) | Voice Stack | `PLUGINS_DIR` or a package entry point |
| MCP, run by Voice Stack | Voice Stack | Integrations → MCP servers |
| `search_knowledge` | Voice Stack | Knowledge (local mode) |
| `transfer_to_<agent>`, `transfer_call`, `end_call` | Voice Stack | Handoffs, transfer lines, Behavior |

**Why `x_search` runs through Voice Stack.** In realtime sessions the native `x_search` tool hands its inner tool (`x_keyword_search`) to the client as a function call and never runs it. The model also tends to announce a failure before calling it. This was verified live and is recorded in `docs/xai-api-notes.md`. So when X search is enabled, the agent gets a function tool named `x_search(query)`. Voice Stack runs it through the Responses API's `x_search`, applies the agent's handle and date filters, and returns a short summary. `web_search` runs natively at xAI and worked as documented.

Function tools run in parallel when the model calls several at once. Each has a timeout (`TOOL_TIMEOUT_S`, default 15 s). Errors and timeouts come back to the model as tool output, so the agent can say what happened. Every call shows in the live dock with its arguments, output, and latency.

## HTTP tools

Define them in the UI or in the landscape YAML:

```yaml
- name: check_order
  kind: http
  description: Look up an order's status by order number.
  parameters:
    type: object
    properties: {order_id: {type: string, description: "Order number, e.g. A-1042"}}
    required: [order_id]
  config:
    method: GET
    url: https://orders.example.com/v1/orders/{order_id}
    headers: {Authorization: "Bearer {{secret:ORDERS_TOKEN}}"}
    send_args_as: none            # query | json | none (arguments not used in the URL)
    response_fields:              # keep results short enough to speak
      status: $.status
      eta: $.delivery.estimated_date
    max_chars: 1500
    timeout_s: 10
  preamble: Let me check that order.
  requires_confirmation: false
```

- `{param}` placeholders in the URL are filled and URL-encoded. `body_template` accepts a JSON string with placeholders.
- `{{secret:NAME}}` pulls from the encrypted secret store (Integrations → Secrets).
- **Preamble** adds "Before calling, say a short line such as…" to the tool description, which masks latency as the guide suggests. **Confirm first** tells the model to ask before calling tools that change something.
- **SSRF guard:** URLs that resolve to private, loopback, or link-local addresses are blocked unless they match `SSRF_ALLOWLIST`.
- Use **Save and run** in the editor to test with real arguments.

## MCP servers

| Mode | How it works | Use when |
|---|---|---|
| Hosted by xAI | Listed in `session.tools` as `{"type": "mcp", "server_url", "server_label", "allowed_tools", "authorization", "headers"}`. xAI connects and calls the server. | The server is public (Streamable HTTP or SSE) and you want the lowest latency. |
| Run by Voice Stack | `langchain-mcp-adapters` connects. The server's tools are exposed to the model as function tools and executed by the graph. | The server is on a private network, uses stdio, or you want every call logged here. |

**Test connection** lists the server's tools in either mode. Tick the ones to allow. Credentials come from secrets: an Authorization secret plus optional header secrets. In hosted mode, those values are sent to xAI with the session config. They are masked in the UI's session inspector.

The sample landscape uses DeepWiki (`https://mcp.deepwiki.com/mcp`, tools `ask_wiki_question` and `read_wiki_structure`) in **managed** mode. In live tests, the same server in hosted mode often stalled after `response.mcp_call.in_progress`, and the agent told the caller the tool was unavailable. DeepWiki answers take tens of seconds. Managed mode answered reliably, with `MCP_TOOL_TIMEOUT_S` (default 60 s) covering the wait. Prefer managed mode for slow tools, and hosted mode for fast ones.

## Code plugins

Any LangChain tool works. Two ways to register one:

```python
# PLUGINS_DIR=/path/to/plugins, file my_tools.py
from voicestack.tools.plugins import voice_tool

@voice_tool
async def current_weather(city: str) -> str:
    """Get the current weather for a city."""
    ...
```

```toml
# Or in your own package's pyproject.toml
[project.entry-points."voicestack.tools"]
crm = "acme_voice.tools:TOOLS"   # a BaseTool, a list of tools, or a callable returning them
```

Then open Integrations → Code plugins → **Make available**, and attach the tool to an agent. `examples/plugins/open_meteo.py` is a working example that calls Open-Meteo, which needs no key.
