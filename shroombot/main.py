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
from aiotdlib.api import MessageDocument, MessagePhoto, MessageSticker

from shroombot.ban_manager import BanManager
from shroombot.server import (
    MyDocumentMessage,
    MyPhotoMessage,
    MyStickerMessage,
    MyTextMessage,
)

logger = logging.getLogger(__name__)


app = typer.Typer()


@app.command()
def run(  # pylint: disable=too-many-locals
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
    bind: str = typer.Option(
        ..., envvar="BOT_API_SERVER_BIND", help="Server bind address"
    ),
    root_path: str = typer.Option("", envvar="BOT_API_ROOT_PATH", help="API root path"),
    formatter: str = typer.Option(
        "standard", envvar="LOG_FORMATTER", help="Log formatter"
    ),
):
    import asyncio
    import base64
    import logging.config as logging_config

    from aiotdlib.api import (
        MessageForumTopicCreated,
        MessageForumTopicIsHiddenToggled,
        MessageText,
        UpdateNewMessage,
    )
    from aiotdlib.api.api import API
    from aiotdlib.client import Client

    from shroombot.anonymizer import Anonymizer
    from shroombot.server import process_incomming_message
    from shroombot.shroomgen import ShroomNameRandomizer, default_shroom_names
    from shroombot.telegram import LiveTelegramApi

    from . import api_server, server

    randomizer = ShroomNameRandomizer(default_shroom_names())

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
            admin_chat_id=-1002232979097,
        )

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

            await process_incomming_message(
                server_data,
                message.chat_id,
                message.message_thread_id,
                content,
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
    ban_manager = BanManager(ban_file)
    banned_users = ban_manager.get_banned_users()

    if banned_users:
        banned_list = ", ".join(map(str, sorted(banned_users)))
        typer.echo(
            f"🚫 Заблокированные пользователи ({len(banned_users)}): {banned_list}"
        )
    else:
        typer.echo("✅ В данный момент никто не заблокирован")


@app.command()
def help_ban():
    """Show help for ban commands"""
    help_text = """🛡️ **Справка по командам блокировки**

**CLI команды:**
• `shroombot ban <user_id>` - Заблокировать пользователя по ID
• `shroombot unban <user_id>` - Разблокировать пользователя по ID
• `shroombot list-banned` - Показать всех заблокированных пользователей
• `shroombot help-ban` - Показать эту справку

**Telegram команды (Админ чат):**
• `/ban <user_id>` - Заблокировать по ID пользователя
• `/ban` - Ответить на сообщение пользователя чтобы заблокировать
• `/unban <user_id>` - Разблокировать по ID пользователя
• `/unban` - Ответить на сообщение пользователя чтобы разблокировать
• `/banned` - Показать всех заблокированных пользователей
• `/help` - Показать справку по Telegram

**Как получить ID пользователя:**
1. Когда пользователь отправляет сообщение, его ID показывается в админ чате
2. Ответьте на его сообщение командой `/ban` или `/unban` в админ чате
3. Используйте ID пользователя из админ чата для CLI команд

**Пример:**
В админ чате: Ответьте на спам-сообщение командой `/ban` чтобы мгновенно заблокировать этого пользователя!"""

    typer.echo(help_text)


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
