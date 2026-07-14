import discord
from discord.ext import commands
from config import *


class Amalgam(commands.Bot):
    async def setup_hook(self):
        initial_extensions = [
            # add cogs here like this:
            "cogs.review",
            "cogs.threads",
        ]

        for extension in initial_extensions:
            await self.load_extension(extension)


intents = discord.Intents.none()
intents.guilds = True
intents.messages = True
intents.message_content = True
intents.emojis_and_stickers = True

bot = Amalgam(command_prefix=BOT_PREFIX, intents=intents, max_messages=16)


@bot.event
async def on_connect():
    print("Loaded Discord")


@bot.event
async def on_ready():
    print("------")
    print("Logged in as")
    print(bot.user.name)
    print(bot.user.id)
    print("Using Active development branch")
    print(discord.utils.utcnow().strftime("%d/%m/%Y %I:%M:%S:%f"))
    print("------")


@bot.check
async def globally_block_dms(ctx):
    return ctx.guild is not None


bot.run(TOKEN, reconnect=True)
