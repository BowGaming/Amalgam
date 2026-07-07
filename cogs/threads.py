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

               # Open database
        self.conn = sqlite3.connect("forward_threads.db")
        self.cursor = self.conn.cursor()
        
        # Create table if missing
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS forward_threads (
            original_id INTEGER PRIMARY KEY,
            mirrored_channel_id INTEGER NOT NULL,
            mirrored_id INTEGER NOT NULL
        )
        """)
        self.conn.commit()

    def make_forwarded_content(self, message):
        return (
            #Add indicator as to who sent the message, for example:
            #f"Review from **{message.author.display_name}**:\n\n"
            #f"{message.content}"
        )
    
    async def forward_thread(self, message, out_review_channel_id):
        
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
            INSERT INTO forward_threads
            (original_id, mirrored_channel_id, mirrored_id)
            VALUES (?, ?, ?)
            """,
            (message.id, target_channel.id, mirrored.id)
        )
        self.conn.commit()

    @commands.Cog.listener()
    async def on_message(self, message) :
        if message.author.bot :
            return
            
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

        # Stops here if user is banned in out server
        out_guild = self.bot.get_guild(out_guild_id)
        if out_guild:
            try:
                ban = await out_guild.fetch_ban(message.author)
                # User is banned
                return
            except discord.NotFound:
                pass

        await self.forward_review(message, out_review_channel_id)
        
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

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):

        if "content" not in payload.data:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return
        
        try:
            after = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        if after.author.bot:
            return
        
        if after.guild.id == self.guild_id_MD:
            home_review_channel_id = config.comic_review_channel_MD

        elif after.guild.id == self.guild_id_DCO:
            home_review_channel_id = config.comic_review_channel_DCO

        else:
            return

        if after.channel.id != home_review_channel_id:
            return

        self.cursor.execute(
            """
            SELECT mirrored_channel_id, mirrored_id
            FROM forward_reviews
            WHERE original_id = ?
            """,
            (after.id,)
        )
    
        result = self.cursor.fetchone()
    
        if result is None:
            return
    
        channel_id, mirrored_id = result

        mirror_channel = self.bot.get_channel(channel_id)

        try:
            mirrored = await mirror_channel.fetch_message(mirrored_id)
        except discord.NotFound:
            return

        await mirrored.edit(
            content=self.make_forwarded_content(after)
        )

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        
        self.cursor.execute(
            """
            SELECT mirrored_channel_id, mirrored_id
            FROM forward_reviews
            WHERE original_id = ?
            """,
            (payload.message_id,)
        )
    
        result = self.cursor.fetchone()
    
        if result is None:
            return    

        channel_id, mirrored_id = result

        channel = self.bot.get_channel(channel_id)

        if channel is None:
            return
        
        try:
            message = await channel.fetch_message(mirrored_id)
            await message.delete()
        except discord.NotFound:
            pass

        self.cursor.execute(
            "DELETE FROM forward_reviews WHERE original_id = ?",
            (payload.message_id,)
        )
        self.conn.commit()
                
async def setup(bot: commands.Bot) :
    await bot.add_cog(ReviewCog(bot))
