from discord.ext import commands
from discord import Embed, Forbidden
import config
import re


class ReviewCog(commands.Cog) :
    def __init__(self, bot) :
        self.bot = bot

        self.guild_id_MD = config.guild_MD
        self.guild_id_DCO = config.guild_DCO
    
        self.review_channel_id_MD = config.comic_review_channel_MD
        self.review_channel_id_DCO = config.comic_review_channel_DCO

        self.review_instruction_embed = Embed(
            title="**How to Post Reviews**",
            description=(
                "Please follow the format below when writing your review.\n"
                "Your message will be deleted if it doesn't follow the format.\n\n"
                "**Notes:**\n"
                "- Only post reviews for full runs, collected editions, or one-shots. Single issue reviews are allowed in threads (see below).\n"
                "- If you want to post single issue reviews, please make a review post for a full run/collected edition, then post your single issue reviews in the thread. You can edit the main post as you progress reading.\n"
                "- As these reviews are meant for people who haven't read the comic yet, please use spoiler brackets ``||like this||`` if you want to include spoilers in your review. Not using spoiler brackets on spoilers may lead to your review being removed."
            ),
        )

        self.format_message = (
            "```\n"
            "## Comic Name\n"
            "**Year and writer:**\n"
            "**Rating:** x/10\n"
            "**Review:** A few words about your thoughts on the comic and why you gave it that rating. You could include details such as the length of the book, quality of the art, required background reading, etc. Make sure to use spoiler brackets ||like this|| for any spoilers you want to include.\n"
            "**MU/DCUI link:** (optional) A link to the comic on Marvel Unlimited or DC Universe Infinite. This is not mandatory for the format."
            "```"
        )

    @commands.Cog.listener()
    async def on_message(self, message) :
        """Checks messages in the review channel and enforces format."""
        if message.author.bot :
            return
        
        if message.channel.id not in (self.review_channel_id_MD, self.review_channel_id_DCO):
            return
        
        # Regex pattern to match section headers (## or bold headers)
        pattern = re.compile(
            r"##\s*.+\s*"                                   # Comic name header
            r"\*\*year and writer:\*\*.+?"
            r"\*\*rating:\*\*.+?"
            r"\*\*review:\*\*.+",
            re.IGNORECASE | re.DOTALL
        )

        if not pattern.search(message.content):

            try:
                # Try to DM the user before deleting the message
                reason = (
                    "Your review post was removed because it doesn't follow the required format.\n"
                    "Please make sure to follow the provided format.\n"
                    "If you keep experiencing issues, try copying the format or a previous review, and fill in your own information.\n\n"
                    "Here’s what you wrote so you can easily copy and fix it:"
                )
        
                await message.author.send(
                    f"Hey {message.author.display_name},\n\n{reason}\n"
                )
                
                MAX_LENGTH = 1990
                content = message.content

                for i in range(0, len(content), MAX_LENGTH):
                    text = content[i:i + MAX_LENGTH]
                    await message.author.send(f"```\n{text}\n```")
                    
            except Forbidden:
                # User has DMs disabled or blocked the bot
                pass
            
            await message.delete()
            return
        
        # Remove previous embed messages from bot to keep latest at bottom
        async for msg in message.channel.history(limit = 5) :
            if msg.author == self.bot.user :
                await msg.delete()
            
        # Send sticky embeds at bottom
        await message.channel.send(embed=self.review_instruction_embed)
        await message.channel.send(content=self.format_message)

        # Add reaction to passed messages
        if message.guild.id == self.guild_id_MD:
            emoji = self.bot.get_emoji(config.review_reaction_emoji_MD) 
        if message.guild.self == self.guild_id_DCO:
            emoji = self.bot.get_emoji(config.review_reaction_emoji_DCO) 
        await message.add_reaction(emoji)

        # Create a thread for discussion
        first_line = message.content.strip().split("\n", 1)[0]
        comic_name = first_line.replace("##", "").strip()

        thread = await message.create_thread(
            name=f"Review: {comic_name} by {message.author.display_name}",
            auto_archive_duration=4320  # 3 days
        )

        await thread.send(
            f"Thread for discussing **{comic_name}**, reviewed by {message.author.display_name}!"
        )
            
async def setup(bot: commands.Bot) :
    await bot.add_cog(ReviewCog(bot))
