# Discord Bot

- **Purpose**: A small Discord bot with two primary purposes: a music player and a chat assistant.

## Music Player
- **/play**: Play audio from YouTube (supports search terms or direct URLs). Adds to the guild queue and shows a playback view with controls.
- **/join**: Joins the voice channel you're in.
- **/leave**: Disconnects the bot from the voice channel.
- **/queue**: Shows the current queue and now-playing information.
- **/skip**: Skips the current song.
- **/stop**: Stops playback, clears the queue, and disconnects.
- **/clear**: Clears the queue.
- Button controls: A UI view with Skip, Pause/Resume, and Stop buttons appears alongside some music responses.

## Chat Assistant
- The bot listens for mentions in text channels and forwards the message (plus recent channel context) to a local LLM HTTP API.
- The LLM endpoint is expected at `http://localhost:11434/api/generate` by default.
- The chat cog returns the model reply as a threaded reply in-channel.

## Files of Interest
- `main.py` - Bot bootstrap, event handlers, and global commands such as `/ping`, `/hello`, `/pfp`, and `/credits`.
- `cogs/music.py` - Music cog: queue management, yt-dlp integration, and FFmpeg playback.
- `cogs/chat.py` - Chat cog: collects context, calls the local LLM API, and replies when mentioned.
- `environment.yaml` - Conda environment specification (replaces requirements.txt).

## Setup & Run
1. Create the Conda environment from `environment.yaml` (from the repo root):

```bash
conda env create -f environment.yaml
```

2. Activate the environment (the environment name in this repo is `discord-bot`):

```bash
conda activate discord-bot
```

3. Create a `.env` file (do NOT commit this). Required variables:
- `DISCORD_TOKEN` - Your bot token
- `DISCORD_GUILD` - Guild ID where you want to register commands

Example `.env` (do not paste real tokens into source control):
```
DISCORD_TOKEN=YOUR_TOKEN_HERE
DISCORD_GUILD=YOUR_GUILD_ID
```

4. Run the bot:

```bash
python main.py
```
