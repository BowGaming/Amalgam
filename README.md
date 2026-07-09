# Amalgam

A Discord bot that mirrors comic book reviews between two servers, keeping both communities in sync.

## What It Does

When a member posts a review in the review channel, Amalgam:

- Validates it against the required format — invalid posts are deleted and the author is DM'd their original content to fix
- Creates a discussion thread on the review in both servers simultaneously
- Forwards the review to the partner server
- Keeps a sticky format guide pinned at the bottom of both channels at all times
- Propagates edits and deletions across both servers
- Forwards thread replies from the original reviewer
- Respects bans — a user banned in the destination server won't have their review forwarded

## Review Format

Posts that don't match this structure are deleted. The author receives a DM with their original text so they can repost.

```
## Comic Name
**Year and writer:** 
**Rating:** x/10
**Review:** Your thoughts here. Use ||spoiler tags|| for spoilers.
**MU/DCUI link:** (optional)
```

All four main fields are required. The MU/DCUI link is optional. The pattern is matched case-insensitively.

## Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/BowGaming/Amalgam.git
   cd Amalgam
   ```

2. **Install dependencies**

   ```bash
   pip install discord.py python-dotenv
   ```

3. **Create a `.env` file** in the project root — see [Configuration](#configuration) below.

4. **Run the bot**

   ```bash
   python main.py
   ```

## Configuration

All configuration is read from a `.env` file at startup.

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | Yes | Bot token from the Discord Developer Portal |
| `BOT_PREFIX` | No | Command prefix — defaults to `~` |
| `GUILD_MD` | Yes | Server ID for the first server (MD) |
| `GUILD_DCO` | Yes | Server ID for the second server (DCO) |
| `COMIC_REVIEW_CHANNEL_MD` | Yes | Channel ID for the review channel in MD |
| `COMIC_REVIEW_CHANNEL_DCO` | Yes | Channel ID for the review channel in DCO |
| `REVIEW_REACTION_EMOJI_MD` | Yes | Emoji ID for the reaction added to reviews in MD |
| `REVIEW_REACTION_EMOJI_DCO` | Yes | Emoji ID for the reaction added to reviews in DCO |

**Example `.env`:**

```env
# Bot credentials
DISCORD_TOKEN=your-token-here
BOT_PREFIX=~

# Server IDs (right-click server → Copy Server ID)
GUILD_MD=123456789012345678
GUILD_DCO=987654321098765432

# Review channel IDs
COMIC_REVIEW_CHANNEL_MD=111111111111111111
COMIC_REVIEW_CHANNEL_DCO=222222222222222222

# Custom emoji IDs (right-click emoji → Copy ID)
REVIEW_REACTION_EMOJI_MD=333333333333333333
REVIEW_REACTION_EMOJI_DCO=444444444444444444
```

## Bot Permissions

Grant these permissions in both servers when adding the bot:

- Read Messages / View Channels
- Send Messages
- Manage Messages
- Add Reactions
- Create Public Threads
- Send Messages in Threads
- Read Message History
- Ban Members

In the Discord Developer Portal, enable both **Server Members Intent** and **Message Content Intent** under Privileged Gateway Intents.

## Requirements

- Python 3.10+
- discord.py 2.x
- python-dotenv
