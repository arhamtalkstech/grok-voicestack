"""LangGraph checkpointer (per-conversation state) and store (long-term contact memory).

SQLite in development, Postgres when DATABASE_URL points at Postgres.
"""

from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager, AsyncExitStack, nullcontext
from dataclasses import dataclass

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore

from voicestack.config import get_settings


@dataclass
class Persistence:
    checkpointer: BaseCheckpointSaver
    store: BaseStore
    # AsyncSqliteStore shares one connection; concurrent sessions must not interleave transactions.
    store_lock: AbstractAsyncContextManager = nullcontext()


_persistence: Persistence | None = None
_stack: AsyncExitStack | None = None


async def open_persistence() -> Persistence:
    global _persistence, _stack
    if _persistence:
        return _persistence
    settings = get_settings()
    _stack = AsyncExitStack()
    if settings.is_postgres:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from langgraph.store.postgres.aio import AsyncPostgresStore

        saver = await _stack.enter_async_context(AsyncPostgresSaver.from_conn_string(settings.psycopg_url))
        store = await _stack.enter_async_context(AsyncPostgresStore.from_conn_string(settings.psycopg_url))
    else:
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        from langgraph.store.sqlite.aio import AsyncSqliteStore

        # Separate files: two connections writing one SQLite file lock each other out.
        base = settings.checkpoint_sqlite_path
        saver_conn = await _stack.enter_async_context(aiosqlite.connect(str(base)))
        # The store runs its own BEGIN/COMMIT, so it needs an autocommit connection (as LangGraph opens it).
        store_conn = await _stack.enter_async_context(
            aiosqlite.connect(str(base.with_name("langgraph-store.db")), isolation_level=None)
        )
        for conn in (saver_conn, store_conn):
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA busy_timeout=10000")
        saver = AsyncSqliteSaver(saver_conn)
        store = AsyncSqliteStore(store_conn)
    await saver.setup()
    await store.setup()
    _persistence = Persistence(saver, store, nullcontext() if settings.is_postgres else asyncio.Lock())
    return _persistence


async def close_persistence() -> None:
    global _persistence, _stack
    if _stack:
        await _stack.aclose()
    _persistence, _stack = None, None


def get_persistence() -> Persistence:
    if not _persistence:
        raise RuntimeError("Persistence is not open; call open_persistence() at startup")
    return _persistence
