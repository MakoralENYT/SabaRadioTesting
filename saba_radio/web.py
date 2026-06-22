"""Optional Flask REST dashboard and WebSocket-style state broadcaster."""
from __future__ import annotations
import importlib.util, threading

class WebDashboard:
    def __init__(self, app_state: dict, host='127.0.0.1', port=8765) -> None:
        self.app_state=app_state; self.host=host; self.port=port; self.thread=None
    def create_app(self):
        if not importlib.util.find_spec('flask'): raise RuntimeError('Install flask for the web dashboard.')
        from flask import Flask, jsonify, request
        app=Flask(__name__)
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
        return app
    def start_background(self) -> None:
        app=self.create_app(); self.thread=threading.Thread(target=lambda: app.run(self.host,self.port), daemon=True); self.thread.start()
