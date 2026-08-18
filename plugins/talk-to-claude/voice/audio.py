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
import time
import time
from collections import deque
from pathlib import Path

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
NO_SPEECH = float(os.environ.get("VOICE_NO_SPEECH", "4.0"))   # give up by now
# How long a pause is allowed to be before it counts as the end of a turn.
# 1.5 is fine for answering a question and too short for composing a thought,
# which presents as being cut off mid-sentence.
SILENCE = float(os.environ.get("VOICE_SILENCE", "2.5"))

CONTINUOUS = os.environ.get("VOICE_CONTINUOUS", "1") != "0"

# Barge-in: listen while speaking, so an interruption is heard rather than
# ignored. Only safe on headphones. Through laptop speakers the microphone
# hears the synthesiser and every reply interrupts itself, so it is opt-out
# per device rather than a setting you can leave on everywhere.
BARGE = os.environ.get("VOICE_BARGE", "1") != "0"
# Compared against per-block RMS, not sample peak, which is the mistake that
# made an earlier value ten times too high. Measured through AirPods: bleed
# sits at 0.006 median and 0.010 at the 95th percentile, while a voice talking
# over the speaker reaches about 0.018. The gap is real but narrow, so this
# needs remeasuring on any other output device.
BARGE_THRESHOLD = float(os.environ.get("VOICE_BARGE_THRESHOLD", "0.013"))
SPEAKING_FLAG = Path(os.environ.get("TMPDIR", "/tmp")) / "talk-to-claude-speaking"
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
        # Held open, so there has to be a way to let go of it. Releasing closes
        # the stream and the operating system stops showing the microphone as
        # in use, which is the only honest way to say it is off.
        self._wanted = threading.Event()        # starts closed: nothing to hear yet
        self._live = threading.Event()
        self._manual: bool | None = None        # None means follow demand
        self._on_barge = None                   # called when you talk over us
        self._barge_run = 0
        threading.Thread(target=self._run, daemon=True).start()
        threading.Thread(target=self._follow_demand, daemon=True).start()

    def _follow_demand(self) -> None:
        """Open the device when something needs it, close it when nothing does.

        Two things need it: a session in hands-free mode, which must be able to
        hear a reply at any moment, and a recording in progress. Outside those
        there is nothing to listen for, and an input stream held open for no
        reason is a microphone indicator you cannot explain.
        """
        while True:
            if self._manual is None:
                # Open when there is something to hear: a recording running, or
                # speech playing that you might cut off. Being in hands-free is
                # not a reason on its own. Most of that mode is Claude thinking,
                # and an open microphone during thinking is a lit indicator with
                # nothing behind it.
                needed = (self._sink is not None
                          or (BARGE and SPEAKING_FLAG.exists()))
                self.set_open(needed)
            time.sleep(0.2)     # fast enough to catch the start of an utterance

    def _run(self) -> None:
        while True:
            self._wanted.wait()
            self._levels.clear()            # the room may have changed while off
            try:
                with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                                    dtype="float32", blocksize=BLOCK) as stream:
                    for _ in range(int(WARMUP * SAMPLE_RATE / BLOCK)):
                        stream.read(BLOCK)  # devices return silence while starting
                    self._live.set()
                    while self._wanted.is_set():
                        data, _ = stream.read(BLOCK)
                        level = _rms(data)
                        sink = self._sink
                        if sink is None:
                            self._levels.append(level)   # learn the room between turns
                            self._watch_for_barge(level)
                        else:
                            sink.put((level, data.copy()))
            finally:
                self._live.clear()

    def _watch_for_barge(self, level: float) -> None:
        """Interrupt the speaker when someone talks over it.

        This has to live here rather than in `record`, because narration never
        calls `record`. Without it the microphone is open during a reply and
        nothing looks at what it hears, so barge-in appears to do nothing
        whenever hands-free is off.
        """
        if not (BARGE and self._on_barge and SPEAKING_FLAG.exists()):
            self._barge_run = 0
            return
        if level > max(_threshold_from(self._levels), BARGE_THRESHOLD):
            self._barge_run += 1
            if self._barge_run >= ONSET:
                self._barge_run = 0
                self._on_barge()
        else:
            self._barge_run = 0

    def set_open(self, wanted: bool) -> None:
        self._wanted.set() if wanted else self._wanted.clear()

    def wait_live(self, timeout: float = 5.0) -> bool:
        return self._live.wait(timeout)

    @property
    def is_open(self) -> bool:
        return self._live.is_set()

    @property
    def threshold(self) -> float:
        base = _threshold_from(self._levels)
        # While the speaker is active the room includes us, so ask for more.
        if BARGE and SPEAKING_FLAG.exists():
            return max(base, BARGE_THRESHOLD)
        return base

    def capture(self) -> queue.Queue:
        with self._lock:
            self._sink = queue.Queue()
            return self._sink

    def release(self) -> None:
        with self._lock:
            self._sink = None


