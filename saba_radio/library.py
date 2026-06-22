"""Hot-reloading music library scanner."""
from __future__ import annotations
from pathlib import Path
import threading, time
from .queueing import SmartQueue

class MusicLibrary:
    def __init__(self, folder: str, on_change=lambda paths: None) -> None:
        self.folder=folder; self.on_change=on_change; self.paths: list[str]=[]; self.running=False
    def scan(self) -> list[str]: self.paths=SmartQueue.scan(self.folder); return self.paths
    def watch(self, interval: float=2.0) -> None:
        def loop():
            old=set(self.scan())
            while self.running:
                time.sleep(interval); new=set(self.scan())
                if new != old: old=new; self.on_change(self.paths)
        self.running=True; threading.Thread(target=loop, daemon=True).start()
    def stop(self) -> None: self.running=False
