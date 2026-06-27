import discord
from discord.ext import commands

import os

from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
env_path = BASE_DIR / ".env"

load_dotenv(dotenv_path=env_path, override=True)

TOKEN = os.getenv("DISCORD_TOKEN")
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")


class Amalgam(commands.Bot):
    async def setup_hook(self):
        initial_extensions = [
          #add cogs here like this:
          #"cogs.example"
        ]

        for extension in initial_extensions:
            await self.load_extension(extension)


intents = discord.Intents.all()

get_pre = lambda bot, message: BOT_PREFIX

bot = Amalgam(
    command_prefix=get_pre, intents=intents, max_messages=16
)

@bot.event
async def on_connect():
    print("Loaded Discord")

@bot.event
async def on_ready():
    print("------")
    print("Logged in as")
    print(bot.user.name)
    print(bot.user.id)
    print(discord.utils.utcnow().strftime("%d/%m/%Y %I:%M:%S:%f"))
    print("This is the new bot, Amalgam")
    print("------")

@bot.check
async def globally_block_dms(ctx):
    return ctx.guild is not None

bot.run(TOKEN, reconnect=True)
