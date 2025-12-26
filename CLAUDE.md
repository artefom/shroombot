# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Shroombot is a Telegram bot for "Grybnytci" (Грибница) that provides anonymous messaging between users and admins. Users message the bot privately, and their messages are forwarded to an admin group with topics. Admins reply in the topics, and responses go back to users anonymously.

The project uses:
- **aiotdlib**: Low-level Telegram client library (not the bot API)
- **FastAPI + Uvicorn**: API server with Prometheus metrics
- **Typer**: CLI interface
- **Poetry**: Dependency management
- **Pydantic v1**: Data validation (note: pinned to <2.0)

**Multi-Bot Support**: The system now supports running multiple bot instances simultaneously with different bot types:
- **Forum Bot**: Topic-based system with random mushroom names (original behavior)
- **Simple Bot**: Reply-based system with generic names (new)

## Architecture

### Core Components

1. **Anonymizer** (`shroombot/anonymizer.py`): Bidirectional mapping between user chat IDs and admin forum topics. Data is encrypted and persisted to disk using Fernet encryption.

2. **Server** (`shroombot/server.py`): Core message routing logic
   - `process_incomming_message()`: Main entry point for all messages
   - `_process_admin_message()`: Handles messages from admin chat (including ban commands)
   - `_process_user_message()`: Handles messages from users, creates topics if needed
   - Message types: `MyTextMessage`, `MyPhotoMessage`, `MyDocumentMessage`, `MyStickerMessage`

3. **BanManager** (`shroombot/ban_manager.py`): CSV-based user ban system with timestamps and thread tracking.

4. **Telegram API** (`shroombot/telegram.py`): Wraps aiotdlib client, converts internal message types to Telegram API calls.

5. **Name Randomizer** (`shroombot/shroomgen.py`): Generates random mushroom names for forum topics. Also supports `GenericNameRandomizer` for simple bot.

6. **API Server** (`shroombot/api_server.py`): FastAPI app with health check and Prometheus metrics.

7. **BotHandler** (`shroombot/bot_handler.py`): Bot type abstraction
   - `ForumBotHandler`: Topic-based routing for forum bots
   - `SimpleBotHandler`: Reply-based routing with message ID mapping and name generation

### Message Flow

**Forum Bot (User → Admin):**
1. User sends message to bot
2. Check if user is banned (if yes, silently drop)
3. Get or create forum topic for user (with random mushroom name)
4. Forward message to admin chat in that topic

**Forum Bot (Admin → User):**
1. Admin replies in forum topic
2. Look up user chat ID from topic ID
3. Forward message to user
4. Admin commands (`/ban`, `/unban`, `/banned`, `/help`) are processed instead of forwarded

**Simple Bot (User → Admin):**
1. User sends message to bot
2. Check if user is banned (if yes, silently drop)
3. Generate or retrieve anonymous name for user (e.g., "User Alpha")
4. Prepend "👤 <generated_name>" to message
5. Forward to admin chat (no topic)
6. Store message_id → user_chat_id mapping

**Simple Bot (Admin → User):**
1. Admin replies to forwarded message (using Telegram reply feature)
2. Extract user_chat_id from reply_to_message_id via mapping
3. Fallback: parse generated name from message text and look up user_chat_id
4. Send reply to user
5. Admin commands (`/ban <name>`, `/ban <id>`, `/unban <name>`, `/banned`, `/help`) supported

## Common Commands

### Development

```bash
# Install dependencies (use virtual environment)
poetry install

# Activate virtual environment
poetry shell

# Run type checking
pyright shroombot/

# Run linting
pylint shroombot/

# Run tests
pytest

# Run pre-commit hooks manually
pre-commit run --all-files

# Format code
black shroombot/
isort shroombot/
```

### Running the Bot

```bash
# Main run command (requires all arguments)
shroombot run <chat_mapping_file> <files_dir> <ban_file> \
  --api-id <id> \
  --api-hash <hash> \
  --bot-token <token> \
  --encryption-key <key> \
  --bind <host:port>

# Or use environment variables (see .env.example)
export API_ID=...
export API_HASH=...
export BOT_TOKEN=...
export ENCRYPTION_KEY=...
export BOT_API_SERVER_BIND=0.0.0.0:8080

shroombot run mapping.bin .aiotdlib banned_users.csv
```