_device = _Device() if CONTINUOUS else None


def _consume(next_block, threshold, silence_seconds: float, max_seconds: float,
             on_speech=None):
    """The decision loop, fed one (level, block) at a time from either source."""
    frames, started, silent_for, elapsed = [], False, 0.0, 0.0
    loud_run, speech, quiet_since = 0, 0.0, 0.0
    while elapsed < max_seconds:
        level, data = next_block()
        elapsed += STEP
        limit = threshold() if callable(threshold) else threshold
        if level > limit:
            # One loud block is a door or a cup. Speech is sustained.
            loud_run += 1
            silent_for = 0.0
            if loud_run == ONSET:
                # The onset blocks were speech too. Not counting them leaves a
                # one-word answer unable to reach MIN_SPEECH, so it never ends.
                started, speech = True, ONSET * STEP
                if on_speech is not None:
                    on_speech()          # you interrupted; stop talking over them
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
                # Do not give up while the speaker is still going: with barge-in
                # the whole point is to be listening for the length of the reply,
                # so the clock only starts once we have stopped talking.
                if BARGE and SPEAKING_FLAG.exists():
                    quiet_since = elapsed
                elif elapsed - quiet_since > NO_SPEECH:
                    break                  # nobody spoke; the loop reads this as goodbye
    return np.concatenate(frames).flatten() if frames else np.array([], "float32")


def record(silence_seconds: float = SILENCE, max_seconds: float = 120.0,
           on_speech=None) -> "np.ndarray":
    """Wait for speech, then record until it stops.

    `on_speech` fires the moment speech is confirmed, which is how barge-in
    works: the caller passes something that stops the speaker.
    """
    if _device is not None:
        held_open = _device.is_open
        sink = _device.capture()            # this alone makes the device wanted
        if not held_open:
            _device.set_open(True)
            _device.wait_live()
            # No history yet, so pay for a little here rather than measure the
            # room from nothing. Hands-free skips this: it never closed.
            time.sleep(CALIBRATE)
        try:
            return _consume(sink.get, lambda: _device.threshold,
                            silence_seconds, max_seconds, on_speech)
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

        return _consume(next_block, _threshold_from(levels), silence_seconds,
                        max_seconds, on_speech)


def on_barge(callback) -> None:
    """Register what to do when the user talks over the speaker."""
    if _device is not None:
        _device._on_barge = callback


def microphone(state: str | None = None) -> str:
    """Report or change whether the input device is held open."""
    if _device is None:
        return "per-turn"                   # only opened while recording anyway
    if state == "auto":
        _device._manual = None              # back to following demand
        return "auto"
    if state in ("on", "off"):
        # A manual choice sticks, or the demand watcher would undo it a second
        # later and the control would look broken.
        _device._manual = state == "on"
        _device.set_open(state == "on")
        # The stream closes on the reading thread's next pass, so report what
        # actually happened rather than what was asked for.
        want = state == "on"
        for _ in range(30):
            if _device.is_open == want:
                break
            time.sleep(0.1)
    return "on" if _device.is_open else "off"


def room_level() -> tuple[float, float]:
    """Current noise floor and the threshold it produces."""
    if _device is not None:
        return _threshold_from(_device._levels) / MARGIN, _device.threshold
    return 0.0, FLOOR


def trim(pcm: "np.ndarray", threshold: float, pad: float = 0.2) -> "np.ndarray":
    """Cut the quiet ends off a clip, keeping a little padding.

    A barge-in clip is mostly speaker bleed with a short burst of voice in it.
    Handing all of that to a transcriber gives it far more noise than signal,
    which is how "stop" comes back as "alright". Sending the voice alone is a
    dozen lines and removes the guesswork.
    """
    if pcm.size == 0:
        return pcm
    blocks = pcm[:pcm.size - pcm.size % BLOCK].reshape(-1, BLOCK)
    loud = np.where(np.sqrt((blocks ** 2).mean(axis=1)) > threshold)[0]
    if loud.size == 0:
        return pcm
    pad_blocks = max(1, int(pad * SAMPLE_RATE / BLOCK))
    start = max(0, loud[0] - pad_blocks)
    end = min(blocks.shape[0], loud[-1] + pad_blocks + 1)
    return blocks[start:end].reshape(-1)


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
