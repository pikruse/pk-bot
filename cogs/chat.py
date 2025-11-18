import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import asyncio
import logging
import json

LLM_PORT = 11434

# make cog for chatting with LLM
class Chat(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.LLM_PORT = 11434
        self.model_name = "qwen3:8b"
        self.system_prompt = "You are Chudley Updoot, a helpful and friendly assistant." \
                            "Your goal is to be as helpful and as engaging as possible in conversation." \
                            "Answer all questions from users honestly, correctly, and accurately." \
                            "In addition, talk like a redditor."
                                
        
    # call ollama 
    async def call_ollama(self, prompt):
        try:
            # prepare request payload
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "system": self.system_prompt
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                        f"http://localhost:{self.LLM_PORT}/api/generate",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            raise Exception(f"LLM error: {response.status}: {error_text}")
                        
                        data = await response.json()
                        if "response" in data:
                            return data["response"]
                        else:
                            raise Exception(f"Unexpected response format: {data}")
        except aiohttp.ClientError as e:
            raise Exception(f"Connection error: {str(e)}")            
    
    async def get_channel_context(self, channel, limit=5):
        """Fetch the last N messages from the channel"""
        context = ""
        messages = []

        async for message in channel.history(limit=limit):
            messages.append(message)

        messages.reverse()
        for message in messages:
            context += f"{message.author.display_name}: {message.clean_content}\n"
        return context
    
    @app_commands.command(name="chat", description="Chat with Chudley")
    @app_commands.describe(message="The message you want to send to Chudley")
    async def chat(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer()
        
        # get channel where user sent the message
        channel = interaction.channel
        try:
            context = await self.get_channel_context(channel)
            user_prompt = f"""Recent chat context:
                {context}
                {interaction.user.display_name}: {message}
                Assistant:"""
            response_text = await self.call_ollama(user_prompt)
            if len(response_text) > 2000:
                response_text = response_text[:1997] + "..."
            await interaction.followup.send(f"{response_text}")

        except Exception as e:
            logging.error(f"Chat error: {str(e)}")
            await interaction.followup.send("An error occurred while processing your request.")
    
# create setup function for cog
async def setup(bot: commands.Bot): # Added type hint
    await bot.add_cog(Chat(bot))
    logging.info("Chat Cog Loaded")
                