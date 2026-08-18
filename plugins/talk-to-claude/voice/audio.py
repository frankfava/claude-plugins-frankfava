"""The microphone. Knows nothing about who transcribes what it captures."""

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
BLOCK = 1600            # 0.1 s
FLOOR = 0.015           # quiet-room threshold, and the lower bound
WARMUP = 0.3            # a device returns silence while it starts, AirPods especially
CALIBRATE = 0.4         # seconds of room tone to measure after that
MARGIN = 3.0            # speech has to be this much louder than the room
ONSET = 3               # consecutive loud blocks before we call it speech
MIN_SPEECH = 0.5        # seconds of speech before silence is allowed to end it


def _calibrate(stream) -> float:
    """Set the speech threshold from the room rather than from a constant.

    A fixed threshold is really an assumption about where you are sitting. In a
    cafe the ambient floor sits above it, so the recorder triggers on other
    people and never hears the silence it needs to stop on. Measuring the room
    first costs four hundred milliseconds and makes the same code work at a
    desk and in a crowd.
    """
    for _ in range(int(WARMUP * SAMPLE_RATE / BLOCK)):
        stream.read(BLOCK)          # discard: measuring this reads the room as silent

    levels = []
    for _ in range(int(CALIBRATE * SAMPLE_RATE / BLOCK)):
        data, _ = stream.read(BLOCK)
        levels.append(float(np.sqrt(np.mean(data ** 2))))
    return max(FLOOR, float(np.median(levels)) * MARGIN)


def record(silence_seconds: float = 1.5, max_seconds: float = 120.0) -> "np.ndarray":
    """Wait for speech, then record until it stops.

    Two pieces of state, doing different jobs. `started` latches on the first
    loud block so a pause before you speak does not end the recording.
    `silent_for` accumulates only afterwards, and is what decides you have
    finished. Collapsing them into one gives a recorder that either never
    starts or never stops.
    """
    frames, started, silent_for, elapsed = [], False, 0.0, 0.0
    loud_run, speech = 0, 0.0
    step = BLOCK / SAMPLE_RATE
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="float32", blocksize=BLOCK) as stream:
        threshold = _calibrate(stream)
        while elapsed < max_seconds:      # a hard cap; a noisy room never falls silent
            data, _ = stream.read(BLOCK)
            elapsed += step
            if float(np.sqrt(np.mean(data ** 2))) > threshold:
                # A single loud block is a door or a cup. Speech is sustained,
                # so wait for a run of them before deciding the turn started.
                loud_run += 1
                silent_for = 0.0
                if loud_run >= ONSET:
                    started = True
                    speech += step
                frames.append(data.copy())
            else:
                loud_run = 0
                if started:
                    silent_for += step
                    frames.append(data.copy())
                    # Do not let a gap end a turn that has barely begun.
                    if silent_for >= silence_seconds and speech >= MIN_SPEECH:
                        break
                elif frames:
                    frames.clear()        # drop the transient we were holding
    return np.concatenate(frames).flatten() if frames else np.array([], "float32")


def room_level(seconds: float = 0.4) -> tuple[float, float]:
    """Report the current noise floor and the threshold it would produce."""
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="float32", blocksize=BLOCK) as stream:
        for _ in range(int(WARMUP * SAMPLE_RATE / BLOCK)):
            stream.read(BLOCK)
        levels = []
        for _ in range(int(seconds * SAMPLE_RATE / BLOCK)):
            data, _ = stream.read(BLOCK)
            levels.append(float(np.sqrt(np.mean(data ** 2))))
    floor = float(np.median(levels))
    return floor, max(FLOOR, floor * MARGIN)


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
