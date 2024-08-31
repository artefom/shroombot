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
from aiotdlib.api import MessageDocument, MessagePhoto

from shroombot.server import MyDocumentMessage, MyPhotoMessage, MyTextMessage

logger = logging.getLogger(__name__)


app = typer.Typer()


@app.command()
def run(  # pylint: disable=too-many-locals
    chat_mapping_file: str,
    files_dir: str,
    api_id: int = typer.Argument(..., envvar="API_ID"),
    api_hash: str = typer.Argument(..., envvar="API_HASH"),
    bot_token: str = typer.Argument(..., envvar="BOT_TOKEN"),
    admin_chat: str = typer.Argument(..., envvar="ADMIN_CHAT"),
    bind: str = typer.Option(..., envvar="BOT_API_SERVER_BIND"),
    root_path: str = typer.Option("", envvar="BOT_API_ROOT_PATH"),
    encryption_key: str = typer.Argument(..., envvar="ENCRYPTION_KEY"),
    formatter: str = typer.Option("standard", envvar="LOG_FORMATTER"),
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
    from shroombot.telegram import LiveTelegramApi, get_chat_id

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

        server_data = server.ServerData(
            telegram=LiveTelegramApi(client),
            anonymizer=anonymizer,
            randomizer=randomizer,
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
                logger.info("Received photo: %s", content.json())
                content = MyPhotoMessage(
                    id=content.photo.sizes[0].photo.remote.id,
                    caption=content.caption.text,
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
            # Check that chat id matches
            admin_chat_id = await get_chat_id(client, admin_chat)
            assert admin_chat_id == server_data.admin_chat_id, admin_chat

            await api_server.run_api_server(bind, root_path)

            while True:
                await asyncio.sleep(1)

    asyncio.run(_entry())


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
