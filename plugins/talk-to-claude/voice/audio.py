"""The microphone. Knows nothing about who transcribes what it captures."""

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
BLOCK = 1600            # 0.1 s
THRESHOLD = 0.015       # RMS amplitude that counts as speech


def record(silence_seconds: float = 1.5, max_seconds: float = 120.0) -> "np.ndarray":
    """Wait for speech, then record until it stops.

    Two pieces of state, doing different jobs. `started` latches on the first
    loud block so a pause before you speak does not end the recording.
    `silent_for` accumulates only afterwards, and is what decides you have
    finished. Collapsing them into one gives a recorder that either never
    starts or never stops.
    """
    frames, started, silent_for, elapsed = [], False, 0.0, 0.0
    step = BLOCK / SAMPLE_RATE
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="float32", blocksize=BLOCK) as stream:
        while elapsed < max_seconds:      # a hard cap; a noisy room never falls silent
            data, _ = stream.read(BLOCK)
            elapsed += step
            if float(np.sqrt(np.mean(data ** 2))) > THRESHOLD:
                started, silent_for = True, 0.0
                frames.append(data.copy())
            elif started:
                silent_for += step
                frames.append(data.copy())
                if silent_for >= silence_seconds:
                    break
    return np.concatenate(frames).flatten() if frames else np.array([], "float32")


def to_wav(audio: "np.ndarray") -> bytes:
    """16-bit PCM in memory, which is what every transcription API wants."""
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes((np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes())
    return buf.getvalue()
