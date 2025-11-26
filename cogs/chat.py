import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
from collections import defaultdict
import time
import asyncio
import logging
import json

LLM_PORT = 11434


class Chat(commands.Cog):
    """Chat Cog: forwards messages to a local LLM and replies in-channel.

    The class provides utilities to collect recent channel context, call
    a local LLM HTTP API, and respond when the bot is mentioned.
    """

    def __init__(self, client: commands.Bot):
        self.client = client
        self.LLM_PORT = LLM_PORT
        self.model_name = "qwen3:0.6b"
        # Track messages we've already responded to (prevent double-response)
        self._responded_messages: set[int] = set()
        # Use a neutral, safe system prompt by default. Keep persona/config
        # changes out of source control or configurable via runtime settings.
        self.system_prompt = (
            "You are a helpful, polite, and informative assistant. Respond concisely "
            "and respectfully, follow user instructions, and avoid generating harmful or offensive content."
        )

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
    
    async def get_channel_context(self, channel: discord.TextChannel, limit: int = 5) -> str:
        """Fetch the last `limit` messages from `channel` and return a single
        string containing them in chronological order.
        """
        context = ""
        messages = []

        async for message in channel.history(limit=limit):
            messages.append(message)

        messages.reverse()
        for message in messages:
            if message.author != self.client.user:
                context += f"{message.author.display_name}: {message.clean_content}\n"
        return context
    
    async def process_chat_message(self, message_content: str, author: discord.Member, channel: discord.TextChannel) -> str:
        """Prepare a prompt with recent context and call the LLM backend.

        Returns the LLM response text or an error message on failure.
        """
        try:
            context = await self.get_channel_context(channel)
            user_prompt = f"""Recent chat context:
            {context}
            {author.display_name}: {message_content}
            Assistant:""" 
            response_text = await self.call_ollama(user_prompt)
            return response_text
        except Exception as e:
            logging.error(f"Chat error: {str(e)}")
            return f"An error occurred while processing your request: {str(e)}"
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Reply when the bot is mentioned or when a user replies to the bot's message.

        This listener ignores messages from the bot itself. It triggers on:
        1. Direct @mentions of the bot.
        2. Replies to any message authored by the bot.
        """
        # Ignore bot's own messages
        if message.author == self.client.user:
            return

        # Prevent double-processing the same message
        if message.id in self._responded_messages:
            logging.info(f"Skipping already-processed message: id={message.id}")
            return

        # Determine if this message should trigger a response
        is_mention = self.client.user in message.mentions
        is_reply_to_bot = (
            message.reference is not None
            and message.reference.resolved is not None
            and isinstance(message.reference.resolved, discord.Message)
            and message.reference.resolved.author == self.client.user
        )

        # Debug: log trigger info
        logging.info(f"on_message fired: id={message.id}, is_mention={is_mention}, is_reply_to_bot={is_reply_to_bot}")

        if is_mention or is_reply_to_bot:
            # Mark as processed immediately to prevent race conditions
            self._responded_messages.add(message.id)
            # Keep set from growing indefinitely
            if len(self._responded_messages) > 1000:
                self._responded_messages.clear()

            # Strip mention tokens from content
            content = message.content
            for mention in message.mentions:
                content = content.replace(f'<@!{mention.id}>', '').replace(f'<@{mention.id}>', '')
            content = content.strip()

            if content:
                async with message.channel.typing():
                    response_text = await self.process_chat_message(
                        content,
                        message.author,
                        message.channel
                    )

                    if len(response_text) > 2000:
                        response_text = response_text[:1997] + "..."

                    logging.info(f"Sending reply for message id={message.id}")
                    await message.reply(response_text)
            else:
                await message.reply("Hello! How can I help you today?")
    
# create setup function for cog
async def setup(bot: commands.Bot):
    await bot.add_cog(Chat(bot))
    logging.info("Chat Cog Loaded")
                