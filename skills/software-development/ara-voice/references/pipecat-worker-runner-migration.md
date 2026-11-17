# Pipecat 1.4.0 API Migration: PipelineRunner → WorkerRunner

**Date**: July 3, 2026
**Discovered during**: ARA voice agent debugging marathon

## The Problem

`PipelineRunner` and `PipelineTask` are **deprecated since Pipecat 1.3.0**. The Pipecat CLI templates correctly use the new `PipelineWorker` + `WorkerRunner` pattern, but the deprecation is easy to miss because:

1. `PipelineRunner` still imports without error
2. `PipelineRunner.run()` still runs without crashing
3. The WebRTC connection succeeds (ICE, tracks, `bot-ready`, data channel)
4. The runner's `/start` endpoint returns `200 OK` with a session ID
5. The browser shows "connected" with mic active

**But the pipeline services NEVER start. No STT, no LLM, no TTS.**

## Symptoms

- Zero STT/LLM/TTS initialization in server logs (no "Connecting to ElevenLabs", no "OpenAILLMService", etc.)
- `"Media stream error while reading the audio; clearing track"` appears after ~13 seconds
- User speaks but hears nothing, sees no text
- Pipeline is a zombie — WebRTC transport works, services don't

## Root Cause

`PipelineRunner` is a deprecated alias that wraps `WorkerRunner` but does NOT properly start pipeline services when `run(task)` is called. The `WorkerRunner` + `PipelineWorker` pattern correctly initializes and runs all services.

## Fix

### Before (broken — deprecated since 1.3.0)
```python
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams

task = PipelineTask(
    pipeline,
    params=PipelineParams(allow_interruptions=True, enable_metrics=True),
)
await PipelineRunner().run(task)
```

### After (correct — Pipecat 1.4.0+)
```python
from pipecat.pipeline.task import PipelineParams
from pipecat.pipeline.worker import PipelineWorker
from pipecat.workers.runner import WorkerRunner

worker = PipelineWorker(
    pipeline,
    params=PipelineParams(
        allow_interruptions=True,
        enable_metrics=True,
        enable_usage_metrics=True,
    ),
)
runner = WorkerRunner(handle_sigint=False)
await runner.add_workers(worker)
await runner.run()
```

## Verification

After deployment, restarted server should show STT/LLM/TTS initialization in logs:
```
Connecting to ElevenLabs Realtime STT
Connected to ElevenLabs Realtime STT
OpenAILLMService#0: Using system instruction: ...
Connecting to ElevenLabs
```

If these lines DON'T appear, the runner is wrong.
