"""Optional Flask REST dashboard and WebSocket-style state broadcaster."""
from __future__ import annotations
import importlib.util, shutil, threading
from pathlib import Path


class WebDashboard:
    def __init__(self, app_state: dict, host='127.0.0.1', port=8765) -> None:
        self.app_state=app_state; self.host=host; self.port=port; self.thread=None
    def create_app(self):
        if not importlib.util.find_spec('flask'): raise RuntimeError('Install flask for the web dashboard.')
        from flask import Flask, jsonify, redirect, request
        app=Flask(__name__)
        @app.get('/')
        def panel():
            uploads = self._pending_uploads()
            rows = ''.join(
                f"<tr><td>{item['id']}</td><td>{item['filename']}</td><td>{item['requester']}</td>"
                f"<td><form method='post' action='/uploads/{item['id']}/approve'><button>Approve</button></form></td>"
                f"<td><form method='post' action='/uploads/{item['id']}/deny'><button>Deny</button></form></td></tr>"
                for item in uploads
            ) or "<tr><td colspan='5'>No pending uploads</td></tr>"
            return f"""<!doctype html><title>Saba Radio Uploads</title><h1>Pending Audio Uploads</h1>
            <table border='1' cellpadding='8'><tr><th>ID</th><th>File</th><th>Requester</th><th colspan='2'>Action</th></tr>{rows}</table>"""
        @app.get('/api/now-playing')
        def now_playing(): return jsonify(self.app_state.get('now_playing', {}))
        @app.get('/api/queue')
        def queue(): return jsonify(self.app_state.get('queue', []))
        @app.post('/api/control/<action>')
        def control(action): self.app_state['last_command']=action; return jsonify({'ok': True, 'action': action})
        @app.get('/api/statistics')
        def stats(): return jsonify(self.app_state.get('statistics', {}))
        @app.post('/api/queue')
        def add_queue(): self.app_state.setdefault('requests', []).append(request.json or {}); return jsonify({'ok': True})
        @app.get('/api/uploads')
        def uploads(): return jsonify(self._pending_uploads())
        @app.post('/uploads/<int:request_id>/approve')
        @app.post('/api/uploads/<int:request_id>/approve')
        def approve_upload(request_id):
            item = self._review_upload(request_id, 'approved')
            return redirect('/') if not request.path.startswith('/api/') else jsonify({'ok': bool(item), 'upload': item})
        @app.post('/uploads/<int:request_id>/deny')
        @app.post('/api/uploads/<int:request_id>/deny')
        def deny_upload(request_id):
            item = self._review_upload(request_id, 'denied')
            return redirect('/') if not request.path.startswith('/api/') else jsonify({'ok': bool(item), 'upload': item})
        return app
    def _pending_uploads(self) -> list[dict]:
        db = self.app_state.get('database')
        return db.upload_requests('pending') if db else self.app_state.get('uploads', [])
    def _review_upload(self, request_id: int, status: str) -> dict | None:
        db = self.app_state.get('database')
        item = db.review_upload_request(request_id, status) if db else None
        if item and status == 'approved':
            music_folder = Path(self.app_state.get('music_folder', 'music'))
            music_folder.mkdir(parents=True, exist_ok=True)
            target = music_folder / Path(item['stored_path']).name
            shutil.copy2(item['stored_path'], target)
            if self.app_state.get('on_upload_approved'):
                self.app_state['on_upload_approved'](str(target))
        return item
    def start_background(self) -> None:
        app=self.create_app(); self.thread=threading.Thread(target=lambda: app.run(self.host,self.port), daemon=True); self.thread.start()
