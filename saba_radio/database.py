"""SQLite persistence for metadata, play history, requests, and statistics."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from .models import TrackMetadata

class RadioDatabase:
    def __init__(self, path: str = 'saba_radio.sqlite3') -> None:
        self.path = path
        self._init()
    def connect(self):
        return sqlite3.connect(self.path, check_same_thread=False)
    def _init(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True) if Path(self.path).parent != Path('.') else None
        with self.connect() as db:
            db.executescript('''
            create table if not exists tracks(path text primary key,title text,artist text,album text,genre text,duration real,album_art_path text,lufs real,replay_gain_db real);
            create table if not exists play_history(id integer primary key autoincrement,path text,played_at text default current_timestamp,listener_count integer default 0);
            create table if not exists requests(id integer primary key autoincrement,path text,requester text,status text default 'queued',created_at text default current_timestamp);
            create table if not exists statistics(key text primary key,value text);
            ''')
    def upsert_track(self, m: TrackMetadata) -> None:
        with self.connect() as db:
            db.execute('replace into tracks values(?,?,?,?,?,?,?,?,?)',(m.path,m.title,m.artist,m.album,m.genre,m.duration,m.album_art_path,m.lufs,m.replay_gain_db))
    def record_play(self, path: str) -> None:
        with self.connect() as db: db.execute('insert into play_history(path) values(?)',(path,))
    def add_request(self, path: str, requester: str) -> None:
        with self.connect() as db: db.execute('insert into requests(path,requester) values(?,?)',(path,requester))
