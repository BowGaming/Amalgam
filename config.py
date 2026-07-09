import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
BOT_PREFIX = os.getenv("BOT_PREFIX", "~")

guild_MD = int(os.getenv("GUILD_MD", 0))
guild_DCO = int(os.getenv("GUILD_DCO", 0))
comic_review_channel_MD = int(os.getenv("COMIC_REVIEW_CHANNEL_MD", 0))
comic_review_channel_DCO = int(os.getenv("COMIC_REVIEW_CHANNEL_DCO", 0))
review_reaction_emoji_MD = int(os.getenv("REVIEW_REACTION_EMOJI_MD", 0))
review_reaction_emoji_DCO = int(os.getenv("REVIEW_REACTION_EMOJI_DCO", 0))
