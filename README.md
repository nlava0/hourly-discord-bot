# Hourly Discord Sound Bot

Includes your exact MP3 and bot source.

- At minute 00 each hour, plays in the busiest voice channel with human members.
- `!test` plays immediately.
- `!where` reports the channel it would select.

## Deploy to Railway
1. Upload these project files to a GitHub repository (keep the MP3 beside `bot.py`).
2. Create a Railway service from that repository.
3. Set environment variable `BOT_TOKEN` to your Discord bot token.
4. For Railway Railpack, set `RAILPACK_DEPLOY_APT_PACKAGES=ffmpeg`.
5. Discord Developer Portal: enable **Message Content Intent**. Invite bot with View Channels, Connect, Speak permissions.
6. Deploy; run `!where` and `!test` in Discord while someone is in voice.

Do not share or commit your bot token.
