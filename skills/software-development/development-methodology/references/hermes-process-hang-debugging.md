# Hermes Process Hang Debugging

How to diagnose a stuck `process(action='wait')` or `notify_on_complete` hang in Hermes — where the agent calls `wait proc_xxx` and never gets a response because the background process never exits.

## The Symptom

- Agent calls `process(action='wait', session_id='proc_xxx')` — or `wait proc_xxx` in the TUI
- No response comes back
- If the TUI gateway gets SIGTERM'd, the crash log (`tui_gateway_crash.log`) shows a thread dump with multiple blocked threads

## Crash Log Entry Point

Each crash event is bounded by:

```
=== SIGTERM received · 2026-05-22 10:08:56 ===
main-thread stack at signal delivery:
  ...
[thread dumps]
```

SIGTERM = the gateway received a kill signal (restart, shutdown, out-of-memory). The thread dump at signal time captures the frozen state.

## The Three Blocked Threads

When a `wait proc_xxx` hangs, three threads are always involved:

### 1. Reader Thread (`proc-reader-proc_xxx`)

```
--- thread proc-reader-proc_3552849ba801 (id=6297612288) ---
  ...
  File ".../tools/process_registry.py", line 690, in _reader_loop
    chunk = session.process.stdout.read(4096)
```

**Signal:** Blocked on `stdout.read(4096)`. The process is still alive but has stopped writing to stdout. The pipe hasn't been closed because the process hasn't exited.

**Interpretation:** The background process is still running. Nothing is coming through its stdout pipe. The reader thread can't proceed until either (a) more data arrives, or (b) the pipe is closed (process exits).

### 2. Agent Run Thread (conversation loop, inside `wait()`)

```
--- thread Thread-15 (run) (id=...) ---
  ...
  File ".../tui_gateway/server.py", line 3251, in run
    result = agent.run_conversation(
  File ".../run_agent.py", line 11662, in _execute_tool_calls_sequential
    function_result = handle_function_call(
  File ".../model_tools.py", line 775, in handle_function_call
    result = registry.dispatch(
  File ".../tools/process_registry.py", line 1516, in _handle_process
    return json.dumps(process_registry.wait(session_id, timeout=...))
  File ".../tools/process_registry.py", line 1032, in wait
    self._reconcile_local_exit(session)
  File ".../tools/process_registry.py", line 900, in _reconcile_local_exit
    chunk = stdout.read()
```

**Signal:** The `process(action='wait')` handler called `wait()` → `_reconcile_local_exit()` → `stdout.read()`. It's trying to drain remaining stdout after the process exits, but `stdout.read()` (without argument = read until EOF) blocks because the pipe is still open.

**Interpretation:** The wait handler is itself blocked trying to read stdout for reconciliation. Even if the cleanup thread terminates the process, this read may still block if the pipe is held by the reader thread.

### 3. Cleanup Thread

```
--- thread Thread-19 (_cleanup_thread_worker) (id=...) ---
  ...
  File ".../tools/terminal_tool.py", line 1331, in _cleanup_thread_worker
    time.sleep(1)
```

**Signal:** The cleanup worker is cycling through its sleep loop. It's trying to clean up the session but can't because the process is still alive.

## Root Cause Identification

### Primary Cause: The process never exits

```
stdout still open  →  reader thread blocks on read(4096)
                  →  wait() blocks on read() in _reconcile_local_exit()
                  →  cleanup thread keeps sleeping
```

The most common reasons a background process doesn't exit:
- **Server/daemon mode** — the process was started to run indefinitely (e.g., `uvicorn`, `python -m http.server`)
- **Waiting for input** — the process is waiting on stdin, a network socket, or a blocking I/O call
- **Deadlock** — the process has its own internal deadlock
- **Wrong background flag** — the process was intended to run in background but the agent expected it to exit

### Secondary Cause: Process ran too long and was SIGTERM'd

If the process would have eventually exited but took longer than the agent's patience or the TUI gateway's lifespan, the symptom is the same — threads block until the gateway dies.

## The Deadlock ⚠️

The critical bug that made this hang fatal (causing the agent loop to freeze rather than timing out) was a **BufferedReader/TextIOWrapper lock contention** in `_reconcile_local_exit()`.

