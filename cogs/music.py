# necessary imports
import discord
from discord import app_commands
from discord import PCMVolumeTransformer
from discord.ext import commands
from dotenv import load_dotenv
import os
import yt_dlp
import asyncio
import logging

# options
intents = discord.Intents.all()

# music options
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -filter:a "volume=0.3"'
}

YDL_OPTIONS = {"format": "bestaudio/best",
               "noplaylist": True,
               "cookiefile": "cookies.txt",
               "default_search": "ytsearch",
               "nocheckcertificate": True,
               "ignoreerrors": True,
               "quiet": True,}

# create Music class
class Music(commands.Cog):

    # define init method
    def __init__(self, client):
        self.client = client
        self.queues = {}  # stores queues per guild
        self.text_channels = {}  # stores text channels per guild

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        return self.queues[guild_id]

    async def play_next(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        queue = self.get_queue(guild_id)

        if queue:
            url, title = queue.pop(0)  # Fixed here, should be self.get_queue(guild_id).pop(0)
            voice_client = interaction.guild.voice_client

            try:
                source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTIONS)
                source = PCMVolumeTransformer(source, volume=0.3)

                def after_play(error):
                    if error:
                        print(f"Player error: {error}")
                    self.client.loop.create_task(self.play_next(interaction))

                voice_client.play(source, after=after_play)
                await self.text_channels[guild_id].send(f"Now Playing: **{title}**")
            except Exception as e:
                await self.text_channels[guild_id].send(f"Error playing song: {e}")
                await self.play_next(interaction)

        elif interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            await self.text_channels[guild_id].send("Queue is empty. Disconnected from voice channel.")

    # play command
    @app_commands.command(name="play", description="Play audio from YouTube")
    @app_commands.describe(query="Song to name or URL")
    async def play(self, interaction: discord.Interaction, *, query: str):
        await interaction.response.defer()  # Defer FIRST THING
        self.text_channels[interaction.guild.id] = interaction.channel

        if not interaction.user.voice:
            return await interaction.followup.send("You need to be in a voice channel to play music!")

        try:
            # Ensure voice connection
            voice_client = interaction.guild.voice_client or await interaction.user.voice.channel.connect()

            if voice_client.channel != interaction.user.voice.channel:
                await voice_client.move_to(interaction.user.voice.channel)

            # Setup yt-dlp options
            ydl_opts = YDL_OPTIONS.copy()
            ydl_opts['quiet'] = True

            # Attempt to extract video info using yt-dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)

                # Log the info for debugging purposes
                logging.debug(f"Extracted info: {info}")

                # Check if the extracted info is a playlist or single video
                if 'entries' in info:
                    entry = info['entries'][0]  # Get the first video from the playlist
                else:
                    entry = info  # It's a single video

                # Now extract the URL and title correctly
                song_url = entry.get('url')  # Get the URL of the video
                song_title = entry.get('title', 'Unknown Title')  # Get the title, fallback to 'Unknown Title' if not found

                if not song_url:
                    raise ValueError(f"Failed to retrieve a valid URL for the query: {query}")

                # Add the song to the queue
                self.get_queue(interaction.guild.id).append((song_url, song_title))

                # Inform the user about the added song
                await interaction.followup.send(f"Added **{song_title}** to queue!")

                # If nothing is playing, start playing the next song
                if not voice_client.is_playing():
                    await self.play_next(interaction)

        except yt_dlp.utils.ExtractorError as e:
            # Handle yt-dlp specific errors (e.g., extractor issues)
            await interaction.followup.send(f"Error extracting info from the provided query: {str(e)}")
        except ValueError as e:
            # Handle missing URL or other value-related issues
            await interaction.followup.send(f"Error: {str(e)}")
        except Exception as e:
            # General
            await interaction.followup.send(f"An unexpected error occurred: {str(e)}")
            logging.error(f"Unexpected error: {str(e)}")

    # join voice channel
    @app_commands.command(name="join", description="Joins a voice channel")
    async def join(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Defer immediately

        if interaction.user.voice:
            try:
                channel = interaction.user.voice.channel
                await channel.connect(timeout=10.0)  # Increased timeout
                self.voice = interaction.guild.voice_client
                await interaction.followup.send(f"Joined {channel.name}!")
            except asyncio.TimeoutError:
                await interaction.followup.send("Connection timed out. Please try again.")
            except Exception as e:
                await interaction.followup.send(f"Failed to join: {str(e)}")
        else:
            await interaction.followup.send("You must be in a voice channel!")

    # view queue command
    @app_commands.command(name="queue", description="Shows current queue")
    async def queue(self, interaction: discord.Interaction):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not currently in a voice channel! Please use `/join` to join a voice channel.")
        else:
            queue = self.get_queue(interaction.guild.id)
            if len(queue) == 0:
                queue_str = "No songs in queue!"
            else:
                queue_str = "\n".join([f"*{i}*: **{info[1]}**" for i, info in enumerate(queue)])

            emb = discord.Embed(title="**Next Up**", color=discord.Color.purple(), description=queue_str)
            await interaction.response.send_message(embed=emb)

    # clear queue command
    @app_commands.command(name="clear_queue", description="Clears the current queue")
    async def clear_queue(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        if len(queue) > 0:
            queue.clear()
            await interaction.response.send_message("Queue cleared!")
        else:
            await interaction.response.send_message("There is no queue to clear!")

    # skip command
    @app_commands.command(name="skip", description="Skips the current audio")
    async def skip(self, interaction: discord.Interaction):
        await interaction.response.defer()

        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await interaction.followup.send("Skipped current audio!")
        else:
            await interaction.followup.send("Nothing is playing!")

    # pause command
    @app_commands.command(name="pause", description="Pauses audio")
    async def pause(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            if interaction.guild.voice_client.is_paused():
                await interaction.response.send_message(f"Audio is already paused!")
                return

            interaction.guild.voice_client.pause()
            await interaction.response.send_message(f"Audio paused!")
        else:
            await interaction.response.send_message(f"Not currently in a voice channel! Please use `/join` to join a voice channel.")

    # resume command
    @app_commands.command(name="resume", description="Resumes audio")
    async def resume(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            if interaction.guild.voice_client.is_paused():
                interaction.guild.voice_client.resume()
                await interaction.response.send_message(f"Resuming audio...")
            else:
                await interaction.response.send_message(f"Audio is not currently paused!")
        else:
            await interaction.response.send_message(f"Not currently in a voice channel! Please use `/join` to join a voice channel.")

    # stop command
    @app_commands.command(name="stop", description="Stop and clear queue")
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.defer()

        guild_id = interaction.guild.id
        self.queues[guild_id] = []
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            await interaction.followup.send("Stopped and cleared queue!")
        else:
            await interaction.followup.send("Not in a voice channel!")

# create setup function for cog
async def setup(bot):
    await bot.add_cog(Music(bot))