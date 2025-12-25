"""
Entrypoint of the application.

Implementation of the application CLI and logging setup
"""

# pylint: disable = import-outside-toplevel

# Keep imports here to a minimum
# so that help works quickly


import logging
from pathlib import Path

import typer

logger = logging.getLogger(__name__)


app = typer.Typer(pretty_exceptions_enable=False)


@app.command()
def run(  # pylint: disable=too-many-locals,too-many-statements
    *,
    chat_mapping_file: str = typer.Argument(..., help="Path to chat mapping file"),
    files_dir: str = typer.Argument(..., help="Directory for files"),
    ban_file: str = typer.Argument(..., help="Ban file path"),
    api_id: int = typer.Argument(..., envvar="API_ID", help="Telegram API ID"),
    api_hash: str = typer.Argument(..., envvar="API_HASH", help="Telegram API hash"),
    bot_token: str = typer.Argument(..., envvar="BOT_TOKEN", help="Bot token"),
    encryption_key: str = typer.Argument(
        ..., envvar="ENCRYPTION_KEY", help="Encryption key"
    ),
    admin_chat_id: int = typer.Argument(..., envvar="BOT_ADMIN_CHAT_ID"),
    bind: str = typer.Option(
        ..., envvar="BOT_API_SERVER_BIND", help="Server bind address"
    ),
    root_path: str = typer.Option("", envvar="BOT_API_ROOT_PATH", help="API root path"),
    bot_type: str = typer.Option(
        "forum",
        "--bot-type",
        envvar="BOT_TYPE",
        help="Bot type: 'forum' (topic-based) or 'simple' (reply-based)",
    ),
    name_type: str = typer.Option(
        "mushroom",
        "--name-type",
        envvar="BOT_NAMING_TYPE",
        help="Name type: 'mushroom' or 'generic'",
    ),
    formatter: str = typer.Option(
        "standard", envvar="LOG_FORMATTER", help="Log formatter"
    ),
):
    import asyncio
    import base64
    import logging.config as logging_config

    from aiotdlib.api import (
        MessageDocument,
        MessageForumTopicCreated,
        MessageForumTopicIsHiddenToggled,
        MessagePhoto,
        MessageReplyToMessage,
        MessageSticker,
        MessageText,
        UpdateNewMessage,
    )
    from aiotdlib.api.api import API
    from aiotdlib.client import Client

    from shroombot.anonymizer import Anonymizer
    from shroombot.ban_manager import BanManager
    from shroombot.bot_handler import ForumBotHandler, SimpleBotHandler
    from shroombot.server import (
        MyDocumentMessage,
        MyPhotoMessage,
        MyStickerMessage,
        MyTextMessage,
    )
    from shroombot.shroomgen import (
        GenericNameRandomizer,
        ShroomNameRandomizer,
        default_shroom_names,
    )
    from shroombot.telegram import LiveTelegramApi

    from . import api_server, server

    # Validate bot_type and name_type
    if bot_type not in ("forum", "simple"):
        logger.error("Invalid bot_type: %s. Must be 'forum' or 'simple'", bot_type)
        raise typer.BadParameter("bot_type must be 'forum' or 'simple'")

    if name_type not in ("mushroom", "generic"):
        logger.error(
            "Invalid name_type: %s. Must be 'mushroom' or 'generic'", name_type
        )
        raise typer.BadParameter("name_type must be 'mushroom' or 'generic'")

    # Create randomizer based on name_type
    if name_type == "mushroom":
        randomizer = ShroomNameRandomizer(default_shroom_names())
    else:  # generic
        randomizer = GenericNameRandomizer()

    # Configure logging
    logging_config.dictConfig(_get_logging_config(logging.INFO, formatter))

    async def _entry():
        client = Client(
            api_id=api_id,
            api_hash=api_hash,
            bot_token=bot_token,
            files_directory=Path(files_dir),
        )

        anonymizer = await Anonymizer.from_file(
            chat_mapping_file, base64.b64decode(encryption_key)
        )

        ban_manager = BanManager(ban_file)

        server_data = server.ServerData(
            telegram=LiveTelegramApi(client),
            anonymizer=anonymizer,
            randomizer=randomizer,
            ban_manager=ban_manager,
            # The admin chat id only can be fetched when you
            # manually add bot to a chat.
            # And from this addition event you can extract the chat id
            admin_chat_id=admin_chat_id,
        )

        # Create handler based on bot_type
        if bot_type == "forum":
            handler = ForumBotHandler()
            logger.info("Using ForumBotHandler (topic-based)")
        else:  # simple
            handler = SimpleBotHandler()
            logger.info("Using SimpleBotHandler (reply-based)")

        async def message_handler(_, update: UpdateNewMessage):
            message = update.message

            content = message.content

            if isinstance(content, MessageText):
                content = MyTextMessage(
                    text=content.text.text,
                    entities=content.text.entities,
                )
            elif isinstance(content, MessageForumTopicIsHiddenToggled):
                return
            elif isinstance(content, MessageForumTopicCreated):
                return
            elif isinstance(content, MessageDocument):
                content = MyDocumentMessage(
                    id=content.document.document.remote.id,
                    caption=content.caption.text,
                )
            elif isinstance(content, MessagePhoto):
                content = MyPhotoMessage(
                    id=content.photo.sizes[0].photo.remote.id,
                    caption=content.caption.text,
                )
            elif isinstance(content, MessageSticker):
                content = MyStickerMessage(
                    id=content.sticker.sticker.remote.id,
                    emoji=content.sticker.emoji,
                )
            else:
                logger.warning(
                    "Encountered unsupported message type %s. Chat %d thread %d",
                    content.__class__.__name__,
                    message.chat_id,
                    message.message_thread_id,
                )
                content = MyTextMessage(
                    f"<unsupported type {content.__class__.__name__}>",
                )

            # Route to appropriate handler method
            if message.chat_id == server_data.admin_chat_id:
                # Message from admin

                reply_to_id: int | None = None

                if isinstance(message.reply_to, MessageReplyToMessage):
                    reply_to_id = message.reply_to.message_id

                await handler.process_admin_message(
                    data=server_data,
                    chat_id=message.chat_id,
                    message_id=message.id,
                    thread_id=message.message_thread_id,
                    message=content,
                    reply_to_message_id=reply_to_id,
                )
            else:
                # Message from user
                await handler.process_user_message(
                    data=server_data, chat_id=message.chat_id, message=content
                )

        client.add_event_handler(message_handler, API.Types.UPDATE_NEW_MESSAGE)

        async with client:
            await api_server.run_api_server(bind, root_path)

            while True:
                await asyncio.sleep(1)

    asyncio.run(_entry())


