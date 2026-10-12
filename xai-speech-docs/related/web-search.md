<!-- Source: https://docs.x.ai/developers/tools/web-search (markdown: https://docs.x.ai/developers/tools/web-search.md), fetched 2026-10-12. Do not edit; re-run fetch.sh. -->

#### Tools

# Web Search

The Web Search tool enables Grok to search the web in real-time and browse web pages to find information. This powerful tool allows the model to search the internet, access web pages, and extract relevant information to answer queries with up-to-date content.

## SDK Support

| SDK/API | Tool Name |
|---------|-----------|
| xAI SDK | `web_search` |
| OpenAI Responses API | `web_search` |
| Vercel AI SDK | `xai.tools.webSearch()` |

This tool is also supported in all Responses API compatible SDKs.

## Basic Usage

```javascriptAISDK
import { xai } from '@ai-sdk/xai';
import { generateText } from 'ai';

const { text, sources } = await generateText({
  model: xai.responses('grok-4.7'),
  prompt: 'What is xAI?',
  tools: {
    web_search: xai.tools.webSearch(),
  },
});

console.log(text);
console.log('Citations:', sources);
```

```pythonOpenAISDK
import os
from openai import OpenAI

api_key = os.getenv("XAI_API_KEY")
client = OpenAI(
    api_key=api_key,
    base_url="https://api.x.ai/v1",
)

response = client.responses.create(
    model="grok-4.7",
    input=[
        {
            "role": "user",
            "content": "What is xAI?",
        },
    ],
    tools=[
        {
            "type": "web_search",
        },
    ],
)

print(response)
```

```bash
curl https://api.x.ai/v1/responses \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer $XAI_API_KEY" \\
  -d '{
  "model": "grok-4.7",
  "input": [
    {
      "role": "user",
      "content": "What is xAI?"
    }
  ],
  "tools": [
    {
      "type": "web_search"
    }
  ]
}'
```

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4.7",  # reasoning model
    tools=[web_search()],
    include=["verbose_streaming"],
)

chat.append(user("What is xAI?"))

is_thinking = True
for response, chunk in chat.stream():
    for tool_call in chunk.tool_calls:
        print(f"\\nCalling tool: {tool_call.function.name} with arguments: {tool_call.function.arguments}")
    if response.usage.reasoning_tokens and is_thinking:
        print(f"\\rThinking... ({response.usage.reasoning_tokens} tokens)", end="", flush=True)
    if chunk.content and is_thinking:
        print("\\n\\nFinal Response:")
        is_thinking = False
    if chunk.content and not is_thinking:
        print(chunk.content, end="", flush=True)

print("\\n\\nCitations:")
print(response.citations)
```

## Web Search Parameters

| Parameter | Description |
|-----------|-------------|
| `allowed_domains` | Only search within specific domains (max 5) |
| `excluded_domains` | Exclude specific domains from search (max 5) |
| `enable_image_understanding` | Enable analysis of images found during browsing |
| `enable_image_search` | Enable image search results that can be embedded in responses |

### Only Search in Specific Domains

Use `allowed_domains` to make the web search **only** perform the search and web browsing on web pages that fall within the specified domains.

> [!NOTE]
>
> `allowed_domains` cannot be set together with `excluded_domains` in the same request.

```javascriptAISDK
const { text } = await generateText({
  model: xai.responses('grok-4.7'),
  prompt: 'What is xAI?',
  tools: {
    web_search: xai.tools.webSearch({
      allowedDomains: ['grokipedia.com'],
    }),
  },
});
```

```pythonOpenAISDK
response = client.responses.create(
    model="grok-4.7",
    input=[{"role": "user", "content": "What is xAI?"}],
    tools=[
        {
            "type": "web_search",
            "filters": {"allowed_domains": ["grokipedia.com"]},
        },
    ],
)
```

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4.7",
    tools=[
        web_search(allowed_domains=["grokipedia.com"]),
    ],
)

chat.append(user("What is xAI?"))
# stream or sample the response...
```

