import discord
from discord.ext import commands
from discord import Embed, Forbidden
import config
import re
import sqlite3


class ReviewCog(commands.Cog) :
    def __init__(self, bot) :
        self.bot = bot

        self.guild_id_MD = config.guild_MD
        self.guild_id_DCO = config.guild_DCO

        # Max character length for messages. Messages get cut up in pieces if exceeds the below value
        self.max_content_length = 1990

        # Sticky messages
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

        # Open database
        self.conn = sqlite3.connect("forward_reviews.db")
        self.cursor = self.conn.cursor()
        
        # Create tables if missing
        # forward_reviews stores all db info needed to forward, edit and delete reviews
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS forward_reviews (
            original_id INTEGER PRIMARY KEY,
            mirrored_channel_id INTEGER NOT NULL,
            mirrored_id INTEGER NOT NULL
        )
        """)
        self.conn.commit()

        # forward_threads stores all db info needed to determine what original thread belongs to what mirrored thread. This info is used in cog threads.py
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS forward_threads (
            original_thread_id INTEGER PRIMARY KEY,
            mirrored_thread_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL
        )
        """)
        self.conn.commit()

    # Function that alters original review content for forwarding (cutting message up to fit character limit, adding OP credit)
    def make_forwarded_content(self, message):
        return (
            f"Review from **{message.author.display_name}**:\n\n"
            f"{message.content}"
        )

    # Function that forwards the review
    async def forward_review(self, message, out_review_channel_id):
        
        target_channel = self.bot.get_channel(out_review_channel_id)
        if not target_channel:
            return
    
        # Modify message before forwarding
        modified_review = self.make_forwarded_content(message)
    
        # Download attachments
        files = []
        for attachment in message.attachments:
            file = await attachment.to_file()
            files.append(file)
    
        # Send message with attachments
        mirrored = await target_channel.send(content=modified_review, files=files if files else None)
    
        # Store ID mapping
        self.cursor.execute(
            """
            INSERT INTO forward_reviews
            (original_id, mirrored_channel_id, mirrored_id)
            VALUES (?, ?, ?)
            """,
            (message.id, target_channel.id, mirrored.id)
        )
        self.conn.commit()

    # ======================================================================================================================================================================================
    # Listener for new reviews
    @commands.Cog.listener()
    async def on_message(self, message) :
       
        # Ignore bot messages
        if message.author.bot :
            return
        
        # Ignore DMs (globally_block_dms only gates commands, not listeners)
        if message.guild is None:
            return

        # Assign variables based on in which server the original review is sent. Also ignore if review is not sent in MD or DCO
        if message.guild.id == self.guild_id_MD:
            home_guild_id = config.guild_MD
            home_review_channel_id = config.comic_review_channel_MD
            home_emoji = self.bot.get_emoji(config.review_reaction_emoji_MD) 

            out_guild_id = config.guild_DCO
            out_review_channel_id = config.comic_review_channel_DCO
            out_emoji = self.bot.get_emoji(config.review_reaction_emoji_DCO) 

        elif message.guild.id == self.guild_id_DCO:
            home_guild_id = config.guild_DCO
            home_review_channel_id = config.comic_review_channel_DCO
            home_emoji = self.bot.get_emoji(config.review_reaction_emoji_DCO) 

            out_guild_id = config.guild_MD
            out_review_channel_id = config.comic_review_channel_MD
            out_emoji = self.bot.get_emoji(config.review_reaction_emoji_MD) 
        else:
            return
    
        # Ignore messages not sent in review channel    
        if message.channel.id != home_review_channel_id:
            return
        
        # Regex pattern to match section headers (## or bold headers)
        pattern = re.compile(
            r"##\s*.+\s*"                                   # Comic name header
            r"\*\*year and writer:\*\*.+?"
            r"\*\*rating:\*\*.+?"
            r"\*\*review:\*\*.+",
            re.IGNORECASE | re.DOTALL
        )

        # Review message does not pass format
        if not pattern.search(message.content):
            # Try to DM the user before deleting the message
            try:
                # Reason for deletion
                reason = (
                    "Your review post was removed because it doesn't follow the required format.\n"
                    "Please make sure to follow the provided format.\n"
                    "If you keep experiencing issues, try copying the format or a previous review, and fill in your own information.\n\n"
                    "Here’s what you wrote so you can easily copy and fix it:"
                )

                # Send reason for deletion
                await message.author.send(
                    f"Hey {message.author.display_name},\n\n{reason}\n"
                )

                # Send original message so user can copy and fix (note: messages deleted by automod will NOT be DMed to user!)
                content = message.content
                for i in range(0, len(content), self.max_content_length):
                    text = content[i:i + self.max_content_length]
                    await message.author.send(f"```\n{text}\n```")
            
            # User has DMs disabled or blocked the bot        
            except Forbidden:
                pass

            # Delete review message
            await message.delete()
            return
        
        # Remove previous embed messages from bot to keep latest at bottom
        async for msg in message.channel.history(limit=5):
            if msg.author == self.bot.user:
                if msg.content == self.format_message:
                    await msg.delete()
                if msg.embeds:
                    embed = msg.embeds[0]
                    if embed.title == self.review_instruction_embed.title:
                        await msg.delete()    
            
        # Send sticky embeds at bottom
        await message.channel.send(embed=self.review_instruction_embed)
        await message.channel.send(content=self.format_message)

        # Add reaction to passed messages
        await message.add_reaction(home_emoji)

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
        
        # ===============================================================================================================================================================
        # End of code for homeserver, beginning of code of out server

        # Check if user is banned in other server. If so, don't forward
        out_guild = self.bot.get_guild(out_guild_id)
        if out_guild:
            try:
                ban = await out_guild.fetch_ban(message.author)
                # User is banned
                return
            except discord.NotFound:
                pass

        # Forward review
        await self.forward_review(message, out_review_channel_id)

        # Retrieve data from db for following executions
        self.cursor.execute(
            """
            SELECT mirrored_channel_id, mirrored_id
            FROM forward_reviews
            WHERE original_id = ?
            """,
            (message.id,)
        )
        
        result = self.cursor.fetchone()
        channel_id, mirrored_id = result
        out_channel = self.bot.get_channel(channel_id)
        mirrored_review = await out_channel.fetch_message(mirrored_id)

        # Remove previous embed messages from bot to keep latest at bottom in out server
        async for msg in out_channel.history(limit=5):
            if msg.author == self.bot.user:
                if msg.content == self.format_message:
                    await msg.delete()
                if msg.embeds:
                    embed = msg.embeds[0]
                    if embed.title == self.review_instruction_embed.title:
                        await msg.delete()    

        # Send sticky embeds at bottom in out server
        await out_channel.send(embed=self.review_instruction_embed)
        await out_channel.send(content=self.format_message)

        # Add reaction to passed messages
        await mirrored_review.add_reaction(out_emoji)

        # Create a thread for discussion
        thread_out = await mirrored_review.create_thread(
            name=f"Review: {comic_name} by {message.author.display_name}",
            auto_archive_duration=4320  # 3 days
        )
        
        await thread_out.send(
            f"Thread for discussing **{comic_name}**, reviewed by {message.author.display_name}!"
        )

        # Store thread mapping
        self.cursor.execute(
            """
            INSERT INTO forward_threads
            (original_thread_id, mirrored_thread_id, owner_id)
            VALUES (?, ?, ?)
            """,
            (
                thread.id,
                thread_out.id,
                message.author.id
            )
        )
        self.conn.commit()

    # ======================================================================================================================================================================================
    # Listener for edits of reviews
    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):

        # Ignore if content wasn't edited
        if "content" not in payload.data:
            return

        # Ignore edits in DMs
        channel = self.bot.get_channel(payload.channel_id) 
        if channel is None:
            return

        # Get new message
        try:
            after = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        # Ignore edits by bot
        if after.author.bot:
            return

        # Assign variables based on in which server the edit is done. Also ignore if edit is not in MD or DCO
        if after.guild.id == self.guild_id_MD:
            home_review_channel_id = config.comic_review_channel_MD
        elif after.guild.id == self.guild_id_DCO:
            home_review_channel_id = config.comic_review_channel_DCO
        else:
            return

        # Ignore edits not made in review channel
        if after.channel.id != home_review_channel_id:
            return

        # Retrieve data from db for following executions
        self.cursor.execute(
            """
            SELECT mirrored_channel_id, mirrored_id
            FROM forward_reviews
            WHERE original_id = ?
            """,
            (after.id,)
        )
    
        result = self.cursor.fetchone()
        # Ignore if original review has no mirror
        if result is None:
            return
        channel_id, mirrored_id = result
        mirror_channel = self.bot.get_channel(channel_id)

        # Find original mirrored message
        try:
            mirrored = await mirror_channel.fetch_message(mirrored_id)
        except discord.NotFound:
            return

        # Edit mirrored message
        await mirrored.edit(
            content=self.make_forwarded_content(after)
        )

    # ======================================================================================================================================================================================
    # Listener for deletion of reviews
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):

        # Retrieve data from db for following executions
        self.cursor.execute(
            """
            SELECT mirrored_channel_id, mirrored_id
            FROM forward_reviews
            WHERE original_id = ?
            """,
            (payload.message_id,)
        )
        result = self.cursor.fetchone()
        # Ignore if original review has no mirror
        if result is None:
            return    
        channel_id, mirrored_id = result

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return

        # Delete mirrored review
        try:
            message = await channel.fetch_message(mirrored_id)
            await message.delete()
        except discord.NotFound:
            pass

        # Delete db entry from db
        self.cursor.execute(
            "DELETE FROM forward_reviews WHERE original_id = ?",
            (payload.message_id,)
        )
        self.conn.commit()
                
async def setup(bot: commands.Bot) :
    await bot.add_cog(ReviewCog(bot))
