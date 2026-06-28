import discord
from discord.ext import commands
from config import *

class Amalgam(commands.Bot):
    async def setup_hook(self):
        initial_extensions = [
          #add cogs here like this:
          "cogs.review"
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
    print("------")

@bot.check
async def globally_block_dms(ctx):
    return ctx.guild is not None

bot.run(TOKEN, reconnect=True)
