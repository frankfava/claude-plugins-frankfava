"""The microphone. Knows nothing about who transcribes what it captures.

One thread owns the input device for the life of the process. Between turns it
learns the room; during a turn it hands blocks to whoever is recording. That
arrangement exists because calibrating at the start of each recording has three
problems: it costs most of a second before every question, the number is stale
the moment anything changes, and if you begin speaking during it your own voice
becomes the noise floor and the threshold ends up too high to hear you.

The cost is an input stream held open. Nothing is written anywhere, but the
device is live, which is a different posture from opening it per turn. Set
VOICE_CONTINUOUS=0 to calibrate per recording instead.
"""

import os
import queue
import threading
from collections import deque

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
BLOCK = 1600            # 0.1 s
FLOOR = 0.015           # quiet-room threshold, and the lower bound
MARGIN = 3.0            # speech has to be this much louder than the room
QUIET_PCT = 20          # the room is the quiet fifth of recent history
HISTORY = 100           # 10 s of blocks
WARMUP = 0.3            # a device returns silence while it starts
CALIBRATE = 0.4         # only used when continuous listening is off

ONSET = 3               # consecutive loud blocks before we call it speech
MIN_SPEECH = 0.3        # seconds of speech before silence may end the turn
NO_SPEECH = 8.0         # give up if nothing has been said by now

CONTINUOUS = os.environ.get("VOICE_CONTINUOUS", "1") != "0"
STEP = BLOCK / SAMPLE_RATE


def _rms(block) -> float:
    return float(np.sqrt(np.mean(block ** 2)))


def _threshold_from(levels) -> float:
    if not levels:
        return FLOOR
    # A percentile rather than a median: if someone spoke recently, half the
    # window is speech and the median would follow it upwards.
    return max(FLOOR, float(np.percentile(list(levels), QUIET_PCT)) * MARGIN)


class _Device:
    """Owns the input stream, learns the room, lends blocks to a recording."""

    def __init__(self) -> None:
        self._levels: deque = deque(maxlen=HISTORY)
        self._sink: queue.Queue | None = None
        self._lock = threading.Lock()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                            dtype="float32", blocksize=BLOCK) as stream:
            for _ in range(int(WARMUP * SAMPLE_RATE / BLOCK)):
                stream.read(BLOCK)          # devices return silence while starting
            while True:
                data, _ = stream.read(BLOCK)
                level = _rms(data)
                sink = self._sink
                if sink is None:
                    self._levels.append(level)   # only learn the room between turns
                else:
                    sink.put((level, data.copy()))

    @property
    def threshold(self) -> float:
        return _threshold_from(self._levels)

    def capture(self) -> queue.Queue:
        with self._lock:
            self._sink = queue.Queue()
            return self._sink

    def release(self) -> None:
        with self._lock:
            self._sink = None


_device = _Device() if CONTINUOUS else None


def _consume(next_block, threshold: float, silence_seconds: float, max_seconds: float):
    """The decision loop, fed one (level, block) at a time from either source."""
    frames, started, silent_for, elapsed = [], False, 0.0, 0.0
    loud_run, speech = 0, 0.0
    while elapsed < max_seconds:
        level, data = next_block()
        elapsed += STEP
        if level > threshold:
            # One loud block is a door or a cup. Speech is sustained.
            loud_run += 1
            silent_for = 0.0
            if loud_run == ONSET:
                # The onset blocks were speech too. Not counting them leaves a
                # one-word answer unable to reach MIN_SPEECH, so it never ends.
                started, speech = True, ONSET * STEP
            elif started:
                speech += STEP
            frames.append(data)
        else:
            loud_run = 0
            if started:
                silent_for += STEP
                frames.append(data)
                if silent_for >= silence_seconds and speech >= MIN_SPEECH:
                    break
                if silent_for >= silence_seconds * 3:
                    break                  # too short to meet the minimum, but over
            else:
                frames.clear()             # drop the transient we were holding
                if elapsed > NO_SPEECH:
                    break                  # nobody spoke; the loop reads this as goodbye
    return np.concatenate(frames).flatten() if frames else np.array([], "float32")


def record(silence_seconds: float = 1.5, max_seconds: float = 120.0) -> "np.ndarray":
    """Wait for speech, then record until it stops."""
    if _device is not None:
        sink = _device.capture()
        try:
            return _consume(sink.get, _device.threshold, silence_seconds, max_seconds)
        finally:
            _device.release()

    # Per-recording calibration: no stream held open, at the cost of a wait
    # before every turn and a threshold that your own voice can poison.
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="float32", blocksize=BLOCK) as stream:
        for _ in range(int(WARMUP * SAMPLE_RATE / BLOCK)):
            stream.read(BLOCK)
        levels = []
        for _ in range(int(CALIBRATE * SAMPLE_RATE / BLOCK)):
            data, _ = stream.read(BLOCK)
            levels.append(_rms(data))

        def next_block():
            data, _ = stream.read(BLOCK)
            return _rms(data), data.copy()

        return _consume(next_block, _threshold_from(levels), silence_seconds, max_seconds)


def room_level() -> tuple[float, float]:
    """Current noise floor and the threshold it produces."""
    if _device is not None:
        return _threshold_from(_device._levels) / MARGIN, _device.threshold
    return 0.0, FLOOR


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
