<!-- Source: https://docs.x.ai/developers/rate-limits (markdown: https://docs.x.ai/developers/rate-limits.md), fetched 2026-10-12. Do not edit; re-run fetch.sh. -->

#### Key Information

# Rate Limits

Every xAI API team has per-model rate limits on two dimensions: **requests per second (RPS)** and **tokens per minute (TPM)**. Your per-second limit is derived from your per-minute request budget (RPM / 48, with a minimum of 2): you cannot spend a full minute's requests in a single second, which protects the API from sudden bursts. These limits scale with your team's **tier**, which is determined by cumulative spend on the API.

You can view your team's current tier and per-model limits on the [Models](https://console.x.ai/team/default/models?utm_source=docs\&utm_medium=referral\&utm_campaign=developers-rate-limits\&utm_content=models) page in the xAI Console.

## Rate limit tiers

Your tier is based on cumulative spend on the xAI API since January 1, 2026. Tiers unlock automatically as your spend increases.

| Tier | Spend threshold |
| ---- | --------------- |
| Tier 0 | $0 (default) |
| Tier 1 | $50 |
| Tier 2 | $250 |
| Tier 3 | $1,000 |
| Tier 4 | $5,000 |
| Enterprise | Available on request |

Qualification is based on total revenue received through prepaid credit purchases or successfully fulfilled invoices. Once you qualify for a tier, you stay there permanently; tiers never downgrade.

> [!NOTE]
>
> Rate limit tiers apply to text, embedding, and voice models. For increases to Imagine API limits, contact [sales@x.ai](mailto:sales@x.ai).

## Per-model limits

Each tier sets hard RPS and TPM caps per model. Limits scale exponentially with tier. Exceeding any limit returns a `429 Too Many Requests` error.

The table below lists RPS and TPM limits at each tier for every model. Voice & Audio endpoints follow, limited by requests per second and concurrent sessions (CST) rather than tokens; Speech to Speech is limited by concurrent sessions alone. You can also view your team's personalized limits on the [Models](https://console.x.ai/team/default/models?utm_source=docs\&utm_medium=referral\&utm_campaign=developers-rate-limits\&utm_content=models) page in the xAI Console.

| Model | RPS | TPM |
| --- | --- | --- |
| grok-4.7 | T0: 150, T1: 172, T2: 208, T3: 312, T4: 500 | T0: 50M, T1: 53M, T2: 60M, T3: 74M, T4: 100M |
| grok-4.6 | T0: 150, T1: 172, T2: 208, T3: 312, T4: 500 | T0: 50M, T1: 53M, T2: 60M, T3: 74M, T4: 100M |
| grok-4.5 | T0: 150, T1: 172, T2: 208, T3: 312, T4: 500 | T0: 50M, T1: 53M, T2: 60M, T3: 74M, T4: 100M |
| grok-4.3 | T0: 37, T1: 50, T2: 75, T3: 125, T4: 208 | T0: 10M, T1: 15M, T2: 25M, T3: 45M, T4: 85M |
| grok-4.20-0309-reasoning | T0: 37, T1: 50, T2: 75, T3: 125, T4: 208 | T0: 10M, T1: 15M, T2: 25M, T3: 45M, T4: 85M |
| grok-4.20-0309-non-reasoning | T0: 37, T1: 50, T2: 75, T3: 125, T4: 208 | T0: 10M, T1: 15M, T2: 25M, T3: 45M, T4: 85M |
| grok-build-0.1 | T0: 37, T1: 50, T2: 75, T3: 125, T4: 208 | T0: 10M, T1: 15M, T2: 25M, T3: 45M, T4: 85M |
| grok-4.20-multi-agent-0309 | T0: 9, T1: 12, T2: 18, T3: 31, T4: 56 | T0: 2.5M, T1: 3.7M, T2: 6.2M, T3: 11M, T4: 21M |
| grok-imagine-image-quality | T0: 6, T1: 12, T2: 25, T3: 50, T4: 100 | — |
| grok-imagine-image-2.0 | T0: 6, T1: 12, T2: 25, T3: 50, T4: 100 | — |
| grok-imagine-image | T0: 6, T1: 12, T2: 25, T3: 50, T4: 100 | — |
| grok-imagine-video-1.5 | T0: 10, T1: 20, T2: 39, T3: 79, T4: 158 | — |
| grok-imagine-video | T0: 10, T1: 20, T2: 39, T3: 79, T4: 158 | — |
| grok-imagine-video-1.5-lite | T0: 10, T1: 20, T2: 39, T3: 79, T4: 158 | — |

**Voice & Audio**

| Model | RPS | Concurrent sessions |
| --- | --- | --- |
| grok-voice-think-fast-2.0 | — | T0: 10, T1: 20, T2: 50, T3: 100, T4: 200 |
| Text to Speech | T0: 50, T1: 50, T2: 100, T3: 250, T4: 500 | T0: 100, T1: 200, T2: 200, T3: 300, T4: 500 |
| Speech to Text | T0: 10, T1: 10, T2: 20, T3: 30, T4: 40 | T0: 100, T1: 200, T2: 200, T3: 300, T4: 500 |

### What counts toward TPM

All tokens consumed by a request count toward the TPM limit for that model:

* **Prompt tokens** (text, image, and audio)
* **Completion tokens**
* **Reasoning tokens** (on reasoning models)
* **Cached prompt tokens** (still count toward TPM, though they are billed at a reduced rate)

For details on how tokens are counted and priced, see [Models and Pricing](https://docs.x.ai/developers/models). For per-request cost tracking, see [Cost Tracking](https://docs.x.ai/developers/cost-tracking).

## Handling rate limit errors

When you exceed your rate limit, the API returns HTTP `429`. Implement exponential backoff to handle this gracefully:

```python customLanguage="pythonOpenAISDK"
import os
import time
from openai import OpenAI, RateLimitError

client = OpenAI(base_url="https://api.x.ai/v1", api_key=os.getenv("XAI_API_KEY"))

def request_with_backoff(messages, max_retries=5):
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(
                model="grok-4.7",
                messages=messages,
            )
        except RateLimitError:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            time.sleep(wait)
```

```python customLanguage="pythonXAI"
import os
import time
import grpc
from xai_sdk import Client
from xai_sdk.chat import user

client = Client(api_key=os.getenv("XAI_API_KEY"))

def request_with_backoff(prompt, max_retries=5):
    chat = client.chat.create(model="grok-4.7")
    chat.append(user(prompt))
    for attempt in range(max_retries):
        try:
            return chat.sample()
        except grpc.RpcError as e:
            if e.code() != grpc.StatusCode.RESOURCE_EXHAUSTED:
                raise
            wait = 2 ** attempt
            time.sleep(wait)
    raise RuntimeError("Max retries exceeded")
```

## Increasing your limits

* **Spend more.** Tiers upgrade automatically based on cumulative spend. No action required on your part.
* **Request an increase.** Submit a request through the [xAI Console](https://console.x.ai/team/default/models?utm_source=docs\&utm_medium=referral\&utm_campaign=developers-rate-limits\&utm_content=models) if you need higher limits without additional spend, or limits beyond Tier 4.
* **Contact sales.** For enterprise-grade capacity, please email [sales@x.ai](mailto:sales@x.ai).
