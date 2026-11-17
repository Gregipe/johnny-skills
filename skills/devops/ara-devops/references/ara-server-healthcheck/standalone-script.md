# Standalone Healthcheck Script

A standalone Python script is available at `/Users/greg/bin/ara-healthcheck`.

## Usage

```bash
ara-healthcheck
```

Run from any terminal. The script is self-contained (no Hermes dependency) and executes the full healthcheck suite:
- Server health & UI pages
- All core API read endpoints
- Lead CRUD (create, get, patch, search, duplicate check)
- Deal CRUD (create, get, patch, attach lead)
- Chat capability (thread + Ava response + message storage)
- Cadence preview
- Cleanup (deletes all [HEALTHCHECK] test artifacts)

## Exit Codes

- `0` — All checks passed
- `1` — One or more checks failed

## Dependencies

Python 3 with `curl` on PATH. No pip packages required.
