"""Resolved, immutable views of the landscape used by the runtime.

The database stores editable rows; the runtime works from these specs so a published version is a
single JSON snapshot that does not change when someone edits the draft.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field


class ContextField(BaseModel):
    name: str
    type: Literal["string", "number", "integer", "boolean"] = "string"
    description: str = ""
    required: bool = False


class EdgeSpec(BaseModel):
    id: str
    source_slug: str
    target_slug: str
    target_name: str
    description: str = ""
    context_fields: list[ContextField] = Field(default_factory=list)
    handoff_greeting: str = ""
    voice_policy: Literal["switch", "keep"] = "switch"

    @property
    def tool_name(self) -> str:
        return f"transfer_to_{self.target_slug.replace('-', '_')}"


class ToolSpec(BaseModel):
    id: str
    name: str
    kind: Literal["http", "plugin"] = "http"
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    preamble: str = ""
    requires_confirmation: bool = False


class McpSpec(BaseModel):
    id: str
    label: str
    description: str = ""
    mode: Literal["xai", "managed"] = "xai"
    transport: Literal["streamable_http", "sse", "stdio"] = "streamable_http"
    url: str = ""
    command: str = ""
    args: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    authorization_secret: str | None = None
    header_secrets: dict[str, str] = Field(default_factory=dict)


class KnowledgeSpec(BaseModel):
    id: str
    slug: str
    name: str
    description: str = ""
    mode: Literal["local", "collections"] = "local"
    collection_id: str | None = None
    top_k: int = 4


class TransferSpec(BaseModel):
    id: str
    name: str
    uri: str
    description: str = ""


class AgentSpec(BaseModel):
    id: str
    slug: str
    name: str
    description: str = ""
    prompt_mode: Literal["sections", "raw"] = "sections"
    prompt_sections: dict[str, str] = Field(default_factory=dict)
    raw_prompt: str = ""
    key_facts: str = ""
    greeting: str = ""
    greeting_mode: Literal["model", "verbatim", "none"] = "model"
    greeting_interruptible: bool = True
    voice_id: str = "eve"
    speed: float = 1.0
    reasoning_effort: Literal["high", "none"] = "high"
    language_hint: str | None = None
    keyterms: list[str] = Field(default_factory=list)
    replace_map: dict[str, str] = Field(default_factory=dict)
    idle_timeout_ms: int | None = None
    builtin_tools: dict[str, Any] = Field(default_factory=dict)
    allow_end_call: bool = True
    tools: list[ToolSpec] = Field(default_factory=list)
    mcps: list[McpSpec] = Field(default_factory=list)
    knowledge: list[KnowledgeSpec] = Field(default_factory=list)
    transfers: list[TransferSpec] = Field(default_factory=list)
    edges: list[EdgeSpec] = Field(default_factory=list)
    version: int | None = None

    def function_tool_names(self, channel: str = "web", managed_mcp_tools: list[str] | None = None) -> set[str]:
        """Names of function tools Voice Stack will attach (used by the linter and optimiser)."""
        names = {t.name for t in self.tools}
        names |= {e.tool_name for e in self.edges}
        if any(k.mode == "local" for k in self.knowledge):
            names.add("search_knowledge")
        if self.transfers:
            names.add("transfer_call")
        if self.allow_end_call:
            names.add("end_call")
        names |= set(managed_mcp_tools or [])
        return names

    def server_tool_names(self) -> set[str]:
        names: set[str] = set()
        for key in ("web_search", "x_search"):
            if (self.builtin_tools.get(key) or {}).get("enabled"):
                names.add(key)
        if any(k.mode == "collections" and k.collection_id for k in self.knowledge):
            names.add("file_search")
        for m in self.mcps:
            if m.mode == "xai":
                names |= set(m.allowed_tools)
        return names


class LandscapeSpec(BaseModel):
    agents: dict[str, AgentSpec]
    entry_slug: str | None = None

    def fingerprint(self) -> str:
        blob = json.dumps(self.model_dump(mode="json"), sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]
