
import os
import asyncio
import math
import struct
from pathlib import Path

import nextcord
from nextcord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TOKEN = os.getenv("BOT_TOKEN")

AUDIO_FILE = (
    Path(__file__).parent
    / "Top of the hour.mp3-enhanced-v2.mp3"
)

intents = nextcord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
scheduler = AsyncIOScheduler()
play_lock = asyncio.Lock()


class TestTone(nextcord.AudioSource):
    def __init__(self, duration=5, frequency=440):
        self.frame_number = 0
        self.total_frames = duration * 50
        self.frequency = frequency

    def read(self):
        if self.frame_number >= self.total_frames:
            return b""

        samples = bytearray()

        for i in range(960):
            position = self.frame_number * 960 + i

            value = int(
                14000 * math.sin(
                    2 * math.pi * self.frequency
                    * position / 48000
                )
            )

            samples.extend(struct.pack("<hh", value, value))

        self.frame_number += 1
        return bytes(samples)

    def is_opus(self):
        return False


def find_channel(guild):
    channels = []

    for channel in guild.voice_channels:
        count = sum(
            1 for member in channel.members
            if not member.bot
        )

        if count > 0:
            channels.append((count, channel))

    if not channels:
        return None

    return max(channels, key=lambda item: item[0])[1]


async def play_audio(channel, tone=False):
    async with play_lock:
        voice = None
        finished = asyncio.Event()
        loop = asyncio.get_running_loop()

        try:
            print(f"Connecting to {channel.name}...")

            voice = await channel.connect(
                timeout=20,
                reconnect=True
            )

            print("Connected using Nextcord.")
            print("Nextcord version:", nextcord.__version__)
            print("Encryption mode:", getattr(voice, "mode", None))

            if tone:
                source = TestTone(duration=5)
                print("Playing 5-second test tone...")
            else:
                if not AUDIO_FILE.is_file():
                    print("Missing audio file:", AUDIO_FILE)
                    return

                source = nextcord.FFmpegPCMAudio(
                    str(AUDIO_FILE),
                    executable="ffmpeg",
                    options="-vn"
                )

                print("Playing MP3:", AUDIO_FILE.name)

            def playback_finished(error):
                print("Playback callback:", repr(error))
                loop.call_soon_threadsafe(finished.set)

            voice.play(source, after=playback_finished)

            print("Playback started.")

            await asyncio.wait_for(
                finished.wait(),
                timeout=45
            )

            print("Playback finished.")

        except Exception as error:
            print("ERROR:", repr(error))

        finally:
            if voice:
                if voice.is_playing():
                    voice.stop()

                await voice.disconnect(force=True)
                print("Disconnected.")


async def hourly_job():
    for guild in bot.guilds:
        channel = find_channel(guild)

        if channel:
            await play_audio(channel)


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


def target_channel(ctx):
    if ctx.author.voice:
        return ctx.author.voice.channel

    return find_channel(ctx.guild)


@bot.command()
async def test(ctx):
    channel = target_channel(ctx)

    if not channel:
        await ctx.send("Join a voice channel first.")
        return

    await ctx.send("Testing MP3 with Nextcord...")
    await play_audio(channel)


@bot.command()
async def testtone(ctx):
    channel = target_channel(ctx)

    if not channel:
        await ctx.send("Join a voice channel first.")
        return

    await ctx.send("Testing Nextcord audio for 5 seconds...")
    await play_audio(channel, tone=True)


@bot.command()
async def where(ctx):
    channel = find_channel(ctx.guild)

    if channel:
        await ctx.send(f"I would play in {channel.name}.")
    else:
        await ctx.send("Nobody is in voice chat.")


if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN environment variable is missing."
    )

bot.run(TOKEN)
