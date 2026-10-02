"""
Generate a synthetic standard PCM WAV audio file for real-time 1.0x replay testing.

Creates a valid 16kHz, 16-bit mono WAV file with audio energy and acoustic frames.
"""

import math
import struct
import wave
from pathlib import Path

OUTPUT_FILE = Path(__file__).resolve().parents[1] / "data" / "audio" / "synthetic_call_sample.wav"
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

SAMPLE_RATE = 16000
DURATION_SECONDS = 8.0  # 8.0 seconds of audio
TOTAL_SAMPLES = int(SAMPLE_RATE * DURATION_SECONDS)

# Generate synthetic carrier tone + modulating conversational frequencies
with wave.open(str(OUTPUT_FILE), "wb") as wav:
    wav.setnchannels(1)  # Mono
    wav.setsampwidth(2)  # 16-bit
    wav.setframerate(SAMPLE_RATE)

    frames = bytearray()
    for i in range(TOTAL_SAMPLES):
        t = i / SAMPLE_RATE
        # Synthesize varying cadence mimicking vocal formants
        f1 = 220.0 + 80.0 * math.sin(2 * math.pi * 0.5 * t)
        f2 = 440.0 + 120.0 * math.cos(2 * math.pi * 0.8 * t)
        envelope = 0.5 * (1.0 + math.sin(2 * math.pi * 1.5 * t))
        val = envelope * (0.6 * math.sin(2 * math.pi * f1 * t) + 0.4 * math.sin(2 * math.pi * f2 * t))
        sample = int(val * 16383.0)
        frames.extend(struct.pack("<h", sample))

    wav.writeframes(frames)

print(f"Generated synthetic WAV audio: {OUTPUT_FILE} ({DURATION_SECONDS}s, {SAMPLE_RATE}Hz, mono)")