### Bot Types

The bot supports two different behavior modes:

**Forum Bot (--bot-type forum)**
- Topic-based system using Telegram supergroup forums
- Each user gets a dedicated topic in the admin chat
- Uses mushroom names by default (or generic with --name-type generic)
- Admins reply within topics

**Simple Bot (--bot-type simple)**
- Reply-based system for simple chats (no topics)
- User messages forwarded to admin chat with name prefix
- Uses generic names by default (User Alpha, Anonymous 1, etc.)
- Admins reply using Telegram's reply feature

```bash
# Run forum bot (default)
shroombot run mapping.bin .aiotdlib banned.csv

# Run simple bot
shroombot run mapping.bin .aiotdlib banned.csv --bot-type simple

# Run forum bot with generic names
shroombot run mapping.bin .aiotdlib banned.csv --bot-type forum --name-type generic

# Run simple bot with mushroom names
shroombot run mapping.bin .aiotdlib banned.csv --bot-type simple --name-type mushroom
```

### Ban Management CLI

```bash
# Ban a user
shroombot ban <user_id>

# Unban a user
shroombot unban <user_id>

# List banned users
shroombot list-banned
```

### Docker

```bash
# Build image
./build.sh
# or
docker build -f .deploy/Dockerfile -t shroombot .

# Run with Docker
docker run -d \
  -e API_ID="${API_ID}" \
  -e API_HASH="${API_HASH}" \
  -e BOT_TOKEN="${BOT_TOKEN}" \
  -e ENCRYPTION_KEY="${ENCRYPTION_KEY}" \
  -v "$(pwd)/mapping.bin:/mapping.bin" \
  -v "$(pwd)/.aiotdlib:/.aiotdlib" \
  -v "$(pwd)/banned_users.csv:/banned_users.csv" \
  shroombot
```

## Configuration Files

- **pyproject.toml**: Poetry dependencies, tool configs (pylint, black, isort, pytest, coverage)
- **pyrightconfig.json**: Pyright type checker config
- **.pre-commit-config.yaml**: Git hooks for black, isort, pylint, pyright
- **.env.example**: Required environment variables template
- **mapping.bin**: Encrypted chat-to-topic mappings (binary)
- **banned_users.csv**: Banned user list (format: `user_id,timestamp,thread_id`)

## Key Implementation Details

### Admin Chat ID
Hard-coded in `main.py:100`: `admin_chat_id=-1002232979097`. This is the supergroup where admin topics are created. Extract this ID when adding the bot to a new admin chat.

### Ban Commands (Admin Chat Only)
- `/ban <user_id>` or `/ban` (reply to message)
- `/unban <user_id>` or `/unban` (reply to message)
- `/banned` - list all banned users
- `/help` or `/banhelp` - show help

See BAN_USAGE.md for detailed usage guide.

### Message Types
All internal messages use custom types (`MyTextMessage`, etc.) rather than raw aiotdlib types. This abstraction allows for easier testing (see `server_test.py`).

### Encryption
Chat mappings are encrypted with Fernet (symmetric encryption). The encryption key must be base64-encoded and passed via `ENCRYPTION_KEY` env var.

### Logging
Standard Python logging with custom format (see `_get_logging_config()` in main.py). Uses INFO level by default, with WARNING for aiotdlib client.

### Testing
Tests use mocked `TelegramApi` implementations (see `server_test.py`, `telegram_test.py`, `anonymizer_test.py`).

## Future Requirements

See `Modifications_requirements.md` for planned feature to support multiple bots simultaneously with different admin chat configurations (topics vs. simple reply-based chat).

## Dependencies Notes

- **Pydantic**: Pinned to <2.0 for compatibility
- **aiotdlib**: Version 0.22.0, requires system deps (libssl, libc++)
- Python 3.11+ required
