<!-- Source: https://docs.x.ai/developers/tools/function-calling (markdown: https://docs.x.ai/developers/tools/function-calling.md), fetched 2026-10-12. Do not edit; re-run fetch.sh. -->

#### Tools

# Function Calling

Define custom tools that the model can invoke during a conversation. The model requests the call, you execute it locally, and return the result. This enables integration with databases, APIs, and any external system.

> [!WARNING]
>
> With streaming, the function call is returned in whole in a single chunk, not streamed across chunks.

1. Define tools with a name, description, and JSON schema for parameters
2. Include tools in your request
3. Model returns a `tool_call` when it needs external data
4. Execute the function locally and return the result
5. Model continues with your result

## Quick Start

```javascriptAISDK
import { xai } from '@ai-sdk/xai';
import { streamText, tool, stepCountIs } from 'ai';
import { z } from 'zod';

const result = streamText({
  model: xai.responses('grok-4.7'),
  tools: {
    getTemperature: tool({
      description: 'Get current temperature for a location',
      inputSchema: z.object({
        location: z.string().describe('City name'),
        unit: z.enum(['celsius', 'fahrenheit']).default('fahrenheit'),
      }),
      execute: async ({ location, unit }) => ({
        location,
        temperature: unit === 'fahrenheit' ? 59 : 15,
        unit,
      }),
    }),
  },
  stopWhen: stepCountIs(5),
  prompt: 'What is the temperature in San Francisco?',
});

for await (const chunk of result.fullStream) {
  if (chunk.type === 'text-delta') {
    process.stdout.write(chunk.text);
  }
}
```

```pythonOpenAISDK
import os
import json
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
)

tools = [
    {
        "type": "function",
        "name": "get_temperature",
        "description": "Get current temperature for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "fahrenheit"}
            },
            "required": ["location"]
        },
    },
]

response = client.responses.create(
    model="grok-4.7",
    input=[{"role": "user", "content": "What is the temperature in San Francisco?"}],
    tools=tools,
)

# Handle function calls
for item in response.output:
    if item.type == "function_call":
        args = json.loads(item.arguments)
        result = {"location": args["location"], "temperature": 59, "unit": args.get("unit", "fahrenheit")}

        response = client.responses.create(
            model="grok-4.7",
            input=[{"type": "function_call_output", "call_id": item.call_id, "output": json.dumps(result)}],
            tools=tools,
            previous_response_id=response.id,
        )

for item in response.output:
    if item.type == "message":
        print(item.content[0].text)
```

```bash customLanguage="bash"
curl https://api.x.ai/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -d '{
  "model": "grok-4.7",
  "input": [
    {"role": "user", "content": "What is the temperature in San Francisco?"}
  ],
  "tools": [
    {
      "type": "function",
      "name": "get_temperature",
      "description": "Get current temperature for a location",
      "parameters": {
        "type": "object",
        "properties": {
          "location": {"type": "string", "description": "City name"},
          "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "fahrenheit"}
        },
        "required": ["location"]
      }
    }
  ]
}'
```

```pythonXAI
import os
import json

from xai_sdk import Client
from xai_sdk.chat import user, tool, tool_result

client = Client(api_key=os.getenv("XAI_API_KEY"))

# Define tools
tools = [
    tool(
        name="get_temperature",
        description="Get current temperature for a location",
        parameters={
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "fahrenheit"}
            },
            "required": ["location"]
        },
    ),
]

chat = client.chat.create(
    model="grok-4.7",
    tools=tools,
)
chat.append(user("What is the temperature in San Francisco?"))
response = chat.sample()

# Handle tool calls
if response.tool_calls:
    chat.append(response)
    for tc in response.tool_calls:
        args = json.loads(tc.function.arguments)
        # Execute your function
        result = {"location": args["location"], "temperature": 59, "unit": args.get("unit", "fahrenheit")}
        chat.append(tool_result(json.dumps(result)))

    response = chat.sample()

print(response.content)
```

## Defining Tools with Pydantic

Use Pydantic models for type-safe parameter schemas:

