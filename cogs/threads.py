import discord
from discord.ext import commands
from discord import Embed, Forbidden
import config
import re
import sqlite3


class ThreadCog(commands.Cog) :
    def __init__(self, bot) :
        self.bot = bot

        self.guild_id_MD = config.guild_MD
        self.guild_id_DCO = config.guild_DCO

        # Max character length for messages. Messages get cut up in pieces if exceeds the below value
        self.max_content_length = 1990

        # Open database
        self.conn = sqlite3.connect("forward_reviews.db")
        self.cursor = self.conn.cursor()
        
        # Create tables if missing
        # forwarded_threads stores all db info needed to determine what original thread belongs to what mirrored thread. This info is gathered in cog review.py
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS forwarded_threads (
            original_thread_id INTEGER PRIMARY KEY,
            mirrored_thread_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL
        )
        """)
        self.conn.commit()

        # forwarded_thread_messages stores all db info needed to determine what original thread belongs to what mirrored thread
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS forwarded_thread_messages (
            original_thread_message_id INTEGER PRIMARY KEY,
            mirrored_thread_message_id INTEGER NOT NULL
        )
        """)
        self.conn.commit()

    # Function that alters original message content for forwarding (cutting message up to fit character limit, adding OP credit)
    def make_forwarded_content(self, message):
        return (
            f"Review from **{message.author.display_name}**:\n\n"
            f"{message.content}"
        )

    # Function that forwards the message
    async def forward_content(self, message, out_thread_id):
        
        target_channel = self.bot.get_channel(out_thread_id)
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
            INSERT INTO forwarded_thread_messages
            (original_thread_message_id, mirrored_thread_message_id)
            VALUES (?, ?)
            """,
            (message.id, mirrored.id)
        )
        self.conn.commit()

    # ======================================================================================================================================================================================
    # Listener for new thread messages
    @commands.Cog.listener()
    async def on_message(self, message) :
       
        # Ignore bot messages, messages not sent in a thread, messages sent in DMs
        if message.author.bot :
            return
        if not isinstance(message.channel, discord.Thread):
            return
        if message.guild is None:
            return

        # Assign variables based on in which server the thread message is sent. Also ignore if thread message is not sent in MD or DCO
        if message.guild.id == self.guild_id_MD:
            home_guild_id = config.guild_MD
            home_review_channel_id = config.comic_review_channel_MD

            out_guild_id = config.guild_DCO
            out_review_channel_id = config.comic_review_channel_DCO

        elif message.guild.id == self.guild_id_DCO:
            home_guild_id = config.guild_DCO
            home_review_channel_id = config.comic_review_channel_DCO

            out_guild_id = config.guild_MD
            out_review_channel_id = config.comic_review_channel_MD
        else:
            return

        parent_channel = message.channel.parent
        parent_channel_id = parent_channel.id
        
        # Ignore messages not sent in review channel threads    
        if parent_channel_id != home_review_channel_id:
            return

        # Retrieve data from db for following executions
        self.cursor.execute(
            """
            SELECT mirrored_thread_id, owner_id
            FROM forwarded_threads
            WHERE original_thread_id = ?
            """,
            (message.channel.id,)
        )
        
        result = self.cursor.fetchone()
        # Stop if no mirrored thread exists
        if result is None:
            return
        mirrored_thread_id, owner_id = result
        out_channel = self.bot.get_channel(mirrored_thread_id)

        # Ignore all thread messages not sent by review OP
        if message.author.id != owner_id:
            return
        
        # Regex pattern, NEED TO ADJUST!
        pattern = re.compile(
            r"##\s*.+\s*"                                   # Comic name header
            r"\*\*year and writer:\*\*.+?"
            r"\*\*rating:\*\*.+?"
            r"\*\*review:\*\*.+",
            re.IGNORECASE | re.DOTALL
        )

        # Review message does not pass format
        #if not pattern.search(message.content):

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
        await self.forward_content(message, mirrored_thread_id)

    # ======================================================================================================================================================================================
    # Listener for edits of forwarded thread messages
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
    # Listener for deletion of forwarded thread messages
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
    await bot.add_cog(ThreadCog(bot))
