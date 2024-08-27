# import packages
import discord
import yt_dlp
import asyncio
from discord.ext import commands

# define intents
intents = discord.Intents.all()

# define ffmpeg options
FFMPEG_OPTIONS = {'options': '-vn'}
YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': 'True'}

# make music class
class Music(commands.Cog):

    # init command
    def __init__(self, client):
        self.client = client
        self.queue = []
    
    # play command
    @commands.command()
    async def play(self, ctx, *, search):
        voice_channel = ctx.author.voice.channel if ctx.author.voice else None

        # music bot is not in a voice channel
        if not voice_channel:
            await ctx.send("You need to be in a voice channel to play music!")
            return
        
        # connect to voice channel
        if not ctx.voice_client:
            await voice_channel.connect()
        
        # get video url from queue
        async with ctx.typing():
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(f"ytsearch:{search}", download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                url = info['url']
                title = info['title']
                self.queue.append((url, title))
                await ctx.send(f"Added to queue: **{title}**")
        
        # play music if not playing
        if not ctx.voice_client.is_playing():
            self.play_next(ctx)

    async def play_next(self, ctx):
        if self.queue:
            url, title = self.queue.pop(0)
            source = await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)
            ctx.voice_client.play(source, after=lambda e: self.client.loop.create_task(self.play_next(ctx)))
            await ctx.send(f"Now playing: **{title}**")
        elif not ctx.voice_client.is_playing():
            await ctx.send("Queue is empty.")
    
    @commands.command()
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("Skipped.")