"""
Testing of the telegram adapter over LIVE api
"""

# Importing telegram takes too long!
# That's why we're not importing here on top level
# pylint: disable=import-outside-toplevel

import os

import pytest

from shroombot.server import MyTextMessage


@pytest.mark.skip
@pytest.mark.asyncio
async def test_telegram_api():
    from aiotdlib.client import Client

    from .telegram import LiveTelegramApi

    async with Client(
        api_id=int(os.environ["API_ID"]),
        api_hash=os.environ["API_HASH"],
        bot_token=os.environ["BOT_TOKEN"],
    ) as client:
        telegram = LiveTelegramApi(client)

        # The admin chat id only can be fetched when you manually add bot to a chat.
        # And from this addition event you can extract the chat id
        admin_chat = -1002232979097

        chat_info = await client.get_chat_info(admin_chat)

        print(f"Chat info: {chat_info}")

        print(f"Admin chat: {admin_chat}")

        await telegram.send_message(admin_chat, MyTextMessage("Hello, world"))

        topic_id = await telegram.create_topic(admin_chat, "Test topic")

        await telegram.send_topic_message(
            admin_chat, topic_id, MyTextMessage("Test message")
        )
