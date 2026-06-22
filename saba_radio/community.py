"""Community engagement features with an advanced, configurable music bingo engine."""
from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterable


@dataclass(slots=True)
class ListenerProfile:
    listener_id: str
    display_name: str
    xp: int = 0
    reputation: int = 0
    badges: set[str] = field(default_factory=set)
    achievements: set[str] = field(default_factory=set)
    requests: int = 0
    votes: int = 0
    bingo_wins: int = 0
    trivia_wins: int = 0

    def award_xp(self, amount: int, reason: str = "") -> None:
        self.xp += max(0, amount)
        if self.xp >= 100:
            self.achievements.add("Century Club")
        if self.xp >= 500:
            self.achievements.add("Station Regular")
        if reason:
            self.badges.add(reason)


@dataclass(slots=True)
class Dedication:
    track: str
    listener_id: str
    message: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class SongVote:
    track: str
    voter_id: str
    weight: int = 1


@dataclass(slots=True)
class CommunityPoll:
    question: str
    options: list[str]
    votes: dict[str, str] = field(default_factory=dict)
    open: bool = True

    def vote(self, listener_id: str, option: str) -> None:
        if not self.open:
            raise ValueError("Poll is closed")
        if option not in self.options:
            raise ValueError("Unknown poll option")
        self.votes[listener_id] = option

    def results(self) -> Counter[str]:
        return Counter(self.votes.values())


@dataclass(frozen=True, slots=True)
class BingoPattern:
    """A named win pattern made of one or more required square positions."""

    name: str
    positions: frozenset[tuple[int, int]]
    prize: str = ""


@dataclass(slots=True)
class BingoConfig:
    """Configures card generation, win rules, late joins, and rewards."""

    size: int = 5
    free_space: bool = True
    free_space_label: str = "FREE SPACE"
    enabled_patterns: tuple[str, ...] = ("line",)
    max_cards_per_listener: int = 1
    allow_late_join: bool = True
    deterministic_cards: bool = True
    seed: str = "saba-radio-bingo"
    xp_for_card: int = 10
    xp_for_square: int = 1
    xp_for_win: int = 100
    require_exact_title_match: bool = False
    prizes: dict[str, str] = field(default_factory=dict)
    custom_patterns: tuple[BingoPattern, ...] = ()

    def required_song_count(self) -> int:
        count = self.size * self.size
        if self.free_space and self.size % 2 == 1:
            count -= 1
        return count

    def patterns(self) -> list[BingoPattern]:
        return build_bingo_patterns(self.size, self.enabled_patterns, self.prizes) + list(self.custom_patterns)


