
import os
import asyncio
import math
import struct
from pathlib import Path

import nextcord
from nextcord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler


# =====================================
# SETTINGS
# =====================================

TOKEN = os.getenv("BOT_TOKEN")

FOLDER = Path(__file__).parent

HOURLY_AUDIO = (
    FOLDER / "Top of the hour.mp3-enhanced-v2.mp3"
)

NARUTO_AUDIO = (
    FOLDER / "Nartuto Filler.mp3"
)

NARUTO_PEOPLE_REQUIRED = 5


# =====================================
# BOT SETUP
# =====================================

intents = nextcord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

scheduler = AsyncIOScheduler()

play_lock = asyncio.Lock()

# Tracks which channels have already
# triggered the Naruto music.
naruto_triggered = set()

# Tracks background playback tasks.
background_tasks = set()


# =====================================
# TEST TONE
# =====================================

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
                    2 * math.pi
                    * self.frequency
                    * position / 48000
                )
            )

            samples.extend(
                struct.pack("<hh", value, value)
            )

        self.frame_number += 1

        return bytes(samples)

    def is_opus(self):
        return False


# =====================================
# VOICE CHANNEL HELPERS
# =====================================

def human_count(channel):

    return sum(
        1 for member in channel.members
        if not member.bot
    )


def find_channel(guild):

    channels = []

    for channel in guild.voice_channels:

        count = human_count(channel)

        if count > 0:
            channels.append((count, channel))

    if not channels:
        return None

    return max(
        channels,
        key=lambda item: item[0]
    )[1]


def target_channel(ctx):

    if ctx.author.voice:
        return ctx.author.voice.channel

    return find_channel(ctx.guild)


def start_background_task(coroutine):

    task = asyncio.create_task(coroutine)

    background_tasks.add(task)

    task.add_done_callback(
        background_tasks.discard
    )


# =====================================
# AUDIO PLAYER
# =====================================

async def play_audio(channel, audio_file=None, tone=False):

    async with play_lock:

        voice = None
        finished = asyncio.Event()

        loop = asyncio.get_running_loop()

        try:

            print(
                f"Connecting to {channel.name}..."
            )

            voice = channel.guild.voice_client

            if voice and voice.channel != channel:

                await voice.disconnect(force=True)
                voice = None

            if not voice or not voice.is_connected():

                voice = await channel.connect(
                    timeout=20,
                    reconnect=True
                )

            print("Connected using Nextcord.")

            if tone:

                source = TestTone(duration=5)

                timeout = 30

                print("Playing test tone...")

            else:

                if not audio_file:
                    print("No audio file selected.")
                    return

                if not audio_file.is_file():

                    print(
                        "Missing audio file:",
                        audio_file
                    )
                    return

                source = nextcord.FFmpegPCMAudio(
                    str(audio_file),
                    executable="ffmpeg",
                    options="-vn"
                )

                timeout = 180

                print(
                    "Playing:",
                    audio_file.name
                )

            def playback_finished(error):

                if error:
                    print(
                        "Playback error:",
                        repr(error)
                    )

                loop.call_soon_threadsafe(
                    finished.set
                )

            voice.play(
                source,
                after=playback_finished
            )

            print("Playback started.")

            await asyncio.wait_for(
                finished.wait(),
                timeout=timeout
            )

            print("Playback finished.")

        except Exception as error:

            print(
                "Audio error:",
                repr(error)
            )

        finally:

            if voice:

                try:

                    if voice.is_playing():
                        voice.stop()

                    await voice.disconnect(
                        force=True
                    )

                    print("Disconnected.")

                except Exception as error:

                    print(
                        "Disconnect error:",
                        repr(error)
                    )


# =====================================
# NARUTO FOUR-PERSON TRIGGER
# =====================================

async def play_naruto(channel):

    # The channel may have changed while
    # waiting for another sound to finish.

    async with play_lock:

        if human_count(channel) < NARUTO_PEOPLE_REQUIRED:

            print(
                "Naruto playback skipped: "
                "fewer than four people."
            )
            return

    print(
        f"Naruto trigger activated in {channel.name}!"
    )

    await play_audio(
        channel,
        audio_file=NARUTO_AUDIO
    )