### Exclude Specific Domains

Use `excluded_domains` to prevent the model from including the specified domains in any web search tool invocations.

```pythonOpenAISDK
response = client.responses.create(
    model="grok-4.7",
    input=[{"role": "user", "content": "What is xAI?"}],
    tools=[
        {
            "type": "web_search",
            "filters": {"excluded_domains": ["grokipedia.com"]},
        },
    ],
)
```

```pythonXAI
chat = client.chat.create(
    model="grok-4.7",
    tools=[
        web_search(excluded_domains=["grokipedia.com"]),
    ],
)
```

### Enable Image Understanding

Setting `enable_image_understanding` to true equips the agent with access to the `view_image` tool, allowing it to analyze images encountered during the search process.

When enabled, you will see `SERVER_SIDE_TOOL_VIEW_IMAGE` in `response.server_side_tool_usage` along with the number of times it was called.

> [!NOTE]
>
> Enabling this parameter for Web Search will also enable the image understanding for X Search tool if it's also included in the request.

```javascriptAISDK
const { text } = await generateText({
  model: xai.responses('grok-4.7'),
  prompt: "What is included in the image in xAI's official website?",
  tools: {
    web_search: xai.tools.webSearch({
      enableImageUnderstanding: true,
    }),
  },
});
```

```pythonOpenAISDK
response = client.responses.create(
    model="grok-4.7",
    input=[
        {
            "role": "user",
            "content": "What is included in the image in xAI's official website?",
        },
    ],
    tools=[
        {
            "type": "web_search",
            "enable_image_understanding": True,
        },
    ],
)
```

```pythonXAI
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4.7",
    tools=[
        web_search(enable_image_understanding=True),
    ],
)

chat.append(user("What is included in the image in xAI's official website?"))
# stream or sample the response...
```

### Enable Image Search

Setting `enable_image_search` to true lets Grok search for relevant images and include them in the response as Markdown image embeds such as `![alt](url)`.

> [!NOTE]
>
> After Grok searches for images, the returned images are included in the model context used to write the response. This is separate from `enable_image_understanding`, which lets Grok inspect images it finds while browsing regular web pages.

The Vercel AI SDK does not yet expose `enableImageSearch`; the examples below use the Responses API and xAI Python SDK.

```python customLanguage="pythonOpenAISDK"
response = client.responses.create(
    model="grok-4.7",
    input=[
        {
            "role": "user",
            "content": "Show me images of Starship on the launch pad.",
        },
    ],
    tools=[
        {
            "type": "web_search",
            "enable_image_search": True,
        },
    ],
)

print(response)
```

```bash customLanguage="bash"
curl https://api.x.ai/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -d '{
  "model": "grok-4.7",
  "input": [
    {
      "role": "user",
      "content": "Show me images of Starship on the launch pad."
    }
  ],
  "tools": [
    {
      "type": "web_search",
      "enable_image_search": true
    }
  ]
}'
```

```python customLanguage="pythonXAI"
import os

from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import web_search

client = Client(api_key=os.getenv("XAI_API_KEY"))
chat = client.chat.create(
    model="grok-4.7",
    tools=[
        web_search(enable_image_search=True),
    ],
)

chat.append(user("Show me images of Starship on the launch pad."))
response = chat.sample()
print(response.content)
print(response.server_side_tool_usage)
```

A response can include Markdown image embeds directly in the output text:

```output
![Why the SpaceX Starship launch pad matters](https://www.astronomy.com/wp-content/uploads/2024/09/starship-test-flight-mission-scaled.jpg)

Here are several high-quality images of SpaceX's Starship on the launch pad at Starbase in Boca Chica, Texas.
```

In the xAI SDK, successful image search executions appear in `response.server_side_tool_usage` as `SERVER_SIDE_TOOL_IMAGE_SEARCH`.

## Citations

For details on how to retrieve and use citations from search results, see the [Citations](https://docs.x.ai/developers/tools/citations) page.
