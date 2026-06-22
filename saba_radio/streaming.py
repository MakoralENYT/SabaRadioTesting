"""Streaming output configuration for Icecast, SHOUTcast, RTMP, and devices."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class StreamTarget:
    kind: str
    url: str
    username: str = ''
    password: str = ''
    enabled: bool = True

class MultiOutputRouter:
    def __init__(self) -> None: self.targets: list[StreamTarget] = []; self.device_names: list[str] = []
    def add_stream(self, target: StreamTarget) -> None: self.targets.append(target)
    def add_device(self, name: str) -> None: self.device_names.append(name)
    def active_outputs(self) -> dict[str, list[str]]:
        return {'streams':[t.url for t in self.targets if t.enabled], 'devices': self.device_names[:]}