def check_naruto_channel(channel):

    if not isinstance(
        channel,
        nextcord.VoiceChannel
    ):
        return

    count = human_count(channel)

    channel_id = channel.id

    print(
        f"{channel.name}: {count} people"
    )

    if count < NARUTO_PEOPLE_REQUIRED:

        if channel_id in naruto_triggered:

            naruto_triggered.discard(
                channel_id
            )

            print(
                f"Naruto trigger reset in "
                f"{channel.name}"
            )

        return

    if channel_id in naruto_triggered:

        print(
            "Naruto already triggered "
            "for this group."
        )
        return

    naruto_triggered.add(channel_id)

    print(
        "Four-person threshold reached!"
    )

    start_background_task(
        play_naruto(channel)
    )


# =====================================
# VOICE STATE DETECTION
# =====================================

@bot.event
async def on_voice_state_update(
    member,
    before,
    after
):

    if member.bot:
        return

    # Ignore mute/deafen changes.
    if before.channel == after.channel:
        return

    # Check the channel the member left.
    if before.channel:

        check_naruto_channel(
            before.channel
        )

    # Check the channel the member joined.
    if after.channel:

        check_naruto_channel(
            after.channel
        )


# =====================================
# HOURLY KROGER ANNOUNCEMENT
# =====================================

async def hourly_job():

    print(
        "Top of the hour! Checking channels..."
    )

    for guild in bot.guilds:

        channel = find_channel(guild)

        if channel:

            await play_audio(
                channel,
                audio_file=HOURLY_AUDIO
            )


# =====================================
# BOT READY
# =====================================

@bot.event
async def on_ready():

    print(
        f"Logged in as {bot.user}"
    )

    # Prevent an immediate Naruto trigger
    # when the bot first starts.
    if not scheduler.running:

        for guild in bot.guilds:

            for channel in guild.voice_channels:

                if human_count(channel) >= NARUTO_PEOPLE_REQUIRED:

                    naruto_triggered.add(
                        channel.id
                    )

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

    print("Hourly announcement active.")
    print("Naruto four-person trigger active.")


# =====================================
# COMMAND: !test
# =====================================

@bot.command()
async def test(ctx):

    channel = target_channel(ctx)

    if not channel:

        await ctx.send(
            "Join a voice channel first."
        )
        return

    await ctx.send(
        "It's the top of the hour!"
    )

    await play_audio(
        channel,
        audio_file=HOURLY_AUDIO
    )


# =====================================
# COMMAND: !testnaruto
# =====================================

@bot.command()
async def testnaruto(ctx):

    channel = target_channel(ctx)

    if not channel:

        await ctx.send(
            "Join a voice channel first."
        )
        return

    await ctx.send(
        "Testing Naruto filler music!"
    )

    await play_audio(
        channel,
        audio_file=NARUTO_AUDIO
    )


# =====================================
# COMMAND: !testtone
# =====================================

@bot.command()
async def testtone(ctx):

    channel = target_channel(ctx)

    if not channel:

        await ctx.send(
            "Join a voice channel first."
        )
        return

    await ctx.send(
        "Wake up time!"
    )

    await play_audio(
        channel,
        tone=True
    )


# =====================================
# COMMAND: !where
# =====================================

@bot.command()
async def where(ctx):

    channel = find_channel(ctx.guild)

    if channel:

        await ctx.send(
            f"I would play in {channel.name}."
        )

    else:

        await ctx.send(
            "Nobody is in voice chat."
        )


# =====================================
# COMMAND: !narutostatus
# =====================================

@bot.command()
async def narutostatus(ctx):

    channel = target_channel(ctx)

    if not channel:

        await ctx.send(
            "Join a voice channel first."
        )
        return

    count = human_count(channel)

    triggered = (
        channel.id in naruto_triggered
    )

    if triggered:

        status = (
            "Already played. Waiting for "
            "the count to drop below four."
        )

    else:

        status = (
            "Ready to trigger at four people."
        )

    await ctx.send(
        f"Channel: {channel.name}\n"
        f"People: {count}\n"
        f"Naruto: {status}"
    )


# =====================================
# START BOT
# =====================================

if not TOKEN:

    raise RuntimeError(
        "BOT_TOKEN environment variable "
        "is missing."
    )

bot.run(TOKEN)