@dataclass(slots=True)
class BingoWin:
    game_id: str
    listener_id: str
    card_id: str
    patterns: list[str]
    track: str
    awarded_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class BingoCard:
    card_id: str
    listener_id: str
    size: int
    squares: list[list[str]]
    marked: set[tuple[int, int]] = field(default_factory=set)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    free_space_label: str = "FREE SPACE"

    def __post_init__(self) -> None:
        center = self.size // 2
        if self.size % 2 == 1 and self.squares[center][center] == self.free_space_label:
            self.marked.add((center, center))

    def slot_for_position(self, row: int, column: int) -> int:
        return (row * self.size) + column + 1

    def position_for_slot(self, slot: int) -> tuple[int, int]:
        if slot < 1 or slot > self.size * self.size:
            raise ValueError(f"Slot must be between 1 and {self.size * self.size}")
        return divmod(slot - 1, self.size)

    def song_at_slot(self, slot: int) -> str:
        row, column = self.position_for_slot(slot)
        return self.squares[row][column]

    def _matches_square(self, square: str, track: str, exact: bool = False) -> bool:
        if square == self.free_space_label:
            return False
        normalized = normalize_song_key(track)
        candidate = normalize_song_key(square)
        return candidate == normalized if exact else candidate == normalized or normalized in candidate or candidate in normalized

    def mark_track(self, track: str, exact: bool = False) -> list[tuple[int, int]]:
        hits: list[tuple[int, int]] = []
        for row_index, row in enumerate(self.squares):
            for column_index, square in enumerate(row):
                if self._matches_square(square, track, exact=exact):
                    position = (row_index, column_index)
                    self.marked.add(position)
                    hits.append(position)
        return hits

    def verify_slot(self, slot: int, played_tracks: Iterable[str], exact: bool = False) -> bool:
        row, column = self.position_for_slot(slot)
        square = self.squares[row][column]
        if square == self.free_space_label:
            self.marked.add((row, column))
            return True
        if any(self._matches_square(square, track, exact=exact) for track in played_tracks):
            self.marked.add((row, column))
            return True
        return False

    def winning_patterns(self, patterns: Iterable[BingoPattern] | None = None) -> list[BingoPattern]:
        available = list(patterns or build_bingo_patterns(self.size, ("line",), {}))
        return [pattern for pattern in available if pattern.positions <= self.marked]

    def has_bingo(self, patterns: Iterable[BingoPattern] | None = None) -> bool:
        return bool(self.winning_patterns(patterns))

    def near_bingos(self, patterns: Iterable[BingoPattern] | None = None, missing: int = 1) -> list[tuple[BingoPattern, list[str]]]:
        near: list[tuple[BingoPattern, list[str]]] = []
        for pattern in list(patterns or build_bingo_patterns(self.size, ("line",), {})):
            remaining = sorted(pattern.positions - self.marked)
            if len(remaining) == missing:
                near.append((pattern, [self.squares[row][column] for row, column in remaining]))
        return near

    def unmarked_squares(self) -> list[str]:
        return [square for row_index, row in enumerate(self.squares) for column_index, square in enumerate(row) if (row_index, column_index) not in self.marked]

    def completion_percent(self) -> float:
        return round((len(self.marked) / (self.size * self.size)) * 100, 2)

    def to_dict(self) -> dict:
        return {
            "card_id": self.card_id,
            "listener_id": self.listener_id,
            "size": self.size,
            "squares": self.squares,
            "marked": list(self.marked),
            "created_at": self.created_at.isoformat(),
            "free_space_label": self.free_space_label,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BingoCard":
        return cls(
            card_id=data["card_id"],
            listener_id=data["listener_id"],
            size=int(data["size"]),
            squares=data["squares"],
            marked={tuple(item) for item in data.get("marked", [])},
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(UTC),
            free_space_label=data.get("free_space_label", "FREE SPACE"),
        )

    def render_text(self, reveal_unmarked: bool = True) -> str:
        rows = []
        for row_index, row in enumerate(self.squares):
            rendered = []
            for column_index, square in enumerate(row):
                marked = (row_index, column_index) in self.marked
                prefix = "✅" if marked else "⬜"
                label = square if marked or reveal_unmarked else "???"
                slot = self.slot_for_position(row_index, column_index)
                rendered.append(f"{prefix} #{slot}: {label}")
            rows.append(" | ".join(rendered))
        return "\n".join(rows)

    def render_discord_grid(self) -> dict:
        fields = []
        for row_index, row in enumerate(self.squares):
            for column_index, square in enumerate(row):
                marked = (row_index, column_index) in self.marked
                slot = self.slot_for_position(row_index, column_index)
                status = "✅" if marked else "⬜"
                fields.append({"name": f"{status} Slot #{slot}", "value": f"Find: {square}", "inline": True})
        return {"fields": fields}


@dataclass(slots=True)
class BingoGame:
    game_id: str
    title: str
    song_pool: list[str]
    size: int = 5
    active: bool = True
    cards: dict[str, BingoCard] = field(default_factory=dict)
    played_tracks: list[str] = field(default_factory=list)
    winners: set[str] = field(default_factory=set)
    config: BingoConfig | None = None
    win_log: list[BingoWin] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.config is None:
            self.config = BingoConfig(size=self.size)
        self.size = self.config.size

    def create_card(self, listener_id: str, seed: int | str | None = None) -> BingoCard:
        if listener_id in self.cards and self.config.max_cards_per_listener <= 1:
            return self.cards[listener_id]
        needed = self.config.required_song_count()
        pool = list(dict.fromkeys(self.song_pool))
        if len(pool) < needed:
            raise ValueError(f"Need at least {needed} unique songs to create a bingo card")
        card_seed = seed
        if card_seed is None and self.config.deterministic_cards:
            card_seed = f"{self.config.seed}:{self.game_id}:{listener_id}:{len(self.cards)}"
        rng = random.Random(card_seed)
        picks = rng.sample(pool, needed)
        squares: list[list[str]] = []
        cursor = 0
        center = self.config.size // 2
        for row in range(self.config.size):
            line: list[str] = []
            for column in range(self.config.size):
                if self.config.free_space and self.config.size % 2 == 1 and row == center and column == center:
                    line.append(self.config.free_space_label)
                else:
                    line.append(picks[cursor])
                    cursor += 1
            squares.append(line)
        card = BingoCard(f"{self.game_id}:{listener_id}:{len(self.cards) + 1}", listener_id, self.config.size, squares, free_space_label=self.config.free_space_label)
        if self.config.allow_late_join:
            for track in self.played_tracks:
                card.mark_track(track, exact=self.config.require_exact_title_match)
        self.cards[listener_id] = card
        return card

    def redraw_card(self, listener_id: str, seed: int | str | None = None) -> BingoCard:
        self.cards.pop(listener_id, None)
        return self.create_card(listener_id, seed=seed)

    def mark_played(self, track: str) -> list[BingoCard]:
        self.played_tracks.append(track)
        winners: list[BingoCard] = []
        patterns = self.config.patterns()
        for card in self.cards.values():
            card.mark_track(track, exact=self.config.require_exact_title_match)
            wins = card.winning_patterns(patterns)
            if card.listener_id not in self.winners and wins:
                self.winners.add(card.listener_id)
                self.win_log.append(BingoWin(self.game_id, card.listener_id, card.card_id, [pattern.name for pattern in wins], track))
                winners.append(card)
        return winners

    def verify_slot(self, listener_id: str, slot: int) -> bool:
        card = self.cards[listener_id]
        return card.verify_slot(slot, self.played_tracks, exact=self.config.require_exact_title_match)

    def card_status(self, listener_id: str) -> dict:
        card = self.cards[listener_id]
        return {
            "card_id": card.card_id,
            "completion_percent": card.completion_percent(),
            "near_bingos": [(pattern.name, missing) for pattern, missing in card.near_bingos(self.config.patterns())],
            "has_bingo": card.has_bingo(self.config.patterns()),
        }

    def leaderboard(self) -> list[tuple[str, int]]:
        scored = [(card.listener_id, (self.size * self.size) - len(card.unmarked_squares())) for card in self.cards.values()]
        return sorted(scored, key=lambda item: item[1], reverse=True)

    def export_cards(self) -> dict[str, dict]:
        return {listener_id: card.to_dict() for listener_id, card in self.cards.items()}

    def import_cards(self, cards: dict[str, dict]) -> None:
        self.cards = {listener_id: BingoCard.from_dict(card) for listener_id, card in cards.items()}


class CommunityManager:
    """In-memory community system that can be backed by the existing database later."""

    def __init__(self) -> None:
        self.profiles: dict[str, ListenerProfile] = {}
        self.votes: list[SongVote] = []
        self.dedications: list[Dedication] = []
        self.polls: dict[str, CommunityPoll] = {}
        self.bingo_games: dict[str, BingoGame] = {}
        self.song_history: list[str] = []

    def profile(self, listener_id: str, display_name: str | None = None) -> ListenerProfile:
        if listener_id not in self.profiles:
            self.profiles[listener_id] = ListenerProfile(listener_id, display_name or listener_id)
        return self.profiles[listener_id]

    def add_request(self, listener_id: str, display_name: str, track: str) -> None:
        profile = self.profile(listener_id, display_name)
        profile.requests += 1
        profile.award_xp(5, "Requester")

    def vote_song(self, listener_id: str, display_name: str, track: str, weight: int = 1) -> None:
        profile = self.profile(listener_id, display_name)
        profile.votes += 1
        profile.award_xp(2, "Voter")
        self.votes.append(SongVote(track, listener_id, max(1, weight)))

    def vote_totals(self) -> Counter[str]:
        totals: Counter[str] = Counter()
        for vote in self.votes:
            totals[vote.track] += vote.weight
        return totals

    def add_dedication(self, listener_id: str, display_name: str, track: str, message: str) -> Dedication:
        self.profile(listener_id, display_name).award_xp(3, "Dedicator")
        dedication = Dedication(track, listener_id, message)
        self.dedications.append(dedication)
        return dedication

    def create_poll(self, poll_id: str, question: str, options: list[str]) -> CommunityPoll:
        poll = CommunityPoll(question, options)
        self.polls[poll_id] = poll
        return poll

    def start_bingo(self, game_id: str, title: str, songs: Iterable[str], size: int = 5, config: BingoConfig | None = None) -> BingoGame:
        bingo_config = config or BingoConfig(size=size)
        game = BingoGame(game_id, title, [display_song_name(song) for song in songs], size=bingo_config.size, config=bingo_config)
        self.bingo_games[game_id] = game
        return game

    def verify_bingo_slot(self, game_id: str, listener_id: str, slot: int) -> bool:
        return self.bingo_games[game_id].verify_slot(listener_id, slot)

    def bingo_card(self, game_id: str, listener_id: str, display_name: str) -> BingoCard:
        profile = self.profile(listener_id, display_name)
        game = self.bingo_games[game_id]
        profile.award_xp(game.config.xp_for_card, "Bingo Player")
        return game.cards.get(listener_id) or game.create_card(listener_id)

    def record_play(self, track: str) -> list[tuple[BingoGame, BingoCard]]:
        display = display_song_name(track)
        self.song_history.append(display)
        winners: list[tuple[BingoGame, BingoCard]] = []
        for game in self.bingo_games.values():
            if not game.active:
                continue
            before = {listener_id: len(card.marked) for listener_id, card in game.cards.items()}
            for card in game.mark_played(display):
                profile = self.profile(card.listener_id)
                profile.bingo_wins += 1
                profile.award_xp(game.config.xp_for_win, "Bingo Winner")
                winners.append((game, card))
            for listener_id, card in game.cards.items():
                gained = len(card.marked) - before.get(listener_id, len(card.marked))
                if gained > 0:
                    self.profile(listener_id).award_xp(gained * game.config.xp_for_square, "Bingo Square")
        return winners

    def listener_of_the_day(self, today: date | None = None) -> ListenerProfile | None:
        if not self.profiles:
            return None
        return max(self.profiles.values(), key=lambda profile: (profile.xp, profile.reputation, profile.requests))

    def hall_of_fame(self, limit: int = 10) -> list[ListenerProfile]:
        return sorted(self.profiles.values(), key=lambda profile: (profile.xp, profile.reputation, profile.bingo_wins), reverse=True)[:limit]

    def now_playing_embed(self, track: str) -> dict:
        return {"title": "Now Playing", "description": display_song_name(track), "color": 0x22C55E}

    def queue_embed(self, queue: Iterable[str]) -> dict:
        songs = [display_song_name(song) for song in queue]
        return {"title": "Upcoming Songs", "description": "\n".join(songs) or "Queue is empty", "color": 0x2563EB}

    def history_embed(self, limit: int = 10) -> dict:
        songs = list(reversed(self.song_history[-limit:]))
        return {"title": "Recently Played", "description": "\n".join(songs) or "No songs played yet", "color": 0xA855F7}

    def bingo_embed(self, game_id: str, listener_id: str) -> dict:
        game = self.bingo_games[game_id]
        card = game.cards[listener_id]
        status = game.card_status(listener_id)
        near = status["near_bingos"]
        near_text = "\n".join(f"{name}: needs {', '.join(missing)}" for name, missing in near[:5]) or "No near-bingos yet"
        return {
            "title": f"{game.title} — {listener_id}",
            "description": "Use `!bingo verify <slot>` when you hear or notice that song.",
            "color": 0xF59E0B,
            "fields": card.render_discord_grid()["fields"] + [
                {"name": "Completion", "value": f"{status['completion_percent']}%", "inline": True},
                {"name": "Near Bingos", "value": near_text, "inline": False},
            ],
        }


def build_bingo_patterns(size: int, enabled: Iterable[str], prizes: dict[str, str] | None = None) -> list[BingoPattern]:
    prizes = prizes or {}
    enabled_set = set(enabled)
    patterns: list[BingoPattern] = []
    if "line" in enabled_set:
        for index in range(size):
            patterns.append(BingoPattern(f"Row {index + 1}", frozenset((index, column) for column in range(size)), prizes.get("line", "")))
            patterns.append(BingoPattern(f"Column {index + 1}", frozenset((row, index) for row in range(size)), prizes.get("line", "")))
        patterns.append(BingoPattern("Diagonal Down", frozenset((index, index) for index in range(size)), prizes.get("line", "")))
        patterns.append(BingoPattern("Diagonal Up", frozenset((index, size - 1 - index) for index in range(size)), prizes.get("line", "")))
    if "four_corners" in enabled_set:
        patterns.append(BingoPattern("Four Corners", frozenset({(0, 0), (0, size - 1), (size - 1, 0), (size - 1, size - 1)}), prizes.get("four_corners", "")))
    if "blackout" in enabled_set:
        patterns.append(BingoPattern("Blackout", frozenset((row, column) for row in range(size) for column in range(size)), prizes.get("blackout", "")))
    if "x" in enabled_set:
        patterns.append(BingoPattern("X", frozenset({*((index, index) for index in range(size)), *((index, size - 1 - index) for index in range(size))}), prizes.get("x", "")))
    if "plus" in enabled_set:
        center = size // 2
        patterns.append(BingoPattern("Plus", frozenset({*((center, column) for column in range(size)), *((row, center) for row in range(size))}), prizes.get("plus", "")))
    if "postage_stamp" in enabled_set and size >= 2:
        stamps = {
            "Top Left Stamp": {(0, 0), (0, 1), (1, 0), (1, 1)},
            "Top Right Stamp": {(0, size - 2), (0, size - 1), (1, size - 2), (1, size - 1)},
            "Bottom Left Stamp": {(size - 2, 0), (size - 2, 1), (size - 1, 0), (size - 1, 1)},
            "Bottom Right Stamp": {(size - 2, size - 2), (size - 2, size - 1), (size - 1, size - 2), (size - 1, size - 1)},
        }
        for name, positions in stamps.items():
            patterns.append(BingoPattern(name, frozenset(positions), prizes.get("postage_stamp", "")))
    return patterns


def display_song_name(track: str) -> str:
    return Path(track).stem if any(separator in track for separator in ("/", "\\")) else Path(track).stem


def normalize_song_key(track: str) -> str:
    return display_song_name(track).casefold().strip()
