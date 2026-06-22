"""Shared domain models."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path
from typing import Any

@dataclass(slots=True)
class TrackMetadata:
    path: str
    title: str = ''
    artist: str = ''
    album: str = ''
    genre: str = ''
    duration: float = 0.0
    album_art_path: str | None = None
    lufs: float | None = None
    replay_gain_db: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

@dataclass(order=True, slots=True)
class QueueItem:
    priority: int
    inserted_at: datetime
    path: str = field(compare=False)
    requester: str | None = field(default=None, compare=False)
    request_id: str | None = field(default=None, compare=False)

@dataclass(slots=True)
class ScheduledPlaylist:
    name: str
    playlist_path: str
    start_time: time
    end_time: time
    days: set[int] = field(default_factory=lambda: set(range(7)))

@dataclass(slots=True)
class RadioEvent:
    name: str
    when: datetime
    action: str
    payload: dict[str, Any] = field(default_factory=dict)