@app.command()
def ban(
    user_id: int = typer.Argument(..., help="User ID to ban"),
    ban_file: str = typer.Option(
        "banned_users.csv", envvar="BAN_FILE", help="Path to ban file"
    ),
):
    """Ban a user by ID"""
    from shroombot.ban_manager import BanManager

    ban_manager = BanManager(ban_file)

    if ban_manager.ban_user(user_id):
        typer.echo(f"✅ Пользователь {user_id} заблокирован")
    else:
        typer.echo(f"⚠️ Пользователь {user_id} уже был заблокирован")


@app.command()
def unban(
    user_id: int = typer.Argument(..., help="User ID to unban"),
    ban_file: str = typer.Option(
        "banned_users.csv", envvar="BAN_FILE", help="Path to ban file"
    ),
):
    """Unban a user by ID"""
    from shroombot.ban_manager import BanManager

    ban_manager = BanManager(ban_file)

    if ban_manager.unban_user(user_id):
        typer.echo(f"✅ Пользователь {user_id} разблокирован")
    else:
        typer.echo(f"⚠️ Пользователь {user_id} не был заблокирован")


@app.command()
def list_banned(
    ban_file: str = typer.Option(
        "banned_users.csv", envvar="BAN_FILE", help="Path to ban file"
    ),
):
    """List all banned users"""
    from shroombot.ban_manager import BanManager

    ban_manager = BanManager(ban_file)
    banned_users = ban_manager.get_banned_users()

    if banned_users:
        typer.echo(f"🚫 Заблокированные пользователи ({len(banned_users)}):")
        typer.echo("")
        for user_id, ban_info in sorted(banned_users.items()):
            ban_date = ban_info.banned_at.strftime("%Y-%m-%d %H:%M")
            line = f"📱 {user_id} | 📅 {ban_date}"
            if ban_info.thread_id:
                line += f" | 🧵 {ban_info.thread_id}"
            typer.echo(line)
    else:
        typer.echo("✅ В данный момент никто не заблокирован")


if __name__ == "__main__":
    app()


def _get_logging_config(level: int, formatter: str):
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s %(levelname)-8s| %(message)s",
                "datefmt": "%H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": formatter,
            },
        },
        "loggers": {
            "Client_1": {"level": "WARNING"},
        },
        "root": {
            "handlers": ["console"],
            "level": level,
        },
    }
