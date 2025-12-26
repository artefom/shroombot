"""
Testing of the simple server functionality
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
)
from shroombot.simple_server import process_incomming_message_simple


class MockTelegramApi(TelegramApi):
    def __init__(self, chats: dict[int, list[tuple[str, int | None]]]):
        """
        chats: {chat_id: [(message_text, reply_to_message_id), ...]}
        """
        self.chats = chats
        # Track per-chat message IDs: {chat_id: last_message_id_in_that_chat}
        self.chat_message_counters: dict[int, int] = {}
        # Track (chat_id, message_id_in_chat) for looking up messages
        self.message_map: dict[tuple[int, int], int] = {}

    async def send_message(
        self,
        chat_id: int,
        message: MyMessageType,
    ) -> int:
        """
        Send message to specific chat
        Returns the message_id in that chat (starts from 1 for each chat)
        """
        assert isinstance(message, MyTextMessage)
        if chat_id not in self.chats:
            self.chats[chat_id] = []
        if chat_id not in self.chat_message_counters:
            self.chat_message_counters[chat_id] = 0

        # Increment message counter for this chat
        self.chat_message_counters[chat_id] += 1
        message_id_in_chat = self.chat_message_counters[chat_id]

        message_index = len(self.chats[chat_id])
        self.chats[chat_id].append((message.text, None))
        self.message_map[(chat_id, message_id_in_chat)] = message_index

        return message_id_in_chat

    async def send_topic_message(
        self,
        chat_id: int,
        topic_id: int,
        message: MyMessageType,
    ):
        """
        Not used in simple server
        """
        raise NotImplementedError("Simple server does not use topics")

    async def create_topic(self, chat_id: int, title: str) -> int:
        """
        Not used in simple server
        """
        raise NotImplementedError("Simple server does not use topics")


class MockRandomizer(NameRandomizer):
    def __init__(self):
        self.counter = 0
        self.names = [
            "Anonymous Alpha",
            "Anonymous Beta",
            "Anonymous Gamma",
            "Anonymous Delta",
            "Anonymous Epsilon",
        ]

    def get_random_topic_name(self) -> str:
        name = self.names[self.counter % len(self.names)]
        self.counter += 1
        return name


@pytest.mark.asyncio
async def test_simple_server_default():
    """Test basic user-admin message flow in simple bot"""
    chats = {
        0: [],  # admin chat
    }

    with TemporaryDirectory() as temp_dir:
        mapping_file = os.path.join(temp_dir, "mapping.bin")

        encryption_key = Fernet.generate_key()

        anonymizer = await Anonymizer.from_file(mapping_file, encryption_key)

        # Create a temporary ban file for testing
        ban_file = os.path.join(temp_dir, "banned_users.csv")

        telegram_api = MockTelegramApi(chats)
        server_data = ServerData(
            telegram=telegram_api,
            randomizer=MockRandomizer(),
            anonymizer=anonymizer,
            ban_manager=BanManager(ban_file),
            admin_chat_id=0,
        )

        # User 1 sends message
        await process_incomming_message_simple(
            server_data, 1, 0, MyTextMessage("Hey! I need help!")
        )

        # Check that message was forwarded to admin with name prefix
        assert len(chats[0]) == 1
        assert "👤 Anonymous Alpha" in chats[0][0][0]
        assert "Hey! I need help!" in chats[0][0][0]

        # Admin replies to user 1's message (reply_to_message_id = 1)
        await process_incomming_message_simple(
            server_data,
            0,
            0,
            MyTextMessage("No problem!"),
            reply_to_message_id=1,
        )

        # Check that user 1 received the reply
        assert len(chats[1]) == 1
        assert chats[1][0][0] == "No problem!"

        # User 2 sends message
        await process_incomming_message_simple(
            server_data, 2, 0, MyTextMessage("I need money!")
        )

        # Check that message was forwarded to admin with different name
        assert len(chats[0]) == 2
        assert "👤 Anonymous Beta" in chats[0][1][0]
        assert "I need money!" in chats[0][1][0]

        # Admin replies to user 2's message (reply_to_message_id = 2)
        await process_incomming_message_simple(
            server_data,
            0,
            0,
            MyTextMessage("Here you go!"),
            reply_to_message_id=2,
        )

        # Check that user 2 received the reply
        assert len(chats[2]) == 1
        assert chats[2][0][0] == "Here you go!"


@pytest.mark.asyncio
async def test_simple_server_start_command():
    """Test /start command sends greeting to user"""
    chats = {0: []}

    with TemporaryDirectory() as temp_dir:
        mapping_file = os.path.join(temp_dir, "mapping.bin")
        ban_file = os.path.join(temp_dir, "banned_users.csv")
        encryption_key = Fernet.generate_key()

        anonymizer = await Anonymizer.from_file(mapping_file, encryption_key)
        telegram_api = MockTelegramApi(chats)

        server_data = ServerData(
            telegram=telegram_api,
            randomizer=MockRandomizer(),
            anonymizer=anonymizer,
            ban_manager=BanManager(ban_file),
            admin_chat_id=0,
        )

        # User sends /start command
        await process_incomming_message_simple(
            server_data, 123, 0, MyTextMessage("/start")
        )

        # Check that user received greeting message
        assert 123 in chats
        assert len(chats[123]) == 1
        assert "Привет!" in chats[123][0][0]
        assert "анонимно" in chats[123][0][0]


@pytest.mark.asyncio
async def test_simple_server_admin_no_reply():
    """Test admin message without reply_to_message_id gets warning"""
    chats = {0: []}

    with TemporaryDirectory() as temp_dir:
        mapping_file = os.path.join(temp_dir, "mapping.bin")
        ban_file = os.path.join(temp_dir, "banned_users.csv")
        encryption_key = Fernet.generate_key()

        anonymizer = await Anonymizer.from_file(mapping_file, encryption_key)
        telegram_api = MockTelegramApi(chats)

        server_data = ServerData(
            telegram=telegram_api,
            randomizer=MockRandomizer(),
            anonymizer=anonymizer,
            ban_manager=BanManager(ban_file),
            admin_chat_id=0,
        )

        # Admin sends message without replying
        await process_incomming_message_simple(
            server_data, 0, 0, MyTextMessage("Random message"), reply_to_message_id=None
        )

        # Check that admin received warning
        assert len(chats[0]) == 1
        assert "⚠️" in chats[0][0][0]
        assert "reply" in chats[0][0][0].lower()


@pytest.mark.asyncio
async def test_simple_server_chatid_command():
    """Test /chatid command shows admin chat ID"""
    chats = {0: []}

    with TemporaryDirectory() as temp_dir:
        mapping_file = os.path.join(temp_dir, "mapping.bin")
        ban_file = os.path.join(temp_dir, "banned_users.csv")
        encryption_key = Fernet.generate_key()

        anonymizer = await Anonymizer.from_file(mapping_file, encryption_key)
        telegram_api = MockTelegramApi(chats)

        server_data = ServerData(
            telegram=telegram_api,
            randomizer=MockRandomizer(),
            anonymizer=anonymizer,
            ban_manager=BanManager(ban_file),
            admin_chat_id=0,
        )

        # Admin sends /chatid command
        await process_incomming_message_simple(
            server_data, 0, 0, MyTextMessage("/chatid")
        )

        # Check that admin received chat ID
        assert len(chats[0]) == 1
        assert "📊" in chats[0][0][0]
        assert "0" in chats[0][0][0]


@pytest.mark.asyncio
async def test_ban_functionality():
    """Test ban functionality in simple server"""
    chats = {0: []}

    with TemporaryDirectory() as temp_dir:
        mapping_file = os.path.join(temp_dir, "mapping.bin")
        ban_file = os.path.join(temp_dir, "banned_users.csv")
        encryption_key = Fernet.generate_key()

        anonymizer = await Anonymizer.from_file(mapping_file, encryption_key)
        telegram_api = MockTelegramApi(chats)
        ban_manager = BanManager(ban_file)

        server_data = ServerData(
            telegram=telegram_api,
            randomizer=MockRandomizer(),
            anonymizer=anonymizer,
            ban_manager=ban_manager,
            admin_chat_id=0,
        )

        user_chat_id = 123456789

        # Test 1: User sends message (should be forwarded)
        await process_incomming_message_simple(
            server_data, user_chat_id, 0, MyTextMessage("Hello, this is a test message")
        )

        # Should have sent message to admin chat
        assert len(chats[0]) == 1
        assert "👤 Anonymous Alpha" in chats[0][0][0]

        # Test 2: Admin bans user by replying with /ban command
        await process_incomming_message_simple(
            server_data,
            0,
            0,
            MyTextMessage("/ban"),
            reply_to_message_id=1,
        )

        # Check that user is banned
        assert ban_manager.is_banned(user_chat_id)
        # Check confirmation message
        assert any("заблокирован" in msg[0] for msg in chats[0])

        # Test 3: Banned user sends message (should be ignored)
        initial_admin_message_count = len(chats[0])

        await process_incomming_message_simple(
            server_data, user_chat_id, 0, MyTextMessage("This should be ignored")
        )

        # Should not have sent any new messages to admin chat
        assert len(chats[0]) == initial_admin_message_count

        # Test 4: Admin unbans user by replying with /unban command
        await process_incomming_message_simple(
            server_data,
            0,
            0,
            MyTextMessage("/unban"),
            reply_to_message_id=1,
        )

        # Check that user is unbanned
        assert not ban_manager.is_banned(user_chat_id)
        # Check confirmation message
        assert any("разблокирован" in msg[0] for msg in chats[0])

        # Test 5: Unbanned user sends message (should be forwarded again)
        initial_admin_message_count = len(chats[0])

        await process_incomming_message_simple(
            server_data, user_chat_id, 0, MyTextMessage("I'm back!")
        )

        # Should have sent new message to admin chat
        assert len(chats[0]) > initial_admin_message_count
        assert "I'm back!" in chats[0][-1][0]


@pytest.mark.asyncio
async def test_admin_reply_unknown_message():
    """Test admin replying to unknown message ID"""
    chats = {0: []}

    with TemporaryDirectory() as temp_dir:
        mapping_file = os.path.join(temp_dir, "mapping.bin")
        ban_file = os.path.join(temp_dir, "banned_users.csv")
        encryption_key = Fernet.generate_key()

        anonymizer = await Anonymizer.from_file(mapping_file, encryption_key)
        telegram_api = MockTelegramApi(chats)

        server_data = ServerData(
            telegram=telegram_api,
            randomizer=MockRandomizer(),
            anonymizer=anonymizer,
            ban_manager=BanManager(ban_file),
            admin_chat_id=0,
        )

        # Admin replies to non-existent message
        await process_incomming_message_simple(
            server_data,
            0,
            0,
            MyTextMessage("Reply to nothing"),
            reply_to_message_id=999,
        )

        # Check that admin received error message
        assert len(chats[0]) == 1
        assert "❌" in chats[0][0][0]
        assert "определить пользователя" in chats[0][0][0]


@pytest.mark.asyncio
async def test_multiple_users_message_flow():
    """Test message flow with multiple users to ensure proper routing"""
    chats = {0: []}

    with TemporaryDirectory() as temp_dir:
        mapping_file = os.path.join(temp_dir, "mapping.bin")
        ban_file = os.path.join(temp_dir, "banned_users.csv")
        encryption_key = Fernet.generate_key()

        anonymizer = await Anonymizer.from_file(mapping_file, encryption_key)
        telegram_api = MockTelegramApi(chats)

        server_data = ServerData(
            telegram=telegram_api,
            randomizer=MockRandomizer(),
            anonymizer=anonymizer,
            ban_manager=BanManager(ban_file),
            admin_chat_id=0,
        )

        # Three users send messages
        await process_incomming_message_simple(
            server_data, 1, 0, MyTextMessage("Message from user 1")
        )
        await process_incomming_message_simple(
            server_data, 2, 0, MyTextMessage("Message from user 2")
        )
        await process_incomming_message_simple(
            server_data, 3, 0, MyTextMessage("Message from user 3")
        )

        # Check all messages forwarded to admin
        assert len(chats[0]) == 3

        # Admin replies to user 2 (message_id = 2)
        await process_incomming_message_simple(
            server_data,
            0,
            0,
            MyTextMessage("Reply to user 2"),
            reply_to_message_id=2,
        )

        # Only user 2 should have received the reply
        assert 1 not in chats
        assert 2 in chats
        assert 3 not in chats
        assert len(chats[2]) == 1
        assert chats[2][0][0] == "Reply to user 2"

        # Admin replies to user 1 (message_id = 1)
        await process_incomming_message_simple(
            server_data,
            0,
            0,
            MyTextMessage("Reply to user 1"),
            reply_to_message_id=1,
        )

        # User 1 should have received the reply
        assert 1 in chats
        assert len(chats[1]) == 1
        assert chats[1][0][0] == "Reply to user 1"


@pytest.mark.asyncio
async def test_user_name_persistence():
    """Test that user names are persisted across messages"""
    chats = {0: []}

    with TemporaryDirectory() as temp_dir:
        mapping_file = os.path.join(temp_dir, "mapping.bin")
        ban_file = os.path.join(temp_dir, "banned_users.csv")
        encryption_key = Fernet.generate_key()

        anonymizer = await Anonymizer.from_file(mapping_file, encryption_key)
        telegram_api = MockTelegramApi(chats)

        server_data = ServerData(
            telegram=telegram_api,
            randomizer=MockRandomizer(),
            anonymizer=anonymizer,
            ban_manager=BanManager(ban_file),
            admin_chat_id=0,
        )

        # User sends first message
        await process_incomming_message_simple(
            server_data, 123, 0, MyTextMessage("First message")
        )

        first_name = chats[0][0][0].split("\n")[0]

        # User sends second message
        await process_incomming_message_simple(
            server_data, 123, 0, MyTextMessage("Second message")
        )

        second_name = chats[0][1][0].split("\n")[0]

        # Names should be the same
        assert first_name == second_name
        assert "Anonymous Alpha" in first_name
