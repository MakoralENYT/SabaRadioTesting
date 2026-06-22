"""Priority, request, smart shuffle, search, and anti-repeat queues."""
from __future__ import annotations
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
import heapq, random
from .config import SUPPORTED_EXTENSIONS
from .models import QueueItem

class SmartQueue:
    def __init__(self, anti_repeat_window: int = 25) -> None:
        self._heap: list[QueueItem] = []
        self.recently_played: deque[str] = deque(maxlen=anti_repeat_window)
        self.favorites: set[str] = set()
    def add(self, path: str, priority: int = 100, requester: str | None = None) -> None:
        heapq.heappush(self._heap, QueueItem(priority, datetime.now(UTC), path, requester))
    def drag_reorder(self, ordered_paths: list[str]) -> None:
        self._heap = [QueueItem(i, datetime.now(UTC), p) for i, p in enumerate(ordered_paths)]; heapq.heapify(self._heap)
    def next(self, library: list[str], shuffle: bool = True) -> str | None:
        if self._heap:
            item = heapq.heappop(self._heap); self.mark_played(item.path); return item.path
        candidates = [p for p in library if p not in self.recently_played] or library[:]
        if not candidates: return None
        pick = random.choice(candidates) if shuffle else candidates[0]
        self.mark_played(pick); return pick
    def mark_played(self, path: str) -> None: self.recently_played.append(path)
    def upcoming(self, limit: int = 10) -> list[str]: return [i.path for i in sorted(self._heap)[:limit]]
    @staticmethod
    def scan(folder: str) -> list[str]:
        root=Path(folder)
        return sorted(str(p) for p in root.rglob('*') if p.suffix.lower() in SUPPORTED_EXTENSIONS) if root.exists() else []
    @staticmethod
    def search(paths: list[str], query: str) -> list[str]:
        q=query.lower(); return [p for p in paths if q in Path(p).name.lower()]
