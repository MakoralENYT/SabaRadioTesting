"""Broadcast recording and archive organization."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import wave

class BroadcastRecorder:
    def __init__(self, folder: str='recordings') -> None: self.folder=Path(folder); self.folder.mkdir(exist_ok=True); self._writer=None
    def start(self, sample_rate=44100, channels=2) -> Path:
        path=self.folder/datetime.utcnow().strftime('%Y/%m/%d/session-%H%M%S.wav'); path.parent.mkdir(parents=True, exist_ok=True)
        self._writer=wave.open(str(path),'wb'); self._writer.setnchannels(channels); self._writer.setsampwidth(2); self._writer.setframerate(sample_rate); return path
    def write(self, data: bytes) -> None:
        if self._writer: self._writer.writeframes(data)
    def stop(self) -> None:
        if self._writer: self._writer.close(); self._writer=None
