# SabaRadioFeatureRich

Saba Radio is now structured as a professional Python radio automation platform while preserving the original Tkinter desktop launcher (`radionew.py`).

## Highlights

- Multi-format library scanning: WAV, MP3, FLAC, OGG, AAC, and M4A.
- Plain playback by default so songs are not colored or bass-boosted, with optional broadcast processing primitives: equal-power crossfade math, LUFS-style gain normalization, compressor, limiter, 10-band EQ configuration, VU/peak/clipping/spectrum meter state.
- Automation: smart queue, priority/request queue, anti-repeat history, search/filter, playlist/event scheduler.
- Metadata: ID3/tag reading and album art extraction when Mutagen is installed, with WAV duration fallback.
- SQLite persistence for metadata cache, play history, listener requests, and statistics.
- Optional integrations for Flask REST dashboard, Discord bot, Discord webhook now-playing posts, broadcast recording, and stream target routing.
- Community features: Discord requests/votes/dedications, real-time queue/history/now-playing embeds, listener XP/reputation/badges, listener-of-the-day, hall-of-fame leaderboard, polls, and advanced configurable music bingo with custom card sizes, free-space rules, deterministic card generation, line/four-corners/blackout/X/plus/postage-stamp/custom win patterns, near-bingo tracking, card export/import, prizes, and automatic winner detection.
- Config file support via `saba_radio.json`, local monitor mute/unmute without interrupting VB-CABLE, modular package layout, type hints, and unit-testable components.

## Optional dependencies

Core tests use the Python standard library. Runtime integrations are loaded only when installed:

- `pyaudio` for live device output / VB-CABLE routing.
- `pydub` and FFmpeg for non-WAV decoding.
- `mutagen` for rich tags and album art.
- `flask` for the REST dashboard.
- `discord.py` for Discord commands.

## Run

```bash
python radionew.py
```

Put music files in the configured `music` folder. The first launch creates `saba_radio.json`, including a `bingo` section you can edit to configure card size, enabled win patterns, free-space behavior, rewards, and prizes.

## Discord bot usage

The webhook field only posts now-playing updates. The interactive Discord bot is implemented separately and runs inside the Tkinter app when you provide a bot token.

1. Install the optional bot dependency:

```bash
pip install discord.py
```

2. In the Discord Developer Portal, create a bot, enable the Message Content Intent, invite it to your server, and copy its token.
3. Launch the app with `python radionew.py`.
4. Paste the token into **Discord Bot Token** and click **Start Discord Bot**.
5. Put at least 24 songs in your library for the default 5x5 music bingo game, then start the radio.

Available commands:

- `!now` — current now-playing text.
- `!request <song>` — add a priority listener request.
- `!queue` / `!upcoming` — show queued/upcoming songs.
- `!history` — show recent played songs.
- `!vote <song>` — vote for a song.
- `!dedicate <song> <message>` — save a listener dedication.
- `!bingo card [game_id]` — get your bingo card; default game is `main`.
- `!bingo board [game_id]` — show bingo leaderboard progress.
- `!bingo status [game_id]` — show your bingo completion and win status.