```pythonOpenAISDK
from typing import Literal
from pydantic import BaseModel, Field

class TemperatureRequest(BaseModel):
    location: str = Field(description="City and state, e.g. San Francisco, CA")
    unit: Literal["celsius", "fahrenheit"] = Field("fahrenheit", description="Temperature unit")

class CeilingRequest(BaseModel):
    location: str = Field(description="City and state, e.g. San Francisco, CA")

tools = [
    {
        "type": "function",
        "name": "get_temperature",
        "description": "Get current temperature for a location",
        "parameters": TemperatureRequest.model_json_schema(),
    },
    {
        "type": "function",
        "name": "get_ceiling",
        "description": "Get current cloud ceiling for a location",
        "parameters": CeilingRequest.model_json_schema(),
    },
]
```

```pythonXAI
from typing import Literal
from pydantic import BaseModel, Field
from xai_sdk.chat import tool

class TemperatureRequest(BaseModel):
    location: str = Field(description="City and state, e.g. San Francisco, CA")
    unit: Literal["celsius", "fahrenheit"] = Field("fahrenheit", description="Temperature unit")

class CeilingRequest(BaseModel):
    location: str = Field(description="City and state, e.g. San Francisco, CA")

# Generate JSON schema from Pydantic models
tools = [
    tool(
        name="get_temperature",
        description="Get current temperature for a location",
        parameters=TemperatureRequest.model_json_schema(),
    ),
    tool(
        name="get_ceiling",
        description="Get current cloud ceiling for a location",
        parameters=CeilingRequest.model_json_schema(),
    ),
]
```

## Handling Tool Calls

When the model wants to use your tool, execute the function and return the result:

```pythonOpenAISDK
import json

def get_temperature(location: str, unit: str = "fahrenheit") -> dict:
    temp = 59 if unit == "fahrenheit" else 15
    return {"location": location, "temperature": temp, "unit": unit}

tools_map = {"get_temperature": get_temperature}

# Process function calls
for item in response.output:
    if item.type == "function_call":
        name = item.name
        args = json.loads(item.arguments)

        if name not in tools_map:
            output = json.dumps({"error": f"Unknown function: {name}"})
        else:
            output = json.dumps(tools_map[name](**args))

        response = client.responses.create(
            model="grok-4.7",
            input=[{"type": "function_call_output", "call_id": item.call_id, "output": output}],
            tools=tools,
            previous_response_id=response.id,
        )

for item in response.output:
    if item.type == "message":
        print(item.content[0].text)
```

```pythonXAI
import json

def get_temperature(location: str, unit: str = "fahrenheit") -> dict:
    # In production, call a real weather API
    temp = 59 if unit == "fahrenheit" else 15
    return {"location": location, "temperature": temp, "unit": unit}

def get_ceiling(location: str) -> dict:
    return {"location": location, "ceiling": 15000, "unit": "ft"}

tools_map = {
    "get_temperature": get_temperature,
    "get_ceiling": get_ceiling,
}

chat.append(user("What's the weather in Denver?"))
response = chat.sample()

# Process tool calls
if response.tool_calls:
    chat.append(response)

    for tool_call in response.tool_calls:
        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        result = tools_map[name](**args)
        chat.append(tool_result(json.dumps(result)))

    response = chat.sample()

print(response.content)
```

## Combining with Built-in Tools

Function calling works alongside built-in agentic tools. The model can use web search, then call your custom function:

```pythonOpenAISDK
tools = [
    {"type": "web_search"},          # Built-in
    {"type": "x_search"},            # Built-in
    {                                # Custom
        "type": "function",
        "name": "save_to_database",
        "description": "Save research results to the database",
        "parameters": {
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "Data to save"}
            },
            "required": ["data"]
        },
    },
]
```

```pythonXAI
from xai_sdk.chat import tool
from xai_sdk.tools import web_search, x_search

tools = [
    web_search(),                    # Built-in: runs on xAI servers
    x_search(),                      # Built-in: runs on xAI servers
    tool(                            # Custom: runs on your side
        name="save_to_database",
        description="Save research results to the database",
        parameters={
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "Data to save"}
            },
            "required": ["data"]
        },
    ),
]

chat = client.chat.create(
    model="grok-4.7",
    tools=tools,
)
```