### Mechanism

1. The **reader thread** (`_reader_loop` in `process_registry.py:690`) calls `session.process.stdout.read(4096)` — this acquires the internal lock of the `TextIOWrapper` (or `BufferedReader`) object and then blocks on the OS pipe, waiting for data.

2. The **agent thread** (`wait()` handler at `process_registry.py:1032`) calls `_reconcile_local_exit()` when the direct child process has exited but a descendant still holds the pipe open. Inside `_reconcile_local_exit()`, it calls `stdout.read()` on the **same** `TextIOWrapper` object.

3. **Deadlock:** `stdout.read()` tries to acquire the same internal lock the reader thread is holding. Since the reader thread is blocked on the OS pipe (waiting for data that will never come), neither thread can make progress. The `wait()` method's timeout loop never gets to check the deadline.

### The Fix

**Do NOT read from the shared `TextIOWrapper`/`BufferedReader` in `_reconcile_local_exit()`.** Read from the raw file descriptor directly using `os.read(fd, 65536)`, which bypasses the Python-level buffered object entirely and works correctly with `O_NONBLOCK`:

```python
# ❌ OLD — deadlocks against reader thread holding TextIOWrapper lock:
chunk = stdout.read()
if chunk:
    drained = chunk if isinstance(chunk, str) else chunk.decode(...)

# ✅ NEW — reads from raw fd, no lock contention:
raw = os.read(fd, 65536)
if raw:
    drained = raw.decode("utf-8", errors="replace")
```

With the fix applied, `_reconcile_local_exit()` can't block, `wait()` properly times out after the configured `TERMINAL_TIMEOUT` (default 180s), and returns `{"status": "timeout", ...}` with accumulated output.

### The Warning Log

A `logger.warning()` was also added to the `wait()` timeout path so that stuck-process events are visible in `agent.log` without needing a crash dump:

```
wait(proc_xxx) timed out after 180s — command=...
```

### Where the fix lives

| File | Function | Lines |
|------|----------|-------|
| `tools/process_registry.py` | `_reconcile_local_exit()` | ~900 (raw fd read) |
| `tools/process_registry.py` | `wait()` | ~1063 (timeout + warning log) |

## How to Investigate Next (beyond crash log)

1. **Check what command spawned the process** — search the agent.log for the session ID associated with the `proc_xxx` ID to find the terminal command that created it.
2. **Check if the same process is still running** — after recovery, use `ps aux | grep` to see if the orphaned process survived.
3. **Look at the process creation arguments** — was `background=True` or `notify_on_complete=True` set? Was the timeout long enough?
4. **For long-running servers:** Don't use `notify_on_complete` or `process(action='wait')` — those are for processes that exit. Use `process(action='poll')` to check status, and design the workflow around the server staying alive.

## Prevention Patterns

| Pattern | When | Strategy |
|---------|------|----------|
| Short-lived script | Process should exit in <60s | Use `terminal(command, timeout=N)` foreground or `background=True` + `notify_on_complete=True` |
| Long-running job | Process takes minutes but exits | Use `background=True` + `notify_on_complete=True` — the notification fires on process exit |
| Server/daemon | Process should never exit | Start with `background=True`, then use `process(action='poll')` to check if it's alive. Do NOT call `wait` |
| Watcher pattern | Process runs until a condition | Use `watch_patterns` for selective mid-process signals, or use `process(action='poll')` + `process(action='log')` to inspect progress |

## Key File Locations

| File | Role |
|------|------|
| `~/.hermes/profiles/<profile>/logs/tui_gateway_crash.log` | Crash thread dumps — primary diagnostic for hangs |
| `~/.hermes/profiles/<profile>/logs/agent.log` | Session timeline — find the command that launched the process |
| `~/.hermes/profiles/<profile>/logs/errors.log` | Error-only view |
| `tools/process_registry.py` | Process lifecycle management (`_reader_loop` L690, `_reconcile_local_exit` L900, `wait` L1032) |
| `tools/terminal_tool.py` | Terminal tool implementation (`_cleanup_thread_worker` L1331) |
| `tui_gateway/server.py` | TUI gateway — notification poller loop |
