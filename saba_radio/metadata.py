"""Metadata reading with optional Mutagen support and stdlib WAV fallback."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import wave
from .models import TrackMetadata

class MetadataReader:
    def read(self, path: str | Path) -> TrackMetadata:
        p = Path(path)
        meta = TrackMetadata(path=str(p), title=p.stem)
        if importlib.util.find_spec('mutagen'):
            from mutagen import File
            audio = File(str(p), easy=True)
            if audio:
                meta.title = self._first(audio.get('title')) or p.stem
                meta.artist = self._first(audio.get('artist')) or ''
                meta.album = self._first(audio.get('album')) or ''
                meta.genre = self._first(audio.get('genre')) or ''
                meta.duration = float(getattr(audio.info, 'length', 0.0) or 0.0)
            art = File(str(p), easy=False)
            pictures = getattr(art, 'pictures', None) if art else None
            if pictures:
                art_dir = p.parent / '.album_art'; art_dir.mkdir(exist_ok=True)
                out = art_dir / f'{p.stem}.art'
                out.write_bytes(pictures[0].data); meta.album_art_path = str(out)
            return meta
        if p.suffix.lower() == '.wav':
            with wave.open(str(p), 'rb') as wf:
                meta.duration = wf.getnframes() / float(wf.getframerate())
        return meta

    @staticmethod
    def _first(value: object) -> str:
        if isinstance(value, (list, tuple)) and value:
            return str(value[0])
        return str(value) if value else ''