When mixing tools:

* **Built-in tools** execute automatically on SpaceXAI servers
* **Custom tools** pause execution and return to you for handling

See [Advanced Usage](https://docs.x.ai/developers/tools/advanced-usage#mixing-server-side-and-client-side-tools) for complete examples with tool loops.

## Tool Choice

Control when the model uses tools:

| Value | Behavior |
|-------|----------|
| `"auto"` | Model decides whether to call a tool (default) |
| `"required"` | Model must call at least one tool |
| `"none"` | Disable tool calling |
| `{"type": "function", "function": {"name": "..."}}` | Force a specific tool |

## Parallel Function Calling

By default, parallel function calling is enabled — the model can request multiple tool calls in a single response. Process all of them before continuing:

```pythonWithoutSDK
# response.tool_calls may contain multiple calls
for tool_call in response.tool_calls:
    result = tools_map[tool_call.function.name](**json.loads(tool_call.function.arguments))
    # Append each result...
```

Disable with `parallel_tool_calls: false` in your request.

## Tool Schema Reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique identifier (max 350 tools per request) |
| `description` | No | What the tool does. Treated as empty if omitted; a clear description helps the model decide when to use it |
| `parameters` | Yes | JSON Schema defining function inputs |

### Parameter Schema

```json
{
  "type": "object",
  "properties": {
    "location": {
      "type": "string",
      "description": "City name"
    },
    "unit": {
      "type": "string",
      "enum": ["celsius", "fahrenheit"],
      "default": "celsius"
    }
  },
  "required": ["location"]
}
```

The root of a `parameters` schema must be an object (`"type": "object"`); nest any other types inside `properties`. A root `anyOf` or `oneOf` also works when every branch is itself an object, letting you define a tool that accepts one of several object variants:

```json
{
  "oneOf": [
    {
      "type": "object",
      "properties": {
        "kind": { "const": "email" },
        "address": { "type": "string" }
      },
      "required": ["kind", "address"]
    },
    {
      "type": "object",
      "properties": {
        "kind": { "const": "sms" },
        "phone": { "type": "string" }
      },
      "required": ["kind", "phone"]
    }
  ]
}
```

> [!WARNING]
>
> A tool whose `parameters` root is neither an object nor a union of objects (for example, a scalar, an array, or an `anyOf`/`oneOf` with a non-object branch) cannot be compiled into a tool-call grammar and is rejected with a `400` error that names the tool.

## Complete Vercel AI SDK Example

The Vercel AI SDK handles tool definition, execution, and the request/response loop automatically:

```javascriptAISDK
import { xai } from '@ai-sdk/xai';
import { streamText, tool, stepCountIs } from 'ai';
import { z } from 'zod';

const result = streamText({
  model: xai.responses('grok-4.7'),
  tools: {
    getCurrentTemperature: tool({
      description: 'Get current temperature for a location',
      inputSchema: z.object({
        location: z.string().describe('City and state, e.g. San Francisco, CA'),
        unit: z.enum(['celsius', 'fahrenheit']).default('fahrenheit'),
      }),
      execute: async ({ location, unit }) => ({
        location,
        temperature: unit === 'fahrenheit' ? 59 : 15,
        unit,
      }),
    }),
    getCurrentCeiling: tool({
      description: 'Get current cloud ceiling for a location',
      inputSchema: z.object({
        location: z.string().describe('City and state'),
      }),
      execute: async ({ location }) => ({
        location,
        ceiling: 15000,
        ceiling_type: 'broken',
        unit: 'ft',
      }),
    }),
  },
  stopWhen: stepCountIs(5),
  prompt: "What's the temperature and cloud ceiling in San Francisco?",
});

for await (const chunk of result.fullStream) {
  switch (chunk.type) {
    case 'text-delta':
      process.stdout.write(chunk.text);
      break;
    case 'tool-call':
      console.log(`Tool call: ${chunk.toolName}`, chunk.input);
      break;
    case 'tool-result':
      console.log(`Tool result: ${chunk.toolName}`, chunk.output);
      break;
  }
}
```
