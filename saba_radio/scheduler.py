"""Time-based playlist, show, and event scheduling."""
from __future__ import annotations
from datetime import datetime
from .models import ScheduledPlaylist, RadioEvent

class AutomationScheduler:
    def __init__(self) -> None:
        self.playlists: list[ScheduledPlaylist] = []
        self.events: list[RadioEvent] = []
    def add_playlist(self, playlist: ScheduledPlaylist) -> None: self.playlists.append(playlist)
    def add_event(self, event: RadioEvent) -> None: self.events.append(event); self.events.sort(key=lambda e: e.when)
    def active_playlist(self, now: datetime | None = None) -> ScheduledPlaylist | None:
        now = now or datetime.now(); t = now.time()
        for p in self.playlists:
            if now.weekday() in p.days and p.start_time <= t <= p.end_time: return p
        return None
    def due_events(self, now: datetime | None = None) -> list[RadioEvent]:
        now = now or datetime.now(); due=[e for e in self.events if e.when <= now]; self.events=[e for e in self.events if e.when > now]; return due
