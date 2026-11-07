
import os
import asyncio
from pathlib import Path

import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TOKEN = os.getenv("BOT_TOKEN")
AUDIO_FILE = Path(__file__).parent / "Top of the hour.mp3-enhanced-v2.mp3"

intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
scheduler = AsyncIOScheduler()
play_lock = asyncio.Lock()


def active_voice_channel(guild):
    choices = []

    for channel in guild.voice_channels:
        humans = [member for member in channel.members if not member.bot]

        if humans:
            choices.append((len(humans), channel))

    return max(choices, key=lambda x: x[0])[1] if choices else None


async def play_in_channel(channel):
    async with play_lock:
        voice = None
        finished = asyncio.Event()
        loop = asyncio.get_running_loop()

        try:
            if not AUDIO_FILE.is_file():
                print(f"ERROR: Audio file missing: {AUDIO_FILE}")
                return

            print(f"Audio file: {AUDIO_FILE.name}")
            print(f"Connecting to {channel.name}...")

            voice = await channel.connect(timeout=20, reconnect=True)
            print("Voice connected.")

            # Use PCM audio instead of FFmpeg Opus output
            source = discord.FFmpegPCMAudio(
                str(AUDIO_FILE),
                executable="ffmpeg",
                options="-vn"
            )

            def after_play(error):
                print(f"Player callback: {error!r}")
                loop.call_soon_threadsafe(finished.set)

            voice.play(source, after=after_play)
            print("Playback started.")

            await asyncio.wait_for(finished.wait(), timeout=45)
            print("Playback ended.")

        except asyncio.TimeoutError:
            print("ERROR: Playback timed out.")

        except Exception as exc:
            print(f"VOICE/PLAYBACK ERROR: {exc!r}")

        finally:
            if voice:
                if voice.is_playing():
                    voice.stop()

                await voice.disconnect(force=True)
                print("Disconnected.")


async def hourly_job():
    for guild in bot.guilds:
        channel = active_voice_channel(guild)

        if channel:
            await play_in_channel(channel)
        else:
            print(f"No people in voice channels in {guild.name}")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    if not scheduler.running:
        scheduler.add_job(
            hourly_job,
            "cron",
            minute=0,
            second=0,
            id="hourly_sound",
            replace_existing=True,
            max_instances=1,
            coalesce=True
        )

        scheduler.start()

    print("Hourly scheduler active.")


@bot.command()
async def test(ctx):
    await ctx.send("Testing sound...")

    if ctx.author.voice and ctx.author.voice.channel:
        channel = ctx.author.voice.channel
    else:
        channel = active_voice_channel(ctx.guild)

    if not channel:
        await ctx.send("Nobody is in a voice channel.")
        return

    await play_in_channel(channel)


@bot.command()
async def where(ctx):
    channel = active_voice_channel(ctx.guild)

    if channel:
        await ctx.send(f"I would play in **{channel.name}**.")
    else:
        await ctx.send("No voice channel currently has a human member.")


if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing.")

bot.run(TOKEN)
