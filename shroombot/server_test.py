"""
Testing of the primary server functionality
"""

import os
from tempfile import TemporaryDirectory

import pytest
from cryptography.fernet import Fernet

from shroombot.anonymizer import Anonymizer
from shroombot.ban_manager import BanManager
from shroombot.server import (
    MyMessageType,
    MyTextMessage,
    NameRandomizer,
    ServerData,
    TelegramApi,
    process_incomming_message_simple,
)


class MockTelegramApi(TelegramApi):
    def __init__(
        self, topic_names: dict[int, str], chats: dict[int, dict[int, list[str]]]
    ):
        self.topic_names = topic_names
        self.chats = chats
        self.last_message_id: int = 0

    async def send_message(
        self,
        chat_id: int,
        message: MyMessageType,
    ) -> int:
        """
        Send message to specific chat and thread
        """
        assert isinstance(message, MyTextMessage)
        self.chats[chat_id][0].append(message.text)

        self.last_message_id += 1

        return self.last_message_id

    async def send_topic_message(
        self,
        chat_id: int,
        topic_id: int,
        message: MyMessageType,
    ):
        """
        Send message to specific chat and thread
        """
        assert isinstance(message, MyTextMessage)
        if topic_id not in self.chats[chat_id]:
            self.chats[chat_id][topic_id] = []
        self.chats[chat_id][topic_id].append(message.text)

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

        # Create a temporary ban file for testing
        ban_file = os.path.join(temp_dir, "banned_users.csv")

        server_data = ServerData(
            telegram=MockTelegramApi(topic_names, chats),
            randomizer=MockRandomizer(),
            anonymizer=anonymizer,
            ban_manager=BanManager(ban_file),
            admin_chat_id=0,
        )

        async def send_message(chat: int, message: str, topic: int = 0):
            if chat not in chats:
                chats[chat] = {0: []}

            chats[chat][topic].append(message)

            await process_incomming_message_simple(
                server_data, chat, topic, MyTextMessage(message)
            )

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


@pytest.mark.asyncio
async def test_ban_functionality():  # pylint: disable=too-many-locals
    """Test ban functionality integration"""
    topic_names = {0: "Test Topic"}
    chats = {0: {}}  # Initialize admin chat

    with TemporaryDirectory() as temp_dir:
        mapping_file = os.path.join(temp_dir, "mapping.bin")
        ban_file = os.path.join(temp_dir, "banned_users.csv")

        encryption_key = Fernet.generate_key()

        anonymizer = await Anonymizer.from_file(mapping_file, encryption_key)
        ban_manager = BanManager(ban_file)

        server_data = ServerData(
            telegram=MockTelegramApi(topic_names, chats),
            randomizer=MockRandomizer(),
            anonymizer=anonymizer,
            ban_manager=ban_manager,
            admin_chat_id=0,
        )

        # Test 1: User sends message (should be forwarded)
        user_chat_id = 123456789
        user_message = MyTextMessage("Hello, this is a test message")

        await process_incomming_message_simple(
            server_data, user_chat_id, 0, user_message
        )

        # Should have sent message to admin chat
        assert len(chats) > 0
        assert 0 in chats  # Admin chat should have the message
        assert len(chats[0]) > 0  # Should have created a topic

        # Test 2: Admin bans user
        admin_message = MyTextMessage(f"/ban {user_chat_id}")

        await process_incomming_message_simple(
            server_data, server_data.admin_chat_id, 0, admin_message
        )

        # Check that user is banned
        assert ban_manager.is_banned(user_chat_id)

        # Test 3: Banned user sends message (should be ignored)
        initial_admin_topic_count = len(chats[0])

        banned_user_message = MyTextMessage("This should be ignored")
        await process_incomming_message_simple(
            server_data, user_chat_id, 0, banned_user_message
        )

        # Should not have sent any new messages to admin chat
        assert len(chats[0]) == initial_admin_topic_count

        # Test 4: Admin unbans user
        unban_message = MyTextMessage(f"/unban {user_chat_id}")

        await process_incomming_message_simple(
            server_data, server_data.admin_chat_id, 0, unban_message
        )

        # Check that user is unbanned
        assert not ban_manager.is_banned(user_chat_id)

        # Test 5: Unbanned user sends message (should be forwarded again)
        # Count messages in the first topic (where user messages go)
        first_topic_id = list(chats[0].keys())[0]
        initial_message_count = len(chats[0][first_topic_id])

        unbanned_user_message = MyTextMessage("I'm back!")
        await process_incomming_message_simple(
            server_data, user_chat_id, 0, unbanned_user_message
        )

        # Should have sent new message to admin chat
        assert len(chats[0][first_topic_id]) > initial_message_count


@pytest.mark.asyncio
async def test_ban_commands():
    """Test ban commands in admin chat"""
    topic_names = {0: "Test Topic"}
    chats = {0: {}}  # Initialize admin chat

    with TemporaryDirectory() as temp_dir:
        mapping_file = os.path.join(temp_dir, "mapping.bin")
        ban_file = os.path.join(temp_dir, "banned_users.csv")

        encryption_key = Fernet.generate_key()

        anonymizer = await Anonymizer.from_file(mapping_file, encryption_key)
        ban_manager = BanManager(ban_file)

        server_data = ServerData(
            telegram=MockTelegramApi(topic_names, chats),
            randomizer=MockRandomizer(),
            anonymizer=anonymizer,
            ban_manager=ban_manager,
            admin_chat_id=0,
        )

        # Test /banned command
        banned_command = MyTextMessage("/banned")
        await process_incomming_message_simple(
            server_data, server_data.admin_chat_id, 0, banned_command
        )

        # Should have sent message about no banned users
        admin_messages = chats.get(server_data.admin_chat_id, {}).get(0, [])
        assert any(
            "В данный момент никто не заблокирован" in str(msg)
            for msg in admin_messages
        )

        # Test /help command
        help_command = MyTextMessage("/help")
        await process_incomming_message_simple(
            server_data, server_data.admin_chat_id, 0, help_command
        )

        # Should have sent help message
        admin_messages = chats.get(server_data.admin_chat_id, {}).get(0, [])
        assert any(
            "Справка по командам блокировки" in str(msg) for msg in admin_messages
        )
