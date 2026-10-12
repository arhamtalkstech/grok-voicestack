<!-- Source: https://docs.x.ai/developers/tools/x-search (markdown: https://docs.x.ai/developers/tools/x-search.md), fetched 2026-10-12. Do not edit; re-run fetch.sh. -->

#### Tools

# X Search

The X Search tool enables Grok to perform keyword search, semantic search, user search, and thread fetch on X (formerly Twitter). This powerful tool allows the model to access real-time social media content, analyze posts, and gather insights from X's vast data.

X Search is billed at $5 per 1k posts fetched and $10 per 1k user profiles fetched, in addition to token costs; see [tool invocation costs](https://docs.x.ai/developers/pricing#tool-invocation-costs) for what counts as a fetched post or profile.

## SDK Support

| SDK/API | Tool Name |
|---------|-----------|
| Responses API | `x_search` |
| Vercel AI SDK | `xai.tools.xSearch()` |

This tool is also supported in all Responses API compatible SDKs.

## Basic Usage

```javascriptAISDK
import { xai } from '@ai-sdk/xai';
import { generateText } from 'ai';

const { text, sources } = await generateText({
  model: xai.responses('grok-4.7'),
  prompt: 'What are people saying about SpaceXAI on X?',
  tools: {
    x_search: xai.tools.xSearch(),
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
            "content": "What are people saying about SpaceXAI on X?",
        },
    ],
    tools=[
        {
            "type": "x_search",
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
      "content": "What are people saying about SpaceXAI on X?"
    }
  ],
  "tools": [
    {
      "type": "x_search"
    }
  ]
}'
```

## X Search Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `allowed_x_handles` | array of strings | Only consider posts from these handles, written without the `@` (max 20; 10 in the Vercel AI SDK) |
| `excluded_x_handles` | array of strings | Ignore posts from these handles, written without the `@` (max 20; 10 in the Vercel AI SDK) |
| `from_date` | string | Start of the [date range](#date-range) (`YYYY-MM-DD`) |
| `to_date` | string | End of the [date range](#date-range) (`YYYY-MM-DD`) |
| `enable_image_understanding` | boolean | Let the model look at images in the posts it finds. Defaults to `false`. |
| `enable_video_understanding` | boolean | Let the model watch videos in the posts it finds. Defaults to `false`. |

### Only Consider Posts from Specific Handles

Use `allowed_x_handles` to consider X posts only from a given list of X handles.

> [!NOTE]
>
> `allowed_x_handles` cannot be set together with `excluded_x_handles` in the same request.

```javascriptAISDK
const { text } = await generateText({
  model: xai.responses('grok-4.7'),
  prompt: 'What has SpaceX posted about Starship recently?',
  tools: {
    x_search: xai.tools.xSearch({
      allowedXHandles: ['SpaceX'],
    }),
  },
});
```

```pythonOpenAISDK
response = client.responses.create(
    model="grok-4.7",
    input=[{"role": "user", "content": "What has SpaceX posted about Starship recently?"}],
    tools=[
        {
            "type": "x_search",
            "allowed_x_handles": ["SpaceX"],
        },
    ],
)
```

### Exclude Posts from Specific Handles

Use `excluded_x_handles` to prevent the model from including X posts from the specified handles in any X search tool invocations.

```javascriptAISDK
const { text } = await generateText({
  model: xai.responses('grok-4.7'),
  prompt: 'How are people reacting to the latest Tesla delivery numbers?',
  tools: {
    x_search: xai.tools.xSearch({
      excludedXHandles: ['Tesla'],
    }),
  },
});
```

```pythonOpenAISDK
response = client.responses.create(
    model="grok-4.7",
    input=[{"role": "user", "content": "How are people reacting to the latest Tesla delivery numbers?"}],
    tools=[
        {
            "type": "x_search",
            "excluded_x_handles": ["Tesla"],
        },
    ],
)
```

### Date Range

You can restrict the date range of search data used by specifying `from_date` and `to_date`. This limits the data to posts from 00:00 UTC on `from_date` up to, but not including, `to_date`. To search a single day, set `to_date` to the day after it.

Use `YYYY-MM-DD` for both fields, e.g., `"2026-09-28"`. Dates in any other format, including full date-times, aren't applied.

```javascriptAISDK
const { text } = await generateText({
  model: xai.responses('grok-4.7'),
  prompt: 'How did people react to the Starship launch?',
  tools: {
    x_search: xai.tools.xSearch({
      fromDate: '2026-09-28',
      toDate: '2026-10-01',
    }),
  },
});
```

```pythonOpenAISDK
response = client.responses.create(
    model="grok-4.7",
    input=[{"role": "user", "content": "How did people react to the Starship launch?"}],
    tools=[
        {
            "type": "x_search",
            "from_date": "2026-09-28",
            "to_date": "2026-10-01",
        },
    ],
)
```

### Enable Image Understanding

Setting `enable_image_understanding` to true allows the agent to analyze images in X posts encountered during the search process.

```javascriptAISDK
const { text } = await generateText({
  model: xai.responses('grok-4.7'),
  prompt: 'Find X posts with images about AI',
  tools: {
    x_search: xai.tools.xSearch({
      enableImageUnderstanding: true,
    }),
  },
});
```

```pythonOpenAISDK
response = client.responses.create(
    model="grok-4.7",
    input=[{"role": "user", "content": "Find X posts with images about AI"}],
    tools=[
        {
            "type": "x_search",
            "enable_image_understanding": True,
        },
    ],
)
```

### Enable Video Understanding

Setting `enable_video_understanding` to true allows the agent to analyze videos in X posts. This is only available for X Search (not Web Search).

```javascriptAISDK
const { text } = await generateText({
  model: xai.responses('grok-4.7'),
  prompt: 'Find X posts with videos about AI',
  tools: {
    x_search: xai.tools.xSearch({
      enableVideoUnderstanding: true,
    }),
  },
});
```

```pythonOpenAISDK
response = client.responses.create(
    model="grok-4.7",
    input=[{"role": "user", "content": "Find X posts with videos about AI"}],
    tools=[
        {
            "type": "x_search",
            "enable_video_understanding": True,
        },
    ],
)
```

## How X Search Works

When you add `x_search` to `tools`, the model decides which of the functions below to call, and how often. It reads the posts it fetches and answers with citations. Each call appears in the response output as a `custom_tool_call` item named after the function, and the response reports the [usage counts](#usage-counts).

| Function | What the model uses it for | Billed as |
|----------|----------------------------|-----------|
| `x_keyword_search` | Keyword search with X's advanced search operators, sorted by `Top` or `Latest` | Posts fetched |
| `x_semantic_search` | Search by meaning rather than exact words | Posts fetched |
| `x_user_search` | Find users by name or description | Profiles fetched |
| `x_thread_fetch` | Fetch one post with its parent posts and replies | Posts fetched |

With [image](#enable-image-understanding) or [video understanding](#enable-video-understanding) turned on, the model can also view images and videos in the posts it finds, billed as image tokens.

Your handle and date parameters apply to every keyword and semantic search, whatever query the model writes. Thread fetches don't use them.

## Examples

Outputs are abridged; results vary because the model picks its own queries.

### Keep Costs Down

To spend less, give the model less to fetch: narrow the handles and dates, ask for fewer rounds of searching with [`max_turns`](https://docs.x.ai/developers/tools/tool-usage-details#limiting-tool-call-turns), and check the fetch counts in the response.

```javascript customLanguage="javascriptAISDK"
import { xai } from '@ai-sdk/xai';
import { generateText } from 'ai';

const { response } = await generateText({
  model: xai.responses('grok-4.7'),
  prompt: 'What did SpaceX post about Starship in September 2026?',
  tools: { x_search: xai.tools.xSearch({ allowedXHandles: ['SpaceX'], fromDate: '2026-09-01', toDate: '2026-10-01' }) },
  providerOptions: { xai: { maxTurns: 2 } },
  include: { responseBody: true },
});

// response.body is the raw Responses API JSON.
const usage = Object(response.body).usage;
console.log(`x_posts_fetched: ${usage.server_side_tool_usage_details.x_posts_fetched}`);
console.log(`x_users_fetched: ${usage.server_side_tool_usage_details.x_users_fetched}`);
```

```python customLanguage="pythonOpenAISDK"
import os

from openai import OpenAI

client = OpenAI(api_key=os.getenv("XAI_API_KEY"), base_url="https://api.x.ai/v1")
response = client.responses.create(
    model="grok-4.7",
    input="What did SpaceX post about Starship in September 2026?",
    tools=[{"type": "x_search", "allowed_x_handles": ["SpaceX"], "from_date": "2026-09-01", "to_date": "2026-10-01"}],
    extra_body={"max_turns": 2},
)

usage = response.usage.model_dump()
details = usage["server_side_tool_usage_details"]
print(f"x_posts_fetched: {details['x_posts_fetched']}")
print(f"x_users_fetched: {details['x_users_fetched']}")
```

```bash customLanguage="bash"
curl -s https://api.x.ai/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $XAI_API_KEY" \
  -d '{
  "model": "grok-4.7",
  "input": "What did SpaceX post about Starship in September 2026?",
  "tools": [{"type": "x_search", "allowed_x_handles": ["SpaceX"], "from_date": "2026-09-01", "to_date": "2026-10-01"}],
  "max_turns": 2
}' | jq -r '.usage | "x_posts_fetched: \(.server_side_tool_usage_details.x_posts_fetched)", "x_users_fetched: \(.server_side_tool_usage_details.x_users_fetched)"'
```

```output
x_posts_fetched: 19
x_users_fetched: 0
```

## Usage Counts

Each Responses API response that ran X Search reports how many items it fetched, so you can reconcile a request against the per-item [pricing](https://docs.x.ai/developers/pricing#tool-invocation-costs) in effect as of September 21, 2026. The counts live under `usage.server_side_tool_usage_details`, next to the per-call `x_search_calls`:

| Field | Counts |
|-------|--------|
| `x_posts_fetched` | Posts returned by `x_keyword_search`, `x_semantic_search`, and `x_thread_fetch`, including parent and quoted posts and every post of a fetched thread |
| `x_users_fetched` | User profiles returned by `x_user_search` |

Both counts accumulate over every X Search call in the request and are not de-duplicated; a post returned by two searches counts twice. When streaming, the `usage` on the terminal event (`response.completed`, or `response.incomplete` when the response was truncated) is the total for the request.

The `server_side_tool_usage_details` block of a `/v1/responses` `usage` object after two X searches looks like this:

```json
"server_side_tool_usage_details": {
  "web_search_calls": 0,
  "x_search_calls": 2,
  "x_posts_fetched": 44,
  "x_users_fetched": 3,
  "code_interpreter_calls": 0,
  "file_search_calls": 0,
  "mcp_calls": 0,
  "document_search_calls": 0,
  "image_generation_calls": 0
}
```

## Citations

For details on how to retrieve and use citations from search results, see the [Citations](https://docs.x.ai/developers/tools/citations) page.
