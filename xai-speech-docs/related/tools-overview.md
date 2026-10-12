<!-- Source: https://docs.x.ai/developers/tools/overview (markdown: https://docs.x.ai/developers/tools/overview.md), fetched 2026-10-12. Do not edit; re-run fetch.sh. -->

#### Tools

# Overview

The xAI API supports **tool calling**, enabling Grok to perform actions beyond generating text—like searching the web, executing code, querying your data, or calling your own custom functions. Tools extend what's possible with the API and let you build powerful, interactive applications.

## Types of Tools

The xAI API offers two categories of tools:

| Type | Description | Examples |
|------|-------------|----------|
| **Built-in Tools** | Server-side tools managed by SpaceXAI that execute automatically | Web Search, X Search, Code Interpreter, Image Generation, Collections Search |
| **Function Calling** | Custom functions you define that the model can invoke | Database queries, API calls, custom business logic |

Built-in tools run on SpaceXAI's servers—you provide the tool configuration, and the API handles execution and returns results. Function calling lets you define your own tools that the model can request, giving you full control over what happens when they're invoked.

## Pricing

Tool requests are priced based on two components: **token usage** and **tool invocations**. Since the model may call multiple tools to answer a query, costs scale with complexity.

For more details on Tools pricing, please check out [the pricing page](https://docs.x.ai/developers/pricing#tools-pricing).

## How It Works

When you provide tools to a request, the xAI API can use them to gather information or perform actions:

1. **Analyzes the query** and determines what information or actions are needed
2. **Decides what to do next**: Make a tool call, or provide a final answer
3. **Executes the tool** (for built-in tools) or returns a tool call request (for function calling)
4. **Processes results** and continues until sufficient information is gathered
5. **Returns the final response** with citations where applicable

## Quick Start

```javascriptAISDK
import { xai } from '@ai-sdk/xai';
import { streamText } from 'ai';

const { fullStream } = streamText({
  model: xai.responses('grok-4.7'),
  prompt: 'What are the latest updates from xAI?',
  tools: {
    web_search: xai.tools.webSearch(),
    x_search: xai.tools.xSearch(),
    code_execution: xai.tools.codeExecution(),
  },
});

for await (const part of fullStream) {
  if (part.type === 'text-delta') {
    process.stdout.write(part.text);
  } else if (part.type === 'source' && part.sourceType === 'url') {
    console.log(`Citation: ${part.url}`);
  }
}
```

```pythonOpenAISDK
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
)

response = client.responses.create(
    model="grok-4.7",
    input=[
        {"role": "user", "content": "What are the latest updates from xAI?"}
    ],
    tools=[
        {"type": "web_search"},
        {"type": "x_search"},
        {"type": "code_interpreter"},
    ],
    stream=True,
)

for event in response:
    if event.type == "response.output_text.delta":
        print(event.delta, end="", flush=True)
```

```bash customLanguage="bash"
curl https://api.x.ai/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -d '{
  "model": "grok-4.7",
  "stream": true,
  "input": [
    {
      "role": "user",
      "content": "What are the latest updates from xAI?"
    }
  ],
  "tools": [
    { "type": "web_search" },
    { "type": "x_search" },
    { "type": "code_interpreter" }
  ]
}'
```

```javascriptOpenAISDK
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.XAI_API_KEY,
  baseURL: "https://api.x.ai/v1",
});

const stream = await client.responses.create({
  model: "grok-4.7",
  input: [
    { role: "user", content: "What are the latest updates from xAI?" }
  ],
  tools: [
    { type: "web_search" },
    { type: "x_search" },
    { type: "code_interpreter" },
  ],
  stream: true,
});

for await (const event of stream) {
  if (event.type === "response.output_text.delta") {
    process.stdout.write(event.delta);
  }
}
```

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search, x_search, code_execution

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4.7",
    tools=[
        web_search(),
        x_search(),
        code_execution(),
    ],
)

chat.append(user("What are the latest updates from xAI?"))

for response, chunk in chat.stream():
    if chunk.content:
        print(chunk.content, end="", flush=True)

print("\nCitations:", response.citations)
```

## Citations

The API automatically returns source URLs for information gathered via tools. See [Citations](https://docs.x.ai/developers/tools/citations) for details on accessing and using citation data.

## Next Steps

* **[Function Calling](https://docs.x.ai/developers/tools/function-calling)** - Define custom tools the model can call
* **[Web Search](https://docs.x.ai/developers/tools/web-search)** - Search the web and browse pages
* **[X Search](https://docs.x.ai/developers/tools/x-search)** - Search X posts, users, and threads
* **[Code Execution](https://docs.x.ai/developers/tools/code-execution)** - Execute Python code in a sandbox
* **[Image Generation](https://docs.x.ai/developers/tools/image-generation)** - Generate and edit images in a conversation
* **[Collections Search](https://docs.x.ai/developers/tools/collections-search)** - Query your uploaded documents
* **[Citations](https://docs.x.ai/developers/tools/citations)** - Access source URLs and inline citations
