"""
Testing of the primary server functionality
"""

import os
from tempfile import TemporaryDirectory

import pytest
from cryptography.fernet import Fernet

from shroombot.anonymizer import Anonymizer
from shroombot.server import (
    NameRandomizer,
    ServerData,
    TelegramApi,
    process_incomming_message,
)


class MockTelegramApi(TelegramApi):
    def __init__(
        self, topic_names: dict[int, str], chats: dict[int, dict[int, list[str]]]
    ):
        self.topic_names = topic_names
        self.chats = chats

    async def send_message(
        self,
        chat_id: int,
        text: str,
    ):
        """
        Send message to specific chat and thread
        """
        self.chats[chat_id][0].append(text)

    async def send_topic_message(
        self,
        chat_id: int,
        topic_id: int,
        text: str,
    ):
        """
        Send message to specific chat and thread
        """
        self.chats[chat_id][topic_id].append(text)

    async def create_topic(self, chat_id: int, title: str) -> int:
        """
        Creates topic in a chat.

        Returns topic id
        """
        topic_id = len(self.chats[chat_id])
        self.chats[chat_id][topic_id] = list()
        self.topic_names[topic_id] = title
        return topic_id


class MockRandomizer(NameRandomizer):
    def __init__(self):
        self.names = [
            "Name2",
            "Name1",
        ]

    def get_random_topic_name(self) -> str:
        return self.names.pop()


@pytest.mark.asyncio
async def test_server_default():
    topic_names = dict()
    chats = {
        0: {0: []},  # admin chat
    }

    with TemporaryDirectory() as temp_dir:
        mapping_file = os.path.join(temp_dir, "mapping.bin")

        encryption_key = Fernet.generate_key()

        anonymizer = await Anonymizer.from_file(mapping_file, encryption_key)

        server_data = ServerData(
            telegram=MockTelegramApi(topic_names, chats),
            randomizer=MockRandomizer(),
            anonymizer=anonymizer,
            admin_chat_id=0,
        )

        async def send_message(chat: int, message: str, topic: int = 0):
            if chat not in chats:
                chats[chat] = {0: []}

            chats[chat][topic].append(message)

            await process_incomming_message(server_data, chat, topic, message)

        # Interaction with user 1
        await send_message(1, "Hey! I need help!")
        await send_message(0, "No problem!", topic=1)

        # Interaction with user 2
        await send_message(2, "I need money!")
        await send_message(0, "Here you go!", topic=2)

        assert topic_names == {1: "Name1", 2: "Name2"}

        assert chats == {
            0: {
                0: [],
                1: ["Hey! I need help!", "No problem!"],
                2: ["I need money!", "Here you go!"],
            },
            1: {0: ["Hey! I need help!", "No problem!"]},
            2: {0: ["I need money!", "Here you go!"]},
        }
