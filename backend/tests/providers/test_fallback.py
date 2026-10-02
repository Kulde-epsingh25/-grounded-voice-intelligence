"""
Comprehensive Provider Fallback Test Suite.

Validates the 6 core fallback principles:
1. Primary succeeds -> Gemini must NOT be called
2. Primary timeout -> Gemini called & succeeds
3. Primary 429 -> Gemini called & succeeds
4. Primary 503 unavailable -> Gemini called & succeeds
5. Gemini also fails -> HF Whisper / MMS used
6. Everything fails -> Returns controlled SERVICE_UNAVAILABLE error without data fabrication
7. Fallback loop prevention
8. Non-retryable error does not trigger fallback
9. Missing credentials skip unconfigured provider
"""

import asyncio
import pytest

from app.core.providers.exceptions import (
    AllProvidersFailedError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.core.providers.fallback import (
    ProviderCandidate,
    ProviderResult,
    execute_with_fallback,
)
from app.core.providers.health import get_health_tracker


@pytest.fixture(autouse=True)
def reset_health():
    tracker = get_health_tracker()
    tracker.reset()
    yield
    tracker.reset()


def test_1_primary_succeeds_fallback_not_called():
    """Test 1: OpenAI succeeds → Gemini must NOT be called."""
    async def _run():
        gemini_called = False

        def call_openai():
            return "OpenAI generated text response."

        def call_gemini():
            nonlocal gemini_called
            gemini_called = True
            return "Gemini response."

        candidates = [
            ProviderCandidate(name="openai", execute_fn=call_openai, is_configured=True),
            ProviderCandidate(name="gemini", execute_fn=call_gemini, is_configured=True),
        ]

        result: ProviderResult = await execute_with_fallback(candidates, operation="llm_test")

        assert result.success is True
        assert result.provider == "openai"
        assert result.fallback_used is False
        assert result.data == "OpenAI generated text response."
        assert gemini_called is False, "Fallback Gemini provider MUST NOT be called when primary succeeds"

    asyncio.run(_run())


def test_2_primary_timeout_triggers_gemini_fallback():
    """Test 2: OpenAI timeout → Gemini called → successful Gemini response."""
    async def _run():
        async def call_openai_timeout():
            raise ProviderTimeoutError("OpenAI connection timed out after 5000ms", provider="openai")

        def call_gemini():
            return "Gemini fallback response."

        candidates = [
            ProviderCandidate(name="openai", execute_fn=call_openai_timeout, is_configured=True),
            ProviderCandidate(name="gemini", execute_fn=call_gemini, is_configured=True),
        ]

        result: ProviderResult = await execute_with_fallback(candidates, operation="llm_test")

        assert result.success is True
        assert result.provider == "gemini"
        assert result.fallback_used is True
        assert result.data == "Gemini fallback response."
        assert len(result.attempts) == 2
        assert any(t in result.attempts[0]["error"].lower() for t in ("timeout", "timed out"))

    asyncio.run(_run())


def test_3_primary_429_triggers_asr_fallback():
    """Test 3: Deepgram 429 rate limit → Gemini Transcribe called."""
    async def _run():
        def call_deepgram():
            raise ProviderRateLimitError("Deepgram 429 Too Many Requests: Rate limit exceeded", provider="deepgram", status_code=429)

        def call_gemini_transcribe():
            return {"transcript": "Verified transcript from Gemini"}

        candidates = [
            ProviderCandidate(name="deepgram", execute_fn=call_deepgram, is_configured=True),
            ProviderCandidate(name="gemini", execute_fn=call_gemini_transcribe, is_configured=True),
        ]

        result = await execute_with_fallback(candidates, operation="asr_test")

        assert result.success is True
        assert result.provider == "gemini"
        assert result.fallback_used is True
        assert result.data["transcript"] == "Verified transcript from Gemini"
        assert result.attempts[0]["status"] == "failed"
        assert "429" in result.attempts[0]["error"]

    asyncio.run(_run())


def test_4_primary_unavailable_triggers_tts_fallback():
    """Test 4: ElevenLabs 503 unavailable → Gemini TTS called."""
    async def _run():
        def call_elevenlabs():
            raise ProviderUnavailableError("ElevenLabs 503 Service Unavailable", provider="elevenlabs", status_code=503)

        def call_gemini_tts():
            return {"audio_bytes": b"synthetic_gemini_audio", "status": "LIVE SYNTHESIZED"}

        candidates = [
            ProviderCandidate(name="elevenlabs", execute_fn=call_elevenlabs, is_configured=True),
            ProviderCandidate(name="gemini", execute_fn=call_gemini_tts, is_configured=True),
        ]

        result = await execute_with_fallback(candidates, operation="tts_test")

        assert result.success is True
        assert result.provider == "gemini"
        assert result.fallback_used is True
        assert result.data["audio_bytes"] == b"synthetic_gemini_audio"

    asyncio.run(_run())


def test_5_gemini_also_fails_falls_back_to_hf_whisper():
    """Test 5: Deepgram fails → Gemini fails → HF Whisper used."""
    async def _run():
        def call_deepgram():
            raise ProviderTimeoutError("Deepgram timeout", provider="deepgram")

        def call_gemini():
            raise ProviderUnavailableError("Gemini service overloaded (503)", provider="gemini")

        def call_hf_whisper():
            return {"transcript": "HF Whisper local fallback audio text", "model": "openai/whisper-large-v3-turbo"}

        candidates = [
            ProviderCandidate(name="deepgram", execute_fn=call_deepgram, is_configured=True),
            ProviderCandidate(name="gemini", execute_fn=call_gemini, is_configured=True),
            ProviderCandidate(name="hf_whisper", execute_fn=call_hf_whisper, is_configured=True),
        ]

        result = await execute_with_fallback(candidates, operation="asr_multilevel_test")

        assert result.success is True
        assert result.provider == "hf_whisper"
        assert result.fallback_used is True
        assert len(result.attempts) == 3
        assert result.attempts[0]["provider"] == "deepgram"
        assert result.attempts[1]["provider"] == "gemini"
        assert result.attempts[2]["provider"] == "hf_whisper"
        assert result.attempts[2]["status"] == "success"

    asyncio.run(_run())


def test_6_everything_fails_controlled_error():
    """Test 6: Everything fails → Return controlled SERVICE_UNAVAILABLE. Never fabricate data."""
    async def _run():
        def call_p1():
            raise ProviderTimeoutError("P1 timeout", provider="p1")

        def call_p2():
            raise ProviderUnavailableError("P2 down", provider="p2")

        candidates = [
            ProviderCandidate(name="p1", execute_fn=call_p1, is_configured=True),
            ProviderCandidate(name="p2", execute_fn=call_p2, is_configured=True),
        ]

        result = await execute_with_fallback(candidates, operation="strict_audit_test")

        assert result.success is False
        assert result.provider == "none"
        assert result.error == "SERVICE_UNAVAILABLE"
        assert result.data is None, "Never fabricate a response when all providers fail"
        assert len(result.attempts) == 2

    asyncio.run(_run())


def test_7_no_fallback_loops():
    """Test 7: Ensure provider duplicates are deduplicated so no provider executes twice."""
    async def _run():
        execution_counts = {"p1": 0, "p2": 0}

        def call_p1():
            execution_counts["p1"] += 1
            raise ProviderTimeoutError("p1 timeout")

        def call_p2():
            execution_counts["p2"] += 1
            return "p2 success"

        candidates = [
            ProviderCandidate(name="p1", execute_fn=call_p1, is_configured=True),
            ProviderCandidate(name="p2", execute_fn=call_p2, is_configured=True),
            ProviderCandidate(name="p1", execute_fn=call_p1, is_configured=True),
            ProviderCandidate(name="p2", execute_fn=call_p2, is_configured=True),
        ]

        result = await execute_with_fallback(candidates, operation="loop_test")

        assert result.success is True
        assert result.provider == "p2"
        assert execution_counts["p1"] == 1, "Provider p1 must only execute once per request"
        assert execution_counts["p2"] == 1, "Provider p2 must only execute once per request"

    asyncio.run(_run())


def test_8_non_retryable_error_does_not_trigger_fallback():
    """Test 8: Client validation / business logic errors must NOT trigger fallback."""
    async def _run():
        p2_called = False

        def call_p1():
            raise ValueError("Invalid user parameter: age cannot be negative")

        def call_p2():
            nonlocal p2_called
            p2_called = True
            return "should not reach"

        candidates = [
            ProviderCandidate(name="p1", execute_fn=call_p1, is_configured=True),
            ProviderCandidate(name="p2", execute_fn=call_p2, is_configured=True),
        ]

        with pytest.raises(ValueError) as excinfo:
            await execute_with_fallback(candidates, operation="validation_test")

        assert "age cannot be negative" in str(excinfo.value)
        assert p2_called is False, "Non-retryable error must abort immediately without fallback"

    asyncio.run(_run())


def test_9_missing_credentials_triggers_fallback():
    """Test 9: When primary credentials are unconfigured, skips to configured fallback."""
    async def _run():
        def call_primary():
            return "primary"

        def call_fallback():
            return "fallback success"

        candidates = [
            ProviderCandidate(name="unconfigured_primary", execute_fn=call_primary, is_configured=False),
            ProviderCandidate(name="configured_fallback", execute_fn=call_fallback, is_configured=True),
        ]

        result = await execute_with_fallback(candidates, operation="config_test")

        assert result.success is True
        assert result.provider == "configured_fallback"
        assert result.fallback_used is True
        assert result.attempts[0]["status"] == "skipped"

    asyncio.run(_run())


def test_10_provider_status_endpoint():
    """Test 10: GET /api/v1/providers/status returns expected schema without leaking secrets."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.get("/api/v1/providers/status")
    assert resp.status_code == 200
    data = resp.json()

    assert "llm" in data
    assert "asr" in data
    assert "tts" in data
    assert "voice" in data
    assert "openai" in data["llm"]
    assert "gemini" in data["llm"]
    assert "deepgram" in data["asr"]
    assert "elevenlabs" in data["tts"]
    assert "vapi" in data["voice"]
    assert "gemini_live" in data["voice"]

    # Verify no secrets in body
    raw_text = resp.text
    assert "sk-" not in raw_text
    assert "vapi_" not in raw_text


def test_11_gemini_live_session_uses_existing_q1_tools():
    """Test 11: Gemini Live session executes Q1 tools (qualification, state machine) consistently."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    # Start session
    resp_start = client.post("/api/v1/gemini/session/start")
    assert resp_start.status_code == 200
    sess_data = resp_start.json()
    sess_id = sess_data["session_id"]
    assert sess_data["provider"] == "gemini_live"

    # Send cooperative message
    resp_msg = client.post(
        f"/api/v1/gemini/session/{sess_id}/message",
        json={"text": "We are a retail company operating for 3 years, monthly revenue is $600k."},
    )
    assert resp_msg.status_code == 200
    turn_data = resp_msg.json()
    assert turn_data["provider"] == "gemini_live"
    assert turn_data["fallback_used"] is True
    assert "qualification_state" in turn_data

    # End session
    resp_end = client.post(f"/api/v1/gemini/session/{sess_id}/end")
    assert resp_end.status_code == 200

