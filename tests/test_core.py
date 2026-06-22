import tempfile, wave
from datetime import datetime, time, timedelta
from pathlib import Path
from saba_radio.metadata import MetadataReader
from saba_radio.queueing import SmartQueue
from saba_radio.scheduler import AutomationScheduler
from saba_radio.models import ScheduledPlaylist, RadioEvent


def test_smart_queue_priority_and_recent():
    q=SmartQueue(anti_repeat_window=2); q.add('normal',100); q.add('urgent',1)
    assert q.next(['a','b']) == 'urgent'
    assert 'urgent' in q.recently_played


def test_scheduler_active_and_due_event():
    s=AutomationScheduler(); now=datetime(2026,6,21,12,0)
    s.add_playlist(ScheduledPlaylist('show','playlist.m3u',time(11),time(13),{now.weekday()}))
    s.add_event(RadioEvent('top',now-timedelta(seconds=1),'play_jingle'))
    assert s.active_playlist(now).name == 'show'
    assert len(s.due_events(now)) == 1


def test_metadata_wav_duration():
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/'tone.wav'
        with wave.open(str(path),'wb') as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(8000); wf.writeframes((b"\0\0" * 8000))
        meta=MetadataReader().read(path)
        assert meta.title == 'tone'
        assert 0.9 < meta.duration < 1.1


def test_default_config_uses_plain_playback():
    from saba_radio.config import AudioConfig
    cfg = AudioConfig()
    assert cfg.volume == 1.0
    assert cfg.broadcast_processing is False


def test_discord_webhook_payload(monkeypatch):
    from saba_radio.discord_integration import DiscordWebhookClient
    captured = {}

    class Response:
        status = 204
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = request.data.decode("utf-8")
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    sent = DiscordWebhookClient("https://discord.example/webhook").send_now_playing("song.wav")
    assert sent is True
    assert captured["url"] == "https://discord.example/webhook"
    assert "Now Playing" in captured["body"]
    assert "song.wav" in captured["body"]


def test_music_bingo_card_marks_played_songs_and_detects_winner():
    from saba_radio.community import CommunityManager
    songs = [f"Song {index}" for index in range(8)]
    community = CommunityManager()
    game = community.start_bingo("main", "Test Bingo", songs, size=3)
    card = community.bingo_card("main", "listener-1", "Listener One")
    winning_line = card.squares[0]
    for song in winning_line:
        winners = community.record_play(song)
    assert card.has_bingo()
    assert winners[0][0] is game
    assert winners[0][1] is card
    assert community.profile("listener-1").bingo_wins == 1


def test_community_votes_dedications_embeds_and_leaderboard():
    from saba_radio.community import CommunityManager
    community = CommunityManager()
    community.vote_song("1", "Alice", "Track A", weight=2)
    community.add_dedication("2", "Bob", "Track B", "For the night shift")
    community.record_play("/music/Track A.wav")
    assert community.vote_totals()["Track A"] == 2
    assert community.history_embed()["description"] == "Track A"
    assert community.listener_of_the_day().display_name in {"Alice", "Bob"}
    assert community.hall_of_fame()


def test_advanced_bingo_config_patterns_near_bingo_and_export():
    from saba_radio.community import BingoConfig, CommunityManager
    songs = [f"Advanced {index}" for index in range(24)]
    config = BingoConfig(
        size=5,
        enabled_patterns=("line", "four_corners", "blackout", "x", "plus", "postage_stamp"),
        prizes={"four_corners": "Sticker pack"},
        seed="test-seed",
    )
    community = CommunityManager()
    game = community.start_bingo("advanced", "Advanced Bingo", songs, config=config)
    card = community.bingo_card("advanced", "listener-advanced", "Advanced Listener")

    assert config.required_song_count() == 24
    assert any(pattern.name == "Four Corners" and pattern.prize == "Sticker pack" for pattern in config.patterns())

    first_row = card.squares[0]
    for song in first_row[:-1]:
        community.record_play(song)
    near = card.near_bingos(config.patterns())
    assert any(pattern.name == "Row 1" and missing == [first_row[-1]] for pattern, missing in near)

    winners = community.record_play(first_row[-1])
    assert winners[0][1].listener_id == "listener-advanced"
    assert game.win_log[0].patterns

    exported = game.export_cards()
    game.import_cards(exported)
    assert game.cards["listener-advanced"].to_dict()["squares"] == card.to_dict()["squares"]
    assert community.bingo_embed("advanced", "listener-advanced")["fields"][0]["name"] == "Completion"


def test_app_config_round_trips_custom_bingo_patterns(tmp_path):
    from saba_radio.config import AppConfig
    from saba_radio.community import BingoPattern
    path = tmp_path / "config.json"
    cfg = AppConfig()
    cfg.bingo.custom_patterns = (BingoPattern("Tiny Corner", frozenset({(0, 0)}), "Prize"),)
    cfg.save(path)
    loaded = AppConfig.load(path)
    assert loaded.bingo.custom_patterns[0].name == "Tiny Corner"
    assert (0, 0) in loaded.bingo.custom_patterns[0].positions
