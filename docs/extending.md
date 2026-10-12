# Extending Voice Stack

Voice Stack is meant to be forked and built on. These are the seams.

## Add a tool backed by your system

Write a LangChain tool and register it. See [tools-and-mcp.md](tools-and-mcp.md#code-plugins):

```python
from voicestack.tools.plugins import voice_tool

@voice_tool
async def lookup_customer(phone: str) -> str:
    """Find a customer by phone number. Returns name, plan, and open tickets."""
    record = await my_crm.find(phone=phone)
    return f"{record.name}, {record.plan} plan, {len(record.tickets)} open tickets"
```

Keep tool output short and speakable: return a sentence or a small JSON object, not a whole record.

## Use your retriever for knowledge

Wrap any LangChain retriever as a tool:

```python
from langchain_core.tools import create_retriever_tool
from voicestack.tools.plugins import voice_tool

retriever = my_vectorstore.as_retriever(search_kwargs={"k": 4})
voice_tool(create_retriever_tool(retriever, "search_policies", "Search company policies."))
```

## Connect a remote service without code

If the service speaks MCP, add it under Integrations → MCP servers. If it is a REST API, add an HTTP tool. Neither needs a deploy.

## React to conversations

- **Live events:** subscribe to `wss://<host>/api/live/ws?conversation_id=*`. You receive `session.started`, `agent.active`, `turn`, `tool.started`, `tool.finished`, `handoff`, `dtmf`, `summary.ready`, and `session.ended`.
- **After the call:** read `GET /api/conversations/{id}` for turns and the summary, and `GET /api/conversations/{id}/state` for the LangGraph state.
- **In process:** the final step of a call is the `post_call` node in `runtime/graph.py`. Add a node after it, for example to write to a CRM, or subscribe to `runtime.bus.bus` in a startup hook.

## Route calls your way

`telephony/calls.py:accept_webhook` picks the entry agent from the dialed number. To route on SIP headers, the caller's number, or business hours, change the `entry_agent_id` decision there. Everything after it uses the chosen agent.

## Change how agents are compiled

- **Instructions:** `prompting/compiler.py`.
- **The rest of `session.update`:** `runtime/session_config.py`. Fields xAI adds later (for example, new transcription options) go here.
- **Handoff semantics:** the agent node in `runtime/graph.py`. One example is requiring a confirmation turn before transferring.

## Manage everything as code

`voicestack export -o landscape.yaml` and `voicestack apply -f landscape.yaml` round-trip agents, handoffs, tools, MCP servers, knowledge-base definitions, and transfer lines. Keep the file in git and apply it in CI.

## API

FastAPI serves OpenAPI at `/docs` (Swagger) and `/openapi.json`. Every UI action is an API call, so anything in the builder can be scripted.
