from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Agent(TimestampMixin, Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("agt"))
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    # Prompt sections follow the xAI prompting guide; raw mode keeps a free-form prompt.
    prompt_mode: Mapped[str] = mapped_column(String(16), default="sections")
    prompt_sections: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    raw_prompt: Mapped[str] = mapped_column(Text, default="")
    key_facts: Mapped[str] = mapped_column(Text, default="")
    greeting: Mapped[str] = mapped_column(Text, default="")
    greeting_mode: Mapped[str] = mapped_column(String(16), default="model")  # model | verbatim | none
    greeting_interruptible: Mapped[bool] = mapped_column(Boolean, default=True)
    voice_id: Mapped[str] = mapped_column(String(64), default="eve")
    speed: Mapped[float] = mapped_column(Float, default=1.0)
    reasoning_effort: Mapped[str] = mapped_column(String(8), default="high")  # high | none
    language_hint: Mapped[str | None] = mapped_column(String(16), nullable=True)
    keyterms: Mapped[list[Any]] = mapped_column(JSON, default=list)
    replace_map: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    idle_timeout_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    builtin_tools: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    tool_ids: Mapped[list[Any]] = mapped_column(JSON, default=list)
    mcp_ids: Mapped[list[Any]] = mapped_column(JSON, default=list)
    knowledge_ids: Mapped[list[Any]] = mapped_column(JSON, default=list)
    transfer_target_ids: Mapped[list[Any]] = mapped_column(JSON, default=list)
    allow_end_call: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_entry: Mapped[bool] = mapped_column(Boolean, default=False)
    published_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AgentVersion(Base):
    __tablename__ = "agent_versions"
    __table_args__ = (UniqueConstraint("agent_id", "version"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("ver"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HandoffEdge(TimestampMixin, Base):
    __tablename__ = "handoff_edges"
    __table_args__ = (UniqueConstraint("source_id", "target_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("edg"))
    source_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    target_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    description: Mapped[str] = mapped_column(Text, default="")
    # [{name, type, description, required}] -> handoff tool parameters.
    context_fields: Mapped[list[Any]] = mapped_column(JSON, default=list)
    handoff_greeting: Mapped[str] = mapped_column(Text, default="")
    voice_policy: Mapped[str] = mapped_column(String(16), default="switch")  # switch | keep


class Tool(TimestampMixin, Base):
    __tablename__ = "tools"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("tool"))
    name: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(16), default="http")  # http | plugin
    description: Mapped[str] = mapped_column(Text, default="")
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    preamble: Mapped[str] = mapped_column(Text, default="")
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class McpServer(TimestampMixin, Base):
    __tablename__ = "mcp_servers"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("mcp"))
    label: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(16), default="xai")  # xai (hosted passthrough) | managed
    transport: Mapped[str] = mapped_column(String(24), default="streamable_http")  # streamable_http | sse | stdio
    url: Mapped[str] = mapped_column(Text, default="")
    command: Mapped[str] = mapped_column(Text, default="")
    args: Mapped[list[Any]] = mapped_column(JSON, default=list)
    allowed_tools: Mapped[list[Any]] = mapped_column(JSON, default=list)
    # Names of secrets in the secret store; values never live on this row.
    authorization_secret: Mapped[str | None] = mapped_column(String(120), nullable=True)
    header_secrets: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Secret(TimestampMixin, Base):
    __tablename__ = "secrets"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("sec"))
    name: Mapped[str] = mapped_column(String(120), unique=True)
    ciphertext: Mapped[str] = mapped_column(Text)
    last4: Mapped[str] = mapped_column(String(8), default="")


class Credential(TimestampMixin, Base):
    __tablename__ = "credentials"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)  # xai_api_key
    ciphertext: Mapped[str] = mapped_column(Text)
    last4: Mapped[str] = mapped_column(String(8))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KnowledgeBase(TimestampMixin, Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("kb"))
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(16), default="local")  # local | collections
    collection_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    top_k: Mapped[int] = mapped_column(Integer, default=4)


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("doc"))
    kb_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(120), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | indexing | ready | error
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    external_file_id: Mapped[str | None] = mapped_column(String(120), nullable=True)


class Chunk(Base):
    """Vector rows for the built-in LangChain vector store (SQLite or Postgres without pgvector)."""

    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("chk"))
    kb_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    embedding: Mapped[bytes] = mapped_column(LargeBinary)
    dim: Mapped[int] = mapped_column(Integer)


class PhoneNumber(TimestampMixin, Base):
    __tablename__ = "phone_numbers"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("num"))
    e164: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    xai_phone_number_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    xai_webhook_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    signing_secret_cipher: Mapped[str | None] = mapped_column(Text, nullable=True)
    sip_host: Mapped[str] = mapped_column(String(120), default="sip.voice.x.ai")
    sip_auth: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # username, allowed_addresses
    entry_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    use_published: Mapped[bool] = mapped_column(Boolean, default=True)
    greeting_disclosure: Mapped[str] = mapped_column(Text, default="")


class TransferTarget(TimestampMixin, Base):
    __tablename__ = "transfer_targets"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("xfr"))
    name: Mapped[str] = mapped_column(String(120), unique=True)
    uri: Mapped[str] = mapped_column(String(255))  # tel:+E164 or sip:user@host
    description: Mapped[str] = mapped_column(Text, default="")


class Contact(TimestampMixin, Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("cnt"))
    external_key: Mapped[str] = mapped_column(String(255), unique=True)  # phone number or preview identity
    display_name: Mapped[str] = mapped_column(String(255), default="")
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("conv"))
    channel: Mapped[str] = mapped_column(String(16))  # web | sip
    status: Mapped[str] = mapped_column(String(16), default="live")  # live | ended | error
    entry_agent_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_agent_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    contact_id: Mapped[str | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    xai_conversation_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    call_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    from_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    resumed_from_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    disposition: Mapped[str] = mapped_column(String(40), default="")
    extracted: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    agents_visited: Mapped[list[Any]] = mapped_column(JSON, default=list)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("trn"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16))  # user | assistant | tool | handoff | system | dtmf
    agent_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)  # webhook-id header
    event_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    detail: Mapped[str] = mapped_column(Text, default="")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ConversationEvent(Base):
    """Realtime events for one conversation, in order: what xAI sent and what Voice Stack sent back.

    Audio and transcript deltas are not stored (they would dwarf everything else); the final
    transcripts are in `turns`. Secrets in session.update are redacted before saving.
    """

    __tablename__ = "conversation_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    direction: Mapped[str] = mapped_column(String(8))  # in (from xAI) | out (to xAI)
    type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
