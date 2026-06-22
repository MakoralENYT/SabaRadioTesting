"""Thread-safe audio engine with real-time PyAudio playback and pydub decoding."""
from __future__ import annotations

import importlib.util
import logging
import math
import threading
import time
import wave
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .config import AudioConfig, EQ_BANDS_HZ


@dataclass
class MeterState:
    vu_left: float = 0.0
    vu_right: float = 0.0
    peak: float = 0.0
    clipping: bool = False
    spectrum: list[float] = field(default_factory=list)


@dataclass
class OutputStream:
    role: str
    stream: Any


class AudioProcessor:
    """Applies broadcast-safe processing and keeps meter state up to date."""

    def __init__(self, config: AudioConfig) -> None:
        self.config = config
        self.meters = MeterState()

    def process(self, samples: np.ndarray) -> np.ndarray:
        audio = samples.astype(np.float32)
        if self.config.broadcast_processing:
            audio = self._normalize_lufs(audio)
            audio = self._eq(audio)
            audio = self._compress(audio)
            audio = self._limit(audio)
        audio *= self.config.volume
        audio = np.clip(audio, -32768, 32767)
        self._meter(audio)
        return audio.astype(np.int16)

    def equal_power_mix(self, a: np.ndarray, b: np.ndarray, progress: float) -> np.ndarray:
        n = min(len(a), len(b))
        p = max(0.0, min(1.0, progress))
        gain_a = math.cos(p * math.pi / 2.0)
        gain_b = math.sin(p * math.pi / 2.0)
        return np.clip(a[:n].astype(np.float32) * gain_a + b[:n].astype(np.float32) * gain_b, -32768, 32767).astype(np.int16)

    def _normalize_lufs(self, audio: np.ndarray) -> np.ndarray:
        rms = float(np.sqrt(np.mean(np.square(audio))) or 1.0)
        current_db = 20 * math.log10(rms / 32768.0 + 1e-9)
        gain_db = min(self.config.target_lufs - current_db, 12.0)
        return audio * (10 ** (gain_db / 20.0))

    def _compress(self, audio: np.ndarray) -> np.ndarray:
        threshold = 32768 * (10 ** (self.config.compressor_threshold_db / 20.0))
        over = np.abs(audio) > threshold
        audio[over] = np.sign(audio[over]) * (threshold + (np.abs(audio[over]) - threshold) / max(self.config.compressor_ratio, 1.0))
        return audio

    def _limit(self, audio: np.ndarray) -> np.ndarray:
        ceiling = 32768 * (10 ** (self.config.limiter_ceiling_db / 20.0))
        if np.any(np.abs(audio) > ceiling):
            audio = np.tanh(audio / ceiling) * ceiling
        return audio

    def _eq(self, audio: np.ndarray) -> np.ndarray:
        # Lightweight global gain hook driven by the 10 configured bands. This keeps the processing path
        # real-time safe while leaving room for a future true filter-bank implementation.
        gain = sum(self.config.eq_gains_db.get(band, 0.0) for band in EQ_BANDS_HZ) / len(EQ_BANDS_HZ)
        return audio * (10 ** (gain / 20.0))

    def _meter(self, audio: np.ndarray) -> None:
        peak = float(np.max(np.abs(audio)) if len(audio) else 0.0)
        rms = float(np.sqrt(np.mean(np.square(audio))) if len(audio) else 0.0)
        spectrum = np.abs(np.fft.rfft(audio[:2048])).tolist()[:64] if len(audio) else []
        self.meters = MeterState(rms / 32768.0, rms / 32768.0, peak / 32768.0, peak >= 32767, spectrum)


