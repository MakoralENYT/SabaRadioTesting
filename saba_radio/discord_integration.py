"""Discord bot and webhook adapters for requests, queue commands, and now-playing posts."""
from __future__ import annotations

import importlib.util
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DiscordWebhookClient:
    """Minimal dependency-free Discord webhook publisher."""

    webhook_url: str = ""
    username: str = "Saba Radio"

    def enabled(self) -> bool:
        return bool(self.webhook_url.strip())

    def send_now_playing(self, title: str, artist: str = "") -> bool:
        if not self.enabled():
            return False
        description = f"{artist} — {title}" if artist else title
        payload = {
            "username": self.username,
            "embeds": [
                {
                    "title": "Now Playing",
                    "description": description,
                    "color": 0x2563EB,
                }
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "SabaRadio/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return 200 <= response.status < 300


class DiscordRadioBot:
    def __init__(self, queue, now_playing_provider, token: str = '', community=None, library_provider=None) -> None:
        self.queue=queue; self.now_playing_provider=now_playing_provider; self.token=token; self.community=community; self.library_provider=library_provider
    def create_bot(self):
        if not importlib.util.find_spec('discord'): raise RuntimeError('Install discord.py for Discord integration.')
        import discord
        from discord.ext import commands
        intents=discord.Intents.default(); intents.message_content=True
        bot=commands.Bot(command_prefix='!', intents=intents)
        @bot.command()
        async def now(ctx): await ctx.send(embed=discord.Embed(title='Now Playing', description=str(self.now_playing_provider())))
        @bot.command()
        async def request(ctx, *, song: str):
            requested = song
            matches = self.queue.search(list(self.library_provider() if self.library_provider else []), song)
            if matches:
                requested = matches[0]
            self.queue.add(requested, priority=10, requester=str(ctx.author))
            if self.community: self.community.add_request(str(ctx.author.id), str(ctx.author), requested)
            if matches:
                await ctx.send(f'Queued request: {Path(requested).name}')
            else:
                await ctx.send(f'Queued request: {song}')
        @bot.command()
        async def queue(ctx): await ctx.send('\n'.join(self.queue.upcoming(10)) or 'Queue is empty')
        @bot.command()
        async def history(ctx):
            if not self.community: await ctx.send('Community features are not enabled'); return
            await ctx.send(embed=build_discord_embed(discord, self.community.history_embed()))
        @bot.command()
        async def upcoming(ctx):
            if not self.community: await ctx.send('Community features are not enabled'); return
            await ctx.send(embed=build_discord_embed(discord, self.community.queue_embed(self.queue.upcoming(10))))
        @bot.command()
        async def vote(ctx, *, song: str):
            if not self.community: await ctx.send('Community features are not enabled'); return
            self.community.vote_song(str(ctx.author.id), str(ctx.author), song); await ctx.send(f'Vote counted for {song}')
        @bot.command()
        async def dedicate(ctx, song: str, *, message: str):
            if not self.community: await ctx.send('Community features are not enabled'); return
            self.community.add_dedication(str(ctx.author.id), str(ctx.author), song, message); await ctx.send(f'Dedication saved for {song}')
        @bot.group()
        async def bingo(ctx):
            if ctx.invoked_subcommand is None: await ctx.send('Use !bingo card, !bingo board, !bingo status, or !bingo verify <slot>')
        @bingo.command(name='card')
        async def bingo_card(ctx, game_id: str = 'main'):
            if not self.community or game_id not in self.community.bingo_games: await ctx.send('No active bingo game'); return
            card=self.community.bingo_card(game_id, str(ctx.author.id), str(ctx.author)); await ctx.send(embed=build_discord_embed(discord, self.community.bingo_embed(game_id, str(ctx.author.id))))
        @bingo.command(name='board')
        async def bingo_board(ctx, game_id: str = 'main'):
            if not self.community or game_id not in self.community.bingo_games: await ctx.send('No active bingo game'); return
            rows=[f'{listener}: {score}' for listener, score in self.community.bingo_games[game_id].leaderboard()[:10]]; await ctx.send('\n'.join(rows) or 'No cards yet')
        @bingo.command(name='status')
        async def bingo_status(ctx, game_id: str = 'main'):
            if not self.community or game_id not in self.community.bingo_games: await ctx.send('No active bingo game'); return
            game=self.community.bingo_games[game_id]
            if str(ctx.author.id) not in game.cards: await ctx.send('You do not have a card yet. Use !bingo card'); return
            status=game.card_status(str(ctx.author.id)); await ctx.send(f"Completion: {status['completion_percent']}% | Bingo: {status['has_bingo']}")
        @bingo.command(name='verify')
        async def bingo_verify(ctx, slot: int, game_id: str = 'main'):
            if not self.community or game_id not in self.community.bingo_games: await ctx.send('No active bingo game'); return
            game=self.community.bingo_games[game_id]
            if str(ctx.author.id) not in game.cards: await ctx.send('You do not have a card yet. Use !bingo card'); return
            try:
                verified=self.community.verify_bingo_slot(game_id, str(ctx.author.id), slot)
            except ValueError as exc:
                await ctx.send(str(exc)); return
            await ctx.send(('Verified' if verified else 'Not verified yet') + f' slot #{slot}')
        return bot
    def run(self) -> None:
        if not self.token: raise RuntimeError('Discord token is not configured.')
        self.create_bot().run(self.token)


def build_discord_embed(discord_module, payload: dict):
    embed = discord_module.Embed(
        title=payload.get("title"),
        description=payload.get("description"),
        color=payload.get("color"),
    )
    for field in payload.get("fields", []):
        embed.add_field(
            name=field.get("name", " "),
            value=field.get("value", " "),
            inline=field.get("inline", False),
        )
    return embed
