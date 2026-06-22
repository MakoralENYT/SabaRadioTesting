"""Configuration models for Saba Radio automation."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict, fields
from pathlib import Path
import json
from .community import BingoConfig, BingoPattern

SUPPORTED_EXTENSIONS = {'.wav', '.mp3', '.flac', '.ogg', '.aac', '.m4a'}
EQ_BANDS_HZ = (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)

@dataclass
class AudioConfig:
    music_folder: str = 'music'
    cable_device_name: str = 'CABLE Input'
    extra_output_device_names: list[str] = field(default_factory=list)
    volume: float = 1.0
    shuffle: bool = True
    loop: bool = True
    crossfade_seconds: float = 3.0
    monitor_local: bool = True
    broadcast_processing: bool = False
    chunk_size: int = 2048
    target_lufs: float = -16.0
    compressor_threshold_db: float = -18.0
    compressor_ratio: float = 3.0
    limiter_ceiling_db: float = -1.0
    eq_gains_db: dict[int, float] = field(default_factory=lambda: {band: 0.0 for band in EQ_BANDS_HZ})

@dataclass
class DiscordFeatureConfig:
    request_command_enabled: bool = True
    upload_command_enabled: bool = True
    bingo_command_enabled: bool = True
    send_audio_files: bool = False


@dataclass
class AppConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    bingo: BingoConfig = field(default_factory=BingoConfig)
    database_path: str = 'saba_radio.sqlite3'
    recordings_folder: str = 'recordings'
    archive_folder: str = 'archives'
    upload_folder: str = 'uploads'
    web_host: str = '127.0.0.1'
    web_port: int = 8765
    discord_token: str = ''
    discord_webhook_url: str = ''
    discord_features: DiscordFeatureConfig = field(default_factory=DiscordFeatureConfig)
    log_file: str = 'saba_radio.log'
    theme: str = 'dark'

    @classmethod
    def load(cls, path: str | Path = 'saba_radio.json') -> 'AppConfig':
        config_path = Path(path)
        if not config_path.exists():
            cfg = cls(); cfg.save(config_path); return cfg
        data = json.loads(config_path.read_text(encoding='utf-8'))
        audio_data = data.get('audio', {})
        bingo_data = data.get('bingo', {})
        audio_fields = {item.name for item in fields(AudioConfig)}
        discord_feature_fields = {item.name for item in fields(DiscordFeatureConfig)}
        bingo_fields = {item.name for item in fields(BingoConfig)}
        app_fields = {item.name for item in fields(cls)}
        audio = AudioConfig(**{key: value for key, value in audio_data.items() if key in audio_fields})
        discord_features = DiscordFeatureConfig(**{key: value for key, value in data.get('discord_features', {}).items() if key in discord_feature_fields})
        if "custom_patterns" in bingo_data:
            bingo_data["custom_patterns"] = tuple(
                BingoPattern(
                    name=item["name"],
                    positions=frozenset(tuple(position) for position in item.get("positions", [])),
                    prize=item.get("prize", ""),
                )
                for item in bingo_data.get("custom_patterns", [])
            )
        bingo = BingoConfig(**{key: value for key, value in bingo_data.items() if key in bingo_fields})
        data = {key: value for key, value in data.items() if key in app_fields}
        data['audio'] = audio
        data['bingo'] = bingo
        data['discord_features'] = discord_features
        return cls(**data)

    def save(self, path: str | Path = 'saba_radio.json') -> None:
        Path(path).write_text(json.dumps(to_jsonable(asdict(self)), indent=2), encoding='utf-8')


def to_jsonable(value):
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_jsonable(item) for item in value]
    return value