class PyAudioOutput:
    """Small adapter that fans processed chunks out to VB-CABLE and monitor devices."""

    def __init__(self, config: AudioConfig) -> None:
        if not importlib.util.find_spec("pyaudio"):
            raise RuntimeError("Install pyaudio to stream audio to VB-CABLE or speakers.")
        import pyaudio

        self.pyaudio = pyaudio
        self.config = config
        self.pa = pyaudio.PyAudio()

    def close(self) -> None:
        self.pa.terminate()

    def _device_index_containing(self, name: str) -> int | None:
        if not name:
            return None
        needle = name.lower()
        for index in range(self.pa.get_device_count()):
            info = self.pa.get_device_info_by_index(index)
            if needle in info.get("name", "").lower():
                return int(info["index"])
        return None

    def _default_output_index(self) -> int | None:
        try:
            return int(self.pa.get_default_output_device_info()["index"])
        except Exception:
            return None

    def open_streams(self, sample_rate: int, channels: int) -> list[OutputStream]:
        outputs: list[tuple[str, int]] = []
        cable_index = self._device_index_containing(self.config.cable_device_name)
        if cable_index is not None:
            outputs.append(("cable", cable_index))
        default_index = self._default_output_index()
        if default_index is not None and default_index not in [index for _, index in outputs]:
            # Keep the monitor stream open for the track so the user can mute/unmute locally
            # without reopening devices or interrupting the VB-CABLE stream.
            outputs.append(("monitor", default_index))
        for name in self.config.extra_output_device_names:
            device_index = self._device_index_containing(name)
            if device_index is not None and device_index not in [index for _, index in outputs]:
                outputs.append(("extra", device_index))
        return [
            OutputStream(
                role=role,
                stream=self.pa.open(
                    format=self.pyaudio.paInt16,
                    channels=channels,
                    rate=sample_rate,
                    output=True,
                    output_device_index=index,
                    frames_per_buffer=self.config.chunk_size,
                ),
            )
            for role, index in outputs
        ]


class RadioEngine:
    """Blocking real-time file player used by UI/background automation loops."""

    def __init__(self, config: AudioConfig, status=lambda m: None, now_playing=lambda p: None) -> None:
        self.config = config
        self.status = status
        self.now_playing = now_playing
        self.processor = AudioProcessor(config)
        self.lock = threading.RLock()
        self.running = False
        self.log = logging.getLogger(__name__)
        self._output: PyAudioOutput | None = None

    def decode_file(self, path: str) -> tuple[np.ndarray, int, int]:
        if path.lower().endswith(".wav"):
            with wave.open(path, "rb") as wf:
                return np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16), wf.getframerate(), wf.getnchannels()
        if importlib.util.find_spec("pydub"):
            from pydub import AudioSegment

            segment = AudioSegment.from_file(path).set_sample_width(2)
            return np.array(segment.get_array_of_samples(), dtype=np.int16), segment.frame_rate, segment.channels
        raise RuntimeError("Install pydub and FFmpeg for MP3/FLAC/OGG/AAC/M4A playback.")

    def play_file(self, path: str) -> bool:
        """Play one file in real time; returns True when the track reached its end."""
        with self.lock:
            if not self.running:
                return False
            self.now_playing(path)
            samples, sample_rate, channels = self.decode_file(path)
            streams: list[OutputStream] = []
            try:
                streams = self._open_streams(sample_rate, channels)
                frames_per_chunk = max(1, self.config.chunk_size)
                sample_step = frames_per_chunk * max(1, channels)
                for offset in range(0, len(samples), sample_step):
                    if not self.running:
                        return False
                    chunk = samples[offset : offset + sample_step]
                    processed = self.processor.process(chunk)
                    payload = processed.tobytes()
                    if streams:
                        for output in streams:
                            if output.role == "monitor" and not self.config.monitor_local:
                                continue
                            output.stream.write(payload)
                    else:
                        # If PyAudio is unavailable, keep automation timing honest instead of instantly skipping.
                        time.sleep((len(chunk) / max(1, channels)) / sample_rate)
                return True
            finally:
                for output in streams:
                    output.stream.stop_stream()
                    output.stream.close()

    def _open_streams(self, sample_rate: int, channels: int) -> list[OutputStream]:
        if self._output is None:
            try:
                self._output = PyAudioOutput(self.config)
            except RuntimeError as exc:
                self.status(f"Audio output warning: {exc}; timing-only playback active")
                return []
        return self._output.open_streams(sample_rate, channels)

    def start(self) -> None:
        self.running = True
        self.status("Radio started")

    def stop(self) -> None:
        self.running = False
        self.status("Radio stopped")

    def shutdown(self) -> None:
        self.stop()
        if self._output is not None:
            self._output.close()
            self._output = None
