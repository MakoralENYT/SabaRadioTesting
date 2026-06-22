"""SQLite persistence for metadata, play history, requests, and statistics."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import UTC, datetime
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
            create table if not exists audio_files(path text primary key,filename text,mime_type text,content blob,updated_at text default current_timestamp);
            create table if not exists upload_requests(id integer primary key autoincrement,filename text,stored_path text,requester text,status text default 'pending',created_at text default current_timestamp,reviewed_at text,note text);
            create table if not exists statistics(key text primary key,value text);
            ''')
    def upsert_track(self, m: TrackMetadata) -> None:
        with self.connect() as db:
            db.execute('replace into tracks values(?,?,?,?,?,?,?,?,?)',(m.path,m.title,m.artist,m.album,m.genre,m.duration,m.album_art_path,m.lufs,m.replay_gain_db))

    def import_audio_file(self, path: str, mime_type: str = 'application/octet-stream') -> None:
        audio_path = Path(path)
        with self.connect() as db:
            db.execute(
                'replace into audio_files(path,filename,mime_type,content,updated_at) values(?,?,?,?,?)',
                (str(audio_path), audio_path.name, mime_type, audio_path.read_bytes(), datetime.now(UTC).isoformat()),
            )

    def materialize_audio_file(self, path: str, folder: str) -> str | None:
        with self.connect() as db:
            row = db.execute('select filename,content from audio_files where path=?', (path,)).fetchone()
        if not row:
            return None
        target = Path(folder) / row[0]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(row[1])
        return str(target)

    def track_paths(self) -> list[str]:
        with self.connect() as db:
            rows = db.execute('select path from tracks order by title,path').fetchall()
        return [row[0] for row in rows]
    def record_play(self, path: str) -> None:
        with self.connect() as db: db.execute('insert into play_history(path) values(?)',(path,))
    def add_request(self, path: str, requester: str) -> None:
        with self.connect() as db: db.execute('insert into requests(path,requester) values(?,?)',(path,requester))


    def add_upload_request(self, filename: str, stored_path: str, requester: str) -> int:
        with self.connect() as db:
            cursor = db.execute('insert into upload_requests(filename,stored_path,requester) values(?,?,?)', (filename, stored_path, requester))
            return int(cursor.lastrowid)

    def upload_requests(self, status: str = 'pending') -> list[dict]:
        with self.connect() as db:
            rows = db.execute('select id,filename,stored_path,requester,status,created_at,note from upload_requests where status=? order by created_at desc', (status,)).fetchall()
        keys = ('id', 'filename', 'stored_path', 'requester', 'status', 'created_at', 'note')
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def review_upload_request(self, request_id: int, status: str, note: str = '') -> dict | None:
        if status not in {'approved', 'denied'}:
            raise ValueError('status must be approved or denied')
        with self.connect() as db:
            row = db.execute('select id,filename,stored_path,requester,status,created_at,note from upload_requests where id=?', (request_id,)).fetchone()
            if not row:
                return None
            db.execute('update upload_requests set status=?, reviewed_at=?, note=? where id=?', (status, datetime.now(UTC).isoformat(), note, request_id))
        keys = ('id', 'filename', 'stored_path', 'requester', 'status', 'created_at', 'note')
        result = dict(zip(keys, row, strict=True))
        result['status'] = status
        result['note'] = note
        return result
