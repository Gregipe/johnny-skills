"""
ARA Voice Agent — Unified WebRTC + WhatsApp voice conversational layer.

Start:
    python bot.py --whatsapp     # both WebRTC + WhatsApp
    python bot.py                # WebRTC only (browser)

Browser:  open the URL shown (serves Pipecat's built-in WebRTC UI)
WhatsApp: webhook at /whatsapp
"""
import os

import httpx
from dotenv import load_dotenv
from loguru import logger

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams
from pipecat.pipeline.worker import PipelineWorker
from pipecat.runner.run import main
from pipecat.runner.types import (
    RunnerArguments,
    SmallWebRTCRunnerArguments,
)
from pipecat.services.elevenlabs.stt import ElevenLabsRealtimeSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.workers.runner import WorkerRunner
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.aggregators.llm_context import LLMContext

from voice_tools import build_voice_tools

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────
try:
    logger.add("/opt/ara-voice-agent/bot-sessions.log", rotation="1 MB", level="DEBUG")
    logger.add("/var/log/ara-voice-bot.log", level="INFO")
except PermissionError:
    pass

# ── Config ──────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ARA_BASE = os.getenv("ARA_BASE_URL", "http://localhost:8766")
ARA_VOICE_SECRET = os.getenv("ARA_VOICE_SECRET", "")

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5.4-mini")
TTS_VOICE_ID = os.getenv("TTS_VOICE_ID", "XrExE9yKIg1WjnnlVkGX")
TTS_MODEL = os.getenv("TTS_MODEL", "eleven_turbo_v2_5")
STT_MODEL = os.getenv("STT_MODEL", "scribe_v2_realtime")

# Different system prompts based on transport
DASHBOARD_SYSTEM_PROMPT = """You are Ava, an AI voice assistant for the user's CRM dashboard.
Spoken-style output: 1–2 sentences, no markdown, no bullet lists.
Numbers and names read naturally. Use tools for any data question — never fabricate
or answer about CRM data from memory. Summarize results — "you have three logistics
leads; Acme is furthest along, in negotiation" — never enumerate long lists.

If asked to create, update, send, schedule, or modify anything: "I can't make
changes by voice yet — I can look anything up for you." Do not propose write
actions or offer to draft them. Be warm, professional, and helpful."""

WHATSAPP_SYSTEM_PROMPT = """You are Ava, a helpful voice assistant for a business CRM.
You speak to customers over the phone. Keep responses concise — under 2 sentences.
Never read raw data — always summarize naturally.
If asked to modify data, say "I'll draft that and send a WhatsApp confirmation."
Be warm, professional, and helpful. Use the caller's name if you know it."""


def build_pipeline(
    runner_args: RunnerArguments,
    system_prompt: str,
    voice_tools: list | None = None,
    app_resources: dict | None = None,
) -> tuple[Pipeline, SmallWebRTCTransport]:
    """Build the STT → LLM → TTS pipeline."""

    transport = SmallWebRTCTransport(
        webrtc_connection=runner_args.webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_passthrough=True,
        ),
    )

    stt = ElevenLabsRealtimeSTTService(api_key=ELEVENLABS_API_KEY)

    llm = OpenAILLMService(
        api_key=OPENAI_API_KEY,
        settings=OpenAILLMService.Settings(
            model=LLM_MODEL,
            system_instruction=system_prompt,
            temperature=0.7,
        ),
    )

    tts = ElevenLabsTTSService(
        api_key=ELEVENLABS_API_KEY,
        sample_rate=16000,
        settings=ElevenLabsTTSService.Settings(
            voice=TTS_VOICE_ID,
            model=TTS_MODEL,
        ),
    )

    # Tools passed through LLMContext — auto-registered via FunctionSchema handlers
    context = LLMContext(tools=voice_tools or [])
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )

    pipeline = Pipeline([
        transport.input(),
        stt,
        user_aggregator,
        llm,
        tts,
        transport.output(),
        assistant_aggregator,
    ])

    return pipeline, transport


async def bot(runner_args: RunnerArguments):
    """Entry point called by the Pipecat runner for every session.
    
    Note: runner_args.body contains WebRTC SDP, NOT the /start POST body.
    Use env vars or external stores for per-session data, not runner_args.body.
    """
    logger.info(f"Voice session starting — transport: {type(runner_args).__name__}")

    # Per-session data must come from env vars or external stores
    # (runner_args.body is the WebRTC SDP, overwritten during handshake)
    tenant_id = os.getenv("ARA_TENANT_ID", "default")

    async with httpx.AsyncClient(timeout=10.0) as http:
        # Build CRM tools (optional — voice works without them)
        voice_tools = []
        try:
            voice_tools = await build_voice_tools(http)
            logger.info(f"Loaded {len(voice_tools)} voice tools")
        except Exception as e:
            logger.warning(f"Could not load voice tools: {e} — voice will run without CRM tools")

        app_resources = {
            "tenant_id": tenant_id,
            "http_client": http,
        }

        pipeline, transport = build_pipeline(
            runner_args, DASHBOARD_SYSTEM_PROMPT, voice_tools, app_resources,
        )

        worker = PipelineWorker(
            pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            app_resources=app_resources,
        )

        runner = WorkerRunner(handle_sigint=False)
        await runner.add_workers(worker)
        await runner.run()


if __name__ == "__main__":
    main()
