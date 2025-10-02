# necessary imports
import discord
from discord import app_commands
from discord import FFmpegPCMAudio, PCMVolumeTransformer # Corrected import for FFmpegPCMAudio
from discord.ext import commands
from dotenv import load_dotenv
import os
import yt_dlp
import asyncio
import logging
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO) # Use INFO or DEBUG as needed

# options
intents = discord.Intents.all() # Consider more specific intents if possible

YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'cookiefile': 'cookies.txt',
    'default_search': 'ytsearch', 
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'compat_opts': ['seperate-video-versions'],  # YouTube compatibility
}
   

FFMPEG_OPTIONS = {
    'before_options': (
        '-reconnect 1 -reconnect_streamed 1 '
        '-reconnect_delay_max 5 -nostdin '
        '-hide_banner -loglevel error'
    ),
    'options': (
        '-vn '
    ),
    'stderr': subprocess.PIPE 
}

class MusicControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="⏭️ Skip", style=discord.ButtonStyle.secondary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Music")
        if not cog:
            await interaction.response.send_message("Music system is not available.", ephemeral=True)
            return
        result = cog.handle_skip(interaction.guild, interaction.user)
        await interaction.response.send_message(content=result, ephemeral=False)

    @discord.ui.button(label="⏯️ Pause/Resume", style=discord.ButtonStyle.primary)
    async def pause_resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Music")
        if not cog:
            await interaction.response.send_message("Music system is not available.", ephemeral=True)
            return
        
        voice_client = interaction.guild.voice_client
        if not voice_client:
            await interaction.response.send_message("Not connected to a voice channel.", ephemeral=True)
            return
        
        if interaction.user.voice is None or interaction.user.voice.channel != voice_client.channel:
            await interaction.response.send_message("You must be in the same voice channel.", ephemeral=True)
            return
        
        if voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("⏸️ Paused.", ephemeral=False)

        elif voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("▶️ Resumed.", ephemeral=False)
        
        else:
            await interaction.response.send_message("Nothing is playing to pause/resume.", ephemeral=True)

    @discord.ui.button(label="⏹️ Stop", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Music")
        if not cog:
            await interaction.response.send_message("Music system is not available.", ephemeral=True)
            return
        result = await cog.handle_stop(interaction.guild, interaction.user)
        await interaction.response.send_message(content=result, ephemeral=False)


# create Music class
class Music(commands.Cog):

    # define init method
    def __init__(self, client: commands.Bot): # Added type hint for client
        self.client = client
        self.queues = {}  # stores queues per guild: {guild_id: [(url, title), ...]}
        self.text_channels = {}  # stores text channels per guild: {guild_id: channel_id}
        self.current_song = {} # Stores the currently playing song info: {guild_id: (url, title)}
        self.active_processes = {}

    # Helper to get guild-specific queue
    def get_queue(self, guild_id: int) -> list:
        return self.queues.setdefault(guild_id, [])

    # Helper to get guild-specific text channel
    async def get_text_channel(self, guild_id: int) -> discord.TextChannel | None:
        channel_id = self.text_channels.get(guild_id)
        if channel_id:
            return self.client.get_channel(channel_id)
        # Fallback: Try to find a suitable channel if none stored (e.g., after restart)
        guild = self.client.get_guild(guild_id)
        if guild:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    self.text_channels[guild_id] = channel.id # Store for next time
                    return channel
        return None
    
    # cleanup processes helper
    async def cleanup_processes(self, guild_id: int):
        process = self.active_processes.get(guild_id)
        if process:
            try:
                if process.poll() is None:
                    process.kill()
                    await asyncio.sleep(0.5)
            except Exception as e:
                logging.warning(f"Cleanup error for guild {guild_id}: {e}")
            finally:
                del self.active_processes[guild_id]
                logging.info(f"Cleaned up process for guild {guild_id}") 

    # Helper to clean up guild state
    def cleanup_guild(self, guild_id: int):
        self.queues.pop(guild_id, None)
        self.text_channels.pop(guild_id, None)
        self.current_song.pop(guild_id, None)
        logging.info(f"Cleaned up state for guild {guild_id}")

    # The core playback loop starter
    async def play_next(self, guild_id: int):
        queue = self.get_queue(guild_id)
        guild = self.client.get_guild(guild_id)
        text_channel = await self.get_text_channel(guild_id) # Use helper

        if not guild or not guild.voice_client:
            return

        voice_client = guild.voice_client

        # Stop previous playback if any (safety measure)
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop() # This will trigger the 'after' callback if one was running
        
        if voice_client.is_paused():
            return
        
        if queue:
            url, title, headers = queue.pop(0)
            self.current_song[guild_id] = (url, title) # Store current song info

            try:
                # Modify the play_next method when creating the source:
                source = discord.FFmpegPCMAudio(
                    executable='ffmpeg',  # Explicitly specify executable
                    source=url,
                    **FFMPEG_OPTIONS
                )
                self.active_processes[guild_id] = source._process
                transformed_source = PCMVolumeTransformer(source, volume=0.3) # Apply volume here

                def after_play(error):
                    self.current_song.pop(guild_id, None)
                    if error:
                        logging.error(f"Player error: {error}")
                    
                    # Proper process cleanup
                    if voice_client.source:
                        if hasattr(voice_client.source, 'cleanup'):
                            voice_client.source.cleanup()
                    
                    # Schedule next only if not paused
                    if not voice_client.is_paused():
                        asyncio.run_coroutine_threadsafe(self.play_next(guild_id), self.client.loop)

                voice_client.play(transformed_source, after=after_play)

                if text_channel:
                    await text_channel.send(f"▶️ Now Playing: **{title}**")
                else:
                    logging.warning(f"Could not send 'Now Playing' message for guild {guild_id}: No text channel found.")

            except Exception as e:
                logging.error(f"Error playing song in guild {guild_id}: {e}", exc_info=True)
                if text_channel:
                    await text_channel.send(f"❌ Error playing **{title}**: `{e}`")
                # Try to play the next song even if current one fails
                await self.play_next(guild_id)

        else:
            # Queue is empty
            if text_channel:
                await text_channel.send("⏹️ Queue finished. Disconnecting.")
            await asyncio.sleep(5) # Give a small delay before disconnecting
            if voice_client.is_connected(): # Check again before disconnect
                 await voice_client.disconnect()
            self.cleanup_guild(guild_id) # Clean up state

    # play command
    @app_commands.command(name="play", description="Play audio from YouTube")
    @app_commands.describe(query="Song name or URL")
    async def play(self, interaction: discord.Interaction, *, query: str):
        await interaction.response.defer()
        guild_id = interaction.guild.id
        self.text_channels[guild_id] = interaction.channel.id

        # Validate user voice state
        if not interaction.user.voice:
            return await interaction.followup.send("🔊 You need to be in a voice channel!")

        try:
            # Connect to voice channel
            voice_client = interaction.guild.voice_client
            if not voice_client:
                voice_client = await interaction.user.voice.channel.connect(timeout=15)
            elif voice_client.channel != interaction.user.voice.channel:
                await voice_client.move_to(interaction.user.voice.channel)

            # Extract audio information
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))

                # Get first valid entry
                if 'entries' in info:
                    entry = next((e for e in info['entries'] if e and e.get('url')), None)
                else:
                    entry = info

                if not entry:
                    return await interaction.followup.send("❌ No playable content found!")

                # Get direct audio stream URL and headers
                audio_format = next((
                    f for f in entry.get('formats', [])
                    if f.get('acodec') != 'none' 
                    and f.get('protocol') in ('https', 'http_dash_segments')
                    and f.get('vcodec') == 'none'  # Audio only
                ), entry.get('formats', [{}])[0])  # Fallback to first format

                if not audio_format:
                    return await interaction.followup.send("❌ Could not find playable audio format!")

                song_url = audio_format['url']
                song_title = entry.get('title', 'Unknown Track')
                headers = entry.get('http_headers', {})

            # Build FFmpeg options with headers
            header_list = [f"{k}: {v}" for k, v in headers.items()]
            header_str = "\\r\\n".join(header_list)
            ffmpeg_options = {
                'before_options': (
                    f"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
                    f"-headers '{header_str}'"
                ),
                'options': '-vn -acodec libopus -b:a 192k -f opus'
            }

            # Create audio source and play
            source = discord.FFmpegPCMAudio(song_url, **ffmpeg_options)
            volume_source = PCMVolumeTransformer(source, volume=0.3)

            # Add to queue or play immediately
            queue = self.get_queue(guild_id)
            queue.append((song_url, song_title, headers))
            
            if not voice_client.is_playing() and not voice_client.is_paused():
                await self.play_next(guild_id)
                await interaction.followup.send(f"🎶 Now playing: **{song_title}**", view=MusicControlView())
            else:
                await interaction.followup.send(f"🎧 Added to queue: **{song_title}**", view=MusicControlView())

        except yt_dlp.utils.DownloadError as e:
            await interaction.followup.send(f"❌ YouTube download error: {str(e)}")
        except discord.ClientException as e:
            await interaction.followup.send(f"🔇 Audio error: {str(e)}")
        except Exception as e:
            logging.error(f"Play error: {str(e)}", exc_info=True)
            await interaction.followup.send("⚠️ Failed to play audio. Please try again.")

    # join voice channel
    @app_commands.command(name="join", description="Joins your current voice channel")
    async def join(self, interaction: discord.Interaction):
        await interaction.response.defer()

        if not interaction.user.voice:
            return await interaction.followup.send("🔊 You must be in a voice channel!")

        user_channel = interaction.user.voice.channel
        voice_client = interaction.guild.voice_client

        try:
            if voice_client and voice_client.is_connected():
                 if voice_client.channel == user_channel:
                     await interaction.followup.send("✅ Already connected to your channel!")
                 else:
                     await voice_client.move_to(user_channel)
                     await interaction.followup.send(f"✅ Moved to {user_channel.name}!")
            else:
                await user_channel.connect(timeout=15.0)
                await interaction.followup.send(f"✅ Joined {user_channel.name}!")
            # Store text channel where join was initiated if not already set
            if interaction.guild.id not in self.text_channels:
                 self.text_channels[interaction.guild.id] = interaction.channel.id
        except asyncio.TimeoutError:
            await interaction.followup.send("⌛ Connection timed out. Please try again.")
        except discord.ClientException as e:
            await interaction.followup.send(f"⚠️ Error joining/moving: {e}")
        except Exception as e:
            logging.error(f"Error in join command for guild {interaction.guild.id}: {e}", exc_info=True)
            await interaction.followup.send(f"❓ An unexpected error occurred: {e}")

    # leave voice channel
    @app_commands.command(name="leave", description="Disconnects the bot from the voice channel")
    async def leave(self, interaction: discord.Interaction):
        await interaction.response.defer()
        voice_client = interaction.guild.voice_client

        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
            await interaction.followup.send("👋 Disconnected from the voice channel.")
            self.cleanup_guild(interaction.guild.id) # Clean up state on leave
        else:
            await interaction.followup.send("❓ I'm not currently in a voice channel.")

    # view queue command
    @app_commands.command(name="queue", description="Shows the current song queue")
    async def queue(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild_id = interaction.guild.id
        queue = self.get_queue(guild_id)
        current = self.current_song.get(guild_id, ())
        
        embed = discord.Embed(title="🎵 Music Queue", color=discord.Color.blurple())
        
        # Handle current song safely
        if current:
            try:
                # Support both (url, title) and (url, title, headers) formats
                current_title = current[1] if len(current) >= 2 else "Unknown Title"
            except (IndexError, TypeError):
                current_title = "Unknown Title"
            embed.add_field(name="▶️ Now Playing", value=f"**{current_title}**", inline=False)
        
        # Build queue list with version-tolerant unpacking
        if queue:
            queue_list = []
            for idx, item in enumerate(queue[:10], start=1):
                try:
                    # Support both item formats
                    title = item[1] if len(item) >= 2 else "Unknown Title"
                except (IndexError, TypeError):
                    title = "Unknown Title"
                queue_list.append(f"{idx}. **{title}**")
            
            if len(queue) > 10:
                queue_list.append(f"\n...and {len(queue)-10} more")
            
            embed.add_field(name="🔜 Up Next", value="\n".join(queue_list), inline=False)
        else:
            embed.description = "🎶 The queue is empty!"
        
        await interaction.followup.send(embed=embed, view=MusicControlView())

    # clear queue command
    @app_commands.command(name="clear", description="Clears the current song queue")
    async def clear_queue(self, interaction: discord.Interaction):
        queue = self.get_queue(interaction.guild.id)
        if queue:
            queue.clear()
            await interaction.response.send_message("🗑️ Queue cleared!")
        else:
            await interaction.response.send_message(" Queue is already empty!")

    # skip command
    @app_commands.command(name="skip", description="Skips the current song")
    async def skip(self, interaction: discord.Interaction): 
        await interaction.response.defer()
        voice_client = interaction.guild.voice_client
        guild_id = interaction.guild.id

        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            current = self.current_song.get(guild_id)
            title_to_skip = f"**{current[1]}**" if current else "the current song"

            voice_client.stop() # Triggers 'after' callback which calls play_next
            await interaction.followup.send(f"⏭️ Skipped {title_to_skip}!")
            # play_next will be called automatically by the 'after' callback
        else:
            await interaction.followup.send("❓ Nothing is playing to skip!")

    # skip helper
    def handle_skip(self, guild: discord.Guild, user: discord.Member) -> str:
        voice_client = guild.voice_client
        if not voice_client or not (voice_client.is_playing() or voice_client.is_paused()):
            return "❓ Nothing is playing to skip!"
        if user.voice is None or user.voice.channel != voice_client.channel:
            return "🔇 You must be in the same voice channel to skip!"
        current = self.current_song.get(guild.id)
        title_to_skip = current[1] if current else "the current song"
        voice_client.stop()
        return f"⏭️ Skipped **{title_to_skip}**!"

    # pause command
    @commands.command(name="pause")
    async def pause(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("⏸️ Paused!")
        else:
            await interaction.response.send_message("❌ Nothing is playing!")

    # resume command
    @app_commands.command(name="resume", description="Resumes the paused song")
    async def resume(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("▶️ Resuming audio...")
        elif voice_client and voice_client.is_playing():
             await interaction.response.send_message(" Audio is already playing!")
        else:
            await interaction.response.send_message("❓ Nothing is paused to resume.")

    # stop command
    @app_commands.command(name="stop", description="Stops playback, clears queue, and disconnects")
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        guild_id = interaction.guild.id
        voice_client = interaction.guild.voice_client

        # Clear the queue first
        self.get_queue(guild_id).clear()
        logging.info(f"Queue cleared for guild {guild_id} by /stop command.")

        if voice_client and voice_client.is_connected():
            # Stop any current playback (important to prevent 'after' callback issues)
            if voice_client.is_playing() or voice_client.is_paused():
                voice_client.stop()
            await voice_client.disconnect()
            await interaction.followup.send("⏹️ Stopped playback, cleared queue, and disconnected.")
            self.cleanup_guild(guild_id) # Clean up state
        else:
            # Still clear state even if not connected, just in case
            self.cleanup_guild(guild_id)
            await interaction.followup.send("⏹️ Cleared queue (was not in a voice channel).")

    # stop helper 
    async def handle_stop(self, guild: discord.Guild, user: discord.Member) -> str:
        voice_client = guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return "❌ Not connected to a voice channel."
        if user.voice is None or user.voice.channel != voice_client.channel:
            return "🔇 You must be in the same voice channel."
        queue = self.get_queue(guild.id)
        queue.clear()
        self.current_song.pop(guild.id, None)
        voice_client.stop()
        await voice_client.disconnect()
        self.cleanup_guild(guild.id)
        return "⏹️ Stopped playback, cleared queue, and disconnected."

# create setup function for cog
async def setup(bot: commands.Bot): # Added type hint
    await bot.add_cog(Music(bot))
    logging.info("Music Cog Loaded")