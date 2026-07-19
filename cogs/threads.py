import discord
from discord.ext import commands
from discord import Embed, Forbidden
from discord.utils import escape_markdown
import config
import re
import sqlite3

# Constants
max_content_length = 1990


class ThreadCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.guild_id_MD = config.guild_MD
        self.guild_id_DCO = config.guild_DCO

        # Open database
        self.conn = sqlite3.connect("forward_reviews.db")
        self.cursor = self.conn.cursor()

        # Create tables if missing
        # forward_threads stores all db info needed to determine what original thread belongs to what mirrored thread. This info is gathered in cog review.py
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS forward_threads (
            original_thread_id INTEGER PRIMARY KEY,
            mirrored_thread_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL
        )
        """)
        self.conn.commit()

        # forward_thread_messages stores all db info needed to determine what original thread belongs to what mirrored thread
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS forward_thread_messages (
            original_thread_message_id INTEGER PRIMARY KEY,
            mirrored_thread_message_id INTEGER NOT NULL
        )
        """)
        self.conn.commit()

    """Function that alters original message content for forwarding (cutting message up to fit character limit, adding OP credit)"""

    def make_forwarded_content(self, message):
        markdown_author_name = escape_markdown(message.author.display_name)
        return (
            f"Message from **{markdown_author_name}**:\n\n" f"{message.content}"
        )

    """Function that forwards the message"""

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
        mirrored = await target_channel.send(
            content=modified_review, files=files if files else None
        )

        # Store ID mapping
        self.cursor.execute(
            """
            INSERT INTO forward_thread_messages
            (original_thread_message_id, mirrored_thread_message_id)
            VALUES (?, ?)
            """,
            (message.id, mirrored.id),
        )
        self.conn.commit()

    # ======================================================================================================================================================================================
    # Listener for new thread messages
    @commands.Cog.listener()
    async def on_message(self, message):

        # Ignore bot messages, messages not sent in a thread, messages sent in DMs
        if message.author.bot:
            return
        if not isinstance(message.channel, discord.Thread):
            return
        if message.guild is None:
            return

        # Assign variables based on in which server the thread message is sent. Also ignore if thread message is not sent in MD or DCO
        if message.guild.id == self.guild_id_MD:
            home_review_channel_id = config.comic_review_channel_MD
            out_guild_id = config.guild_DCO
        elif message.guild.id == self.guild_id_DCO:
            home_review_channel_id = config.comic_review_channel_DCO
            out_guild_id = config.guild_MD
        else:
            return

        parent_channel = message.channel.parent
        if parent_channel is None:
            return
        parent_channel_id = parent_channel.id

        # Ignore messages not sent in review channel threads
        if parent_channel_id != home_review_channel_id:
            return

        # Retrieve data from db for following executions
        self.cursor.execute(
            """
            SELECT mirrored_thread_id, owner_id
            FROM forward_threads
            WHERE original_thread_id = ?
            """,
            (message.channel.id,),
        )

        result = self.cursor.fetchone()
        # Stop if no mirrored thread exists
        if result is None:
            return
        mirrored_thread_id, owner_id = result

        # Ignore all thread messages not sent by review OP
        if message.author.id != owner_id:
            return

        # Check if user is banned in other server. If so, don't continue
        out_guild = self.bot.get_guild(out_guild_id)
        if out_guild:
            try:
                await out_guild.fetch_ban(message.author)
                # User is banned
                return
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        # Regex pattern, NEED TO ADJUST! (also not in use right now)
        pattern = re.compile(
            r"##\s*.+\s*"  # Comic name header
            r"\*\*year and writer:\*\*.+?"
            r"\*\*rating:\*\*.+?"
            r"\*\*review:\*\*.+",
            re.IGNORECASE | re.DOTALL,
        )

        # Review message does not pass format
        # if not pattern.search(message.content):

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
        if payload.guild_id is None:
            return

        # Get new message
        after = payload.message

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

        # Ignore edits if not sent in thread
        if not isinstance(after.channel, discord.Thread):
            return
        parent_channel = after.channel.parent
        if parent_channel is None:
            return
        parent_channel_id = parent_channel.id

        # Ignore edits not sent in review channel threads
        if parent_channel_id != home_review_channel_id:
            return

        # Retrieve data from db's for following executions
        self.cursor.execute(
            """
            SELECT mirrored_thread_message_id
            FROM forward_thread_messages
            WHERE original_thread_message_id = ?
            """,
            (payload.message_id,),
        )

        result = self.cursor.fetchone()
        # Ignore if message has no mirror
        if result is None:
            return
        mirrored_id = result[0]

        self.cursor.execute(
            """
            SELECT mirrored_thread_id
            FROM forward_threads
            WHERE original_thread_id = ?
            """,
            (payload.channel_id,),
        )

        result = self.cursor.fetchone()
        if result is None:
            return
        mirrored_thread_id = result[0]

        # Get mirror thread
        if payload.guild_id is None:
            return

        # Find original mirrored message
        mirror_channel = self.bot.get_channel(mirrored_thread_id)
        try:
            mirrored = await mirror_channel.fetch_message(mirrored_id)
        except discord.NotFound:
            return

        # Edit mirrored message
        await mirrored.edit(content=self.make_forwarded_content(after))

    # ======================================================================================================================================================================================
    # Listener for deletion of forwarded thread messages
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):

        # Retrieve data from db's for following executions
        self.cursor.execute(
            """
            SELECT mirrored_thread_message_id
            FROM forward_thread_messages
            WHERE original_thread_message_id = ?
            """,
            (payload.message_id,),
        )

        result = self.cursor.fetchone()
        # Ignore if message has no mirror
        if result is None:
            return
        mirrored_id = result[0]

        self.cursor.execute(
            """
            SELECT mirrored_thread_id
            FROM forward_threads
            WHERE original_thread_id = ?
            """,
            (payload.channel_id,),
        )

        result = self.cursor.fetchone()
        if result is None:
            return
        mirrored_thread_id = result[0]

        # Ignore DMs
        if payload.guild_id is None:
            return

        # Delete mirrored review
        mirror_channel = self.bot.get_channel(mirrored_thread_id)
        try:
            message = await mirror_channel.fetch_message(mirrored_id)
            await message.delete()
        except discord.NotFound:
            pass

        # Delete db entry from db
        self.cursor.execute(
            "DELETE FROM forward_thread_messages WHERE original_thread_message_id = ?",
            (payload.message_id,),
        )
        self.conn.commit()


async def setup(bot: commands.Bot):
    await bot.add_cog(ThreadCog(bot))
