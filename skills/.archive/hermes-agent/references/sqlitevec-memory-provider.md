# sqlite-vec Memory Provider — Implementation Reference

A user-installed memory provider plugin that adds semantic vector search to Hermes using sqlite-vec for storage and sentence-transformers for local embeddings.

## Plugin Location

```
~/.hermes/plugins/sqlitevec/__init__.py    # Plugin code (MemoryProvider ABC)
~/.hermes/plugins/sqlitevec/plugin.yaml    # Metadata
~/.hermes/memory/sqlitevec.db              # Vector database
```

## Architecture

```
User message → Hermes Agent → MemoryProvider.prefetch(query) → sqlite-vec search → context injection
             → Agent responds → MemoryProvider.sync_turn(user, asst) → embedding → sqlite-vec store
             → Tool call (memory_save/memory_search) → handle_tool_call() → sqlite-vec CRUD
```

## Key Components

### 1. MemoryProvider ABC Implementation (`__init__.py`)

Required methods:
- `name` → `"sqlitevec"`
- `is_available()` → checks `import sqlite_vec`
- `initialize(session_id, **kwargs)` → create DB, load extension, create tables
- `system_prompt_block()` → tool instructions for the model
- `prefetch(query)` → semantic search before each turn (auto-inject context)
- `sync_turn(user, asst)` → auto-store each turn
- `get_tool_schemas()` → expose `memory_save` and `memory_search` tools
- `handle_tool_call()` → dispatch tool calls
- `shutdown()` → close DB

### 2. Plugin Registration

```python
def register(ctx):
    ctx.register_memory_provider(SQLiteVecMemoryProvider())
```

The plugin goes in `~/.hermes/plugins/<name>/` for user-installed plugins.
The directory name MUST match `memory.provider` in config.yaml.

### 3. Database Schema

```sql
-- Vector store (384-dim embeddings from all-MiniLM-L6-v2)
CREATE VIRTUAL TABLE vec_memories USING vec0(embedding float[384]);

-- Metadata store
CREATE TABLE memory_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    source TEXT DEFAULT 'chat',
    timestamp REAL NOT NULL,
    session_id TEXT DEFAULT ''
);
```

## Thread Safety — Critical

Hermes runs tool calls in a **separate thread** from the agent's main loop.
SQLite connections are thread-affine by default — this causes:

```
SQLite objects created in a thread can only be used in that same thread.
```

**Fix:** Pass `check_same_thread=False` when creating the connection:

```python
db = sqlite3.connect(db_path, check_same_thread=False)
```

## Embedding Model — Local, Offline

Using `sentence-transformers/all-MiniLM-L6-v2` (384-dim, 87MB model).

### Cache Setup

Models are cached at `~/.cache/huggingface/hub/`. The first load downloads from
HuggingFace (~87MB), subsequent loads are instant.

### Offline Mode — Critical

**Without offline mode, sentence-transformers hangs on first load** trying to
reach HuggingFace, even when the model is cached. Set these env vars BEFORE
importing:

```python
from __future__ import annotations

import os as _os
_os.environ.setdefault("HF_HUB_OFFLINE", "1")
_os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
```

These must be set BEFORE `sentence_transformers` is imported. In a plugin,
they go at the top of the file.

**Pitfall: `from __future__ import annotations` ordering.** Python enforces
that `__future__` imports are the very first statements in a file (after
comments and docstrings). Do NOT put the env var setup before `from __future__`
— that causes a `SyntaxError`. Use `import os as _os` (aliased) to avoid
shadowing a later `import os` if the module uses `os` elsewhere.

### Model Download (if slow)

If HuggingFace downloads are slow or timeout, download directly with curl:

```bash
curl -sL --connect-timeout 30 --max-time 300 \
  -o ~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/.../pytorch_model.bin \
  "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/pytorch_model.bin"
```

Then manually set up the cache's blob hash / symlink structure, or use
`huggingface_hub.snapshot_download()` with sufficient timeout.

## Dependencies Installed

```bash
pip install sqlite-vec              # Vector extension for SQLite
pip install sentence-transformers    # Embedding model (includes torch)
```

All installed in Hermes's venv: `~/.hermes/hermes-agent/venv/`

## Configuration

```yaml
# In config.yaml
memory:
  provider: sqlitevec
```

## Tools Exposed

| Tool | Description | Parameters |
|------|-------------|------------|
| `memory_save` | Store a fact with semantic embedding | text (req), category (opt), source (opt) |
| `memory_search` | Find memories by meaning | query (req), limit (opt, max 20), category (opt) |

## Performance

- Model load: ~1.6s (first session)
- Embedding: ~0.05s per 100 chars
- Vector search: ~0.01s (up to ~100K vectors, brute force)
- Storage: ~1KB per memory entry (384 floats + metadata)

## Limitations

- sqlite-vec is pre-v1 (v0.1.9) — API may change
- No ANN index — brute-force search, slower with 100K+ vectors
- 384-dim capacity (all-MiniLM-L6-v2) — not suitable for very nuanced similarity
- No knowledge graph or temporal reasoning — pure semantic similarity
- Only one memory provider can be active at a time
