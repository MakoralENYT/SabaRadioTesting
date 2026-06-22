"""Saba Radio desktop launcher preserving the original Tkinter workflow."""
from __future__ import annotations
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from saba_radio import AppConfig, RadioDatabase, MetadataReader, SmartQueue, AutomationScheduler, CommunityManager
from saba_radio.audio import RadioEngine
from saba_radio.discord_integration import DiscordRadioBot, DiscordWebhookClient
from saba_radio.library import MusicLibrary
from saba_radio.recording import BroadcastRecorder
from saba_radio.streaming import MultiOutputRouter
from saba_radio.web import WebDashboard

class RadioGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root=root; self.config=AppConfig.load(); self.db=RadioDatabase(self.config.database_path); self.metadata=MetadataReader(); self.queue=SmartQueue(); self.scheduler=AutomationScheduler(); self.recorder=BroadcastRecorder(self.config.recordings_folder); self.outputs=MultiOutputRouter(); self.community=CommunityManager(); self.app_state={'database': self.db, 'music_folder': self.config.audio.music_folder, 'on_upload_approved': self.on_upload_approved}; self.dashboard=WebDashboard(self.app_state, self.config.web_host, self.config.web_port); self.webhook=DiscordWebhookClient(self.config.discord_webhook_url); self.engine=RadioEngine(self.config.audio, self.set_status, self.set_now_playing); self.library=MusicLibrary(self.config.audio.music_folder, self.on_library_changed)
        self.root.title('Saba Radio Automation'); self.root.geometry('1280x780'); self.root.minsize(1050,680); self.root.configure(bg='#07111f')
        self.status_var=tk.StringVar(value='Ready'); self.song_var=tk.StringVar(value='Nothing Playing'); self.search_var=tk.StringVar(); self.volume_var=tk.DoubleVar(value=self.config.audio.volume); self.crossfade_var=tk.DoubleVar(value=self.config.audio.crossfade_seconds); self.shuffle_var=tk.BooleanVar(value=self.config.audio.shuffle); self.loop_var=tk.BooleanVar(value=self.config.audio.loop); self.monitor_var=tk.BooleanVar(value=self.config.audio.monitor_local); self.processing_var=tk.BooleanVar(value=self.config.audio.broadcast_processing); self.webhook_var=tk.StringVar(value=self.config.discord_webhook_url); self.discord_token_var=tk.StringVar(value=self.config.discord_token); self.command_var=tk.StringVar(); self.requests_enabled_var=tk.BooleanVar(value=self.config.discord_features.request_command_enabled); self.discord_files_var=tk.BooleanVar(value=self.config.discord_features.send_audio_files); self.playback_thread: threading.Thread | None = None; self.discord_thread: threading.Thread | None = None
        self.build_layout(); self.refresh_library(); self.library.watch(); self.root.protocol('WM_DELETE_WINDOW', self.on_close)
    def build_layout(self) -> None:
        style=ttk.Style(); style.theme_use('clam'); style.configure('Dark.TFrame', background='#0f172a'); style.configure('Card.TFrame', background='#111c31'); style.configure('Title.TLabel', background='#0f172a', foreground='#f8fafc', font=('Segoe UI',24,'bold')); style.configure('Body.TLabel', background='#111c31', foreground='#dbeafe', font=('Segoe UI',10)); style.configure('Value.TLabel', background='#111c31', foreground='#ffffff', font=('Segoe UI',14,'bold'))
        shell=ttk.Frame(self.root, style='Dark.TFrame', padding=18); shell.pack(fill='both', expand=True)
        ttk.Label(shell, text='Saba Radio Automation Console', style='Title.TLabel').pack(anchor='w')
        panes=ttk.PanedWindow(shell, orient='horizontal'); panes.pack(fill='both', expand=True, pady=12)
        left=ttk.Frame(panes, style='Card.TFrame', padding=14); mid=ttk.Frame(panes, style='Card.TFrame', padding=14); right=ttk.Frame(panes, style='Card.TFrame', padding=14); panes.add(left, weight=2); panes.add(mid, weight=3); panes.add(right, weight=2)
        ttk.Label(left,text='Now Playing',style='Body.TLabel').pack(anchor='w'); ttk.Label(left,textvariable=self.song_var,style='Value.TLabel').pack(anchor='w',pady=(3,10)); ttk.Label(left,textvariable=self.status_var,style='Body.TLabel').pack(anchor='w')
        self.vu=tk.Canvas(left,height=90,bg='#08111f',highlightthickness=0); self.vu.pack(fill='x',pady=12); self.vu.create_rectangle(10,25,10,45,fill='#22c55e',tags='vu'); self.vu.create_text(12,70,anchor='w',fill='#93c5fd',text='Animated VU / peak / clipping meters')
        ttk.Label(left,text='Controls',style='Value.TLabel').pack(anchor='w',pady=(10,4)); ttk.Scale(left,from_=0,to=1,variable=self.volume_var,command=lambda _: self.apply_settings()).pack(fill='x'); ttk.Scale(left,from_=0,to=15,variable=self.crossfade_var,command=lambda _: self.apply_settings()).pack(fill='x',pady=4); ttk.Checkbutton(left,text='Smart shuffle',variable=self.shuffle_var,command=self.apply_settings).pack(anchor='w'); ttk.Checkbutton(left,text='Loop automation',variable=self.loop_var,command=self.apply_settings).pack(anchor='w'); ttk.Checkbutton(left,text='Hear locally (does not affect VB-CABLE)',variable=self.monitor_var,command=self.apply_settings).pack(anchor='w'); ttk.Checkbutton(left,text='Broadcast processing / normalization',variable=self.processing_var,command=self.apply_settings).pack(anchor='w'); ttk.Button(left,text='▶ Start',command=self.start_radio).pack(fill='x',pady=(12,4)); ttk.Button(left,text='■ Stop',command=self.stop_radio).pack(fill='x')
        ttk.Label(mid,text='Music Library / Search',style='Value.TLabel').pack(anchor='w'); ttk.Entry(mid,textvariable=self.search_var).pack(fill='x',pady=5); self.search_var.trace_add('write',lambda *_: self.populate_library()); self.library_box=tk.Listbox(mid,bg='#08111f',fg='white',selectbackground='#2563eb',borderwidth=0); self.library_box.pack(fill='both',expand=True); ttk.Button(mid,text='Add Selected to Priority Queue',command=self.add_selected).pack(fill='x',pady=6)
        ttk.Label(right,text='Discord Webhook URL',style='Body.TLabel').pack(anchor='w'); ttk.Entry(right,textvariable=self.webhook_var,show='•').pack(fill='x',pady=(0,8)); ttk.Label(right,text='Discord Bot Token',style='Body.TLabel').pack(anchor='w'); ttk.Entry(right,textvariable=self.discord_token_var,show='•').pack(fill='x',pady=(0,8)); ttk.Button(right,text='Save Discord Settings',command=self.apply_settings).pack(fill='x',pady=(0,6)); ttk.Button(right,text='Start Discord Bot',command=self.start_discord_bot).pack(fill='x',pady=(0,6)); ttk.Button(right,text='Start Upload Review Panel',command=self.start_dashboard).pack(fill='x',pady=(0,6)); ttk.Checkbutton(right,text='Enable !request',variable=self.requests_enabled_var,command=self.apply_settings).pack(anchor='w'); ttk.Checkbutton(right,text='Allow Discord audio files',variable=self.discord_files_var,command=self.apply_settings).pack(anchor='w'); ttk.Button(right,text='Activate Requesting Hour',command=self.activate_requesting_hour).pack(fill='x',pady=(0,10)); ttk.Label(right,text='Priority / Request Queue',style='Value.TLabel').pack(anchor='w'); self.queue_box=tk.Listbox(right,bg='#08111f',fg='white',borderwidth=0); self.queue_box.pack(fill='both',expand=True); ttk.Label(right,text='Command Prompt',style='Body.TLabel').pack(anchor='w',pady=(8,0)); ttk.Entry(right,textvariable=self.command_var).pack(fill='x',pady=(0,4)); ttk.Button(right,text='Run Command',command=self.run_command_prompt).pack(fill='x'); ttk.Label(right,text='Automation modules ready: scheduler, REST dashboard, Discord bot, SQLite stats, recording, streaming outputs, themes, diagnostics.',style='Body.TLabel',wraplength=300).pack(anchor='w',pady=10)
    def apply_settings(self) -> None:
        self.config.audio.volume=float(self.volume_var.get()); self.config.audio.crossfade_seconds=float(self.crossfade_var.get()); self.config.audio.shuffle=bool(self.shuffle_var.get()); self.config.audio.loop=bool(self.loop_var.get()); self.config.audio.monitor_local=bool(self.monitor_var.get()); self.config.audio.broadcast_processing=bool(self.processing_var.get()); self.config.discord_webhook_url=self.webhook_var.get().strip(); self.config.discord_token=self.discord_token_var.get().strip(); self.config.discord_features.request_command_enabled=bool(self.requests_enabled_var.get()); self.config.discord_features.send_audio_files=bool(self.discord_files_var.get()); self.webhook.webhook_url=self.config.discord_webhook_url; self.config.save()
    def refresh_library(self) -> None:
        for path in self.library.scan(): self.db.upsert_track(self.metadata.read(path)); self.db.import_audio_file(path)
        if "main" not in self.community.bingo_games and len(self.library.paths) >= 24:
            self.community.start_bingo("main", "Saba Radio Music Bingo", self.library.paths, config=self.config.bingo)
            self.set_status("Music bingo is ready: Discord listeners can request a card with !bingo card")
        self.populate_library()
    def populate_library(self) -> None:
        q=self.search_var.get(); paths=SmartQueue.search(self.library.paths,q) if q else self.library.paths; self.library_box.delete(0,tk.END)
        for p in paths: self.library_box.insert(tk.END, Path(p).name)
    def on_library_changed(self, paths: list[str]) -> None: self.root.after(0, self.refresh_library)
    def add_selected(self) -> None:
        idx=self.library_box.curselection();
        if not idx: return
        visible=SmartQueue.search(self.library.paths,self.search_var.get()) if self.search_var.get() else self.library.paths; path=visible[idx[0]]; self.queue.add(path, priority=1); self.queue_box.insert(tk.END, Path(path).name)

    def start_discord_bot(self) -> None:
        self.apply_settings()
        if not self.config.discord_token:
            messagebox.showwarning('Discord token missing', 'Paste a Discord bot token first, then click Start Discord Bot.')
            return
        if self.discord_thread and self.discord_thread.is_alive():
            self.set_status('Discord bot is already running')
            return
        bot=DiscordRadioBot(self.queue, lambda: self.song_var.get(), self.config.discord_token, self.community, lambda: self.library.paths, self.db, self.config.upload_folder, self.config.discord_features)
        self.discord_thread=threading.Thread(target=bot.run, daemon=True)
        self.discord_thread.start()
        self.set_status('Discord bot started')
    def start_dashboard(self) -> None:
        self.dashboard.start_background(); self.set_status(f'Upload review panel: http://{self.config.web_host}:{self.config.web_port}')
    def activate_requesting_hour(self) -> None:
        self.requests_enabled_var.set(True); self.apply_settings(); self.set_status('Requesting Hour active: !request is enabled')
    def on_upload_approved(self, path: str) -> None:
        self.db.upsert_track(self.metadata.read(path)); self.db.import_audio_file(path); self.refresh_library()
    def run_command_prompt(self) -> None:
        command=self.command_var.get().strip()
        if command.startswith('!shout '):
            message=command[len('!shout '):].strip()
            if self.webhook.enabled() and message:
                threading.Thread(target=lambda: self.webhook.send_message(message), daemon=True).start(); self.set_status('Shout sent to Discord webhook')
            else: self.set_status('Webhook URL or message missing')
        elif command == '!requests on': self.requests_enabled_var.set(True); self.apply_settings(); self.set_status('Requests enabled')
        elif command == '!requests off': self.requests_enabled_var.set(False); self.apply_settings(); self.set_status('Requests disabled')
        else: self.set_status('Unknown command')
    def start_radio(self) -> None:
        self.apply_settings(); self.refresh_library()
        if not self.library.paths: messagebox.showwarning('No music found','Place WAV, MP3, FLAC, OGG, AAC, or M4A files in the music folder.'); return
        self.engine.start()
        if not self.playback_thread or not self.playback_thread.is_alive():
            self.playback_thread=threading.Thread(target=self.playback_loop, daemon=True)
            self.playback_thread.start()
        self.animate_meters()
    def playback_loop(self) -> None:
        while self.engine.running:
            path=self.queue.next(self.library.paths,self.config.audio.shuffle)
            if not path:
                self.set_status('No playable tracks found')
                break
            completed=self.engine.play_file(path)
            if completed:
                self.db.record_play(path)
                winners=self.community.record_play(path)
                if winners:
                    names=", ".join(card.listener_id for _, card in winners)
                    self.set_status(f"Music bingo winner: {names}")
                self.root.after(0, self.refresh_queue_display)
            if not self.config.audio.loop and not self.queue.upcoming(1):
                self.engine.stop()
                break
    def refresh_queue_display(self) -> None:
        self.queue_box.delete(0, tk.END)
        for p in self.queue.upcoming(10): self.queue_box.insert(tk.END, Path(p).name)
    def animate_meters(self) -> None:
        m=self.engine.processor.meters; width=max(10,int(10+m.vu_left*500)); self.vu.coords('vu',10,25,width,45)
        if self.engine.running: self.root.after(100, self.animate_meters)
    def stop_radio(self) -> None: self.engine.stop()
    def set_status(self, text: str) -> None: self.root.after(0, lambda: self.status_var.set(text))
    def set_now_playing(self, path: str) -> None:
        name=Path(path).name
        self.root.after(0, lambda: self.song_var.set(name))
        if self.webhook.enabled():
            threading.Thread(target=lambda: self.webhook.send_now_playing(name), daemon=True).start()
    def on_close(self) -> None: self.library.stop(); self.engine.shutdown(); self.root.destroy()

if __name__ == '__main__':
    root=tk.Tk(); RadioGUI(root); root.mainloop()
