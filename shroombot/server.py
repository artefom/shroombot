"""
Implementation of the core logic
"""


import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from aiotdlib.api import TextEntity

from shroombot.anonymizer import Anonymizer
from shroombot.ban_manager import BanManager

logger = logging.getLogger(__name__)


@dataclass
class MyTextMessage:
    text: str
    entities: list[TextEntity] = field(default_factory=list)


@dataclass
class MyPhotoMessage:
    id: str
    caption: str | None


@dataclass
class MyStickerMessage:
    id: str
    emoji: str


@dataclass
class MyDocumentMessage:
    id: str
    caption: str | None


MyMessageType = MyTextMessage | MyPhotoMessage | MyDocumentMessage | MyStickerMessage


class TelegramApi(ABC):
    """
    Representation of the telegram API
    that is mocked during tests and used live during deployment
    """

    @abstractmethod
    async def send_message(
        self,
        chat_id: int,
        message: MyMessageType,
    ):
        """
        Send message to specific chat and thread
        """
        ...

    @abstractmethod
    async def send_topic_message(
        self,
        chat_id: int,
        topic_id: int,
        message: MyMessageType,
    ):
        """
        Send message to specific chat and thread
        """
        ...

    @abstractmethod
    async def create_topic(self, chat_id: int, title: str) -> int:
        """
        Creates topic in a chat.

        Returns topic id
        """
        ...


class NameRandomizer(ABC):
    @abstractmethod
    def get_random_topic_name(self) -> str:
        ...


@dataclass
class ServerData:
    """
    Stores objects used by server
    """

    telegram: TelegramApi
    anonymizer: Anonymizer
    randomizer: NameRandomizer
    ban_manager: BanManager
    admin_chat_id: int


async def _process_admin_message(
    data: ServerData, thread_id: int, message: MyMessageType
):
    """
    Function that handles messages sent by admins
    """
    # Handle ban commands first
    if isinstance(message, MyTextMessage):
        if await _handle_admin_commands(data, thread_id, message):
            return

    chat_id = data.anonymizer.get_chat_id(thread_id)

    # Chat id must already be known if admin replies to a message
    if chat_id is None:
        logger.error("Chat id for thread %d not found", thread_id)
        return

    await data.telegram.send_message(chat_id, message)


async def _handle_ban_command(data: ServerData, thread_id: int, text: str) -> bool:
    """Handle /ban command with user ID"""
    try:
        user_id = int(text.split()[1])
        if data.ban_manager.ban_user(user_id):
            await data.telegram.send_topic_message(
                data.admin_chat_id,
                thread_id,
                MyTextMessage(f"✅ User {user_id} has been banned"),
            )
        else:
            await data.telegram.send_topic_message(
                data.admin_chat_id,
                thread_id,
                MyTextMessage(f"⚠️ User {user_id} was already banned"),
            )
    except (ValueError, IndexError):
        await data.telegram.send_topic_message(
            data.admin_chat_id,
            thread_id,
            MyTextMessage(
                "❌ Invalid command. Use: /ban <user_id> or reply to a message with /ban"
            ),
        )
    return True


async def _handle_ban_reply(data: ServerData, thread_id: int) -> bool:
    """Handle /ban command by replying to a message"""
    chat_id = data.anonymizer.get_chat_id(thread_id)
    if chat_id is not None:
        if data.ban_manager.ban_user(chat_id):
            await data.telegram.send_topic_message(
                data.admin_chat_id,
                thread_id,
                MyTextMessage(f"✅ User {chat_id} has been banned"),
            )
        else:
            await data.telegram.send_topic_message(
                data.admin_chat_id,
                thread_id,
                MyTextMessage(f"⚠️ User {chat_id} was already banned"),
            )
    else:
        await data.telegram.send_topic_message(
            data.admin_chat_id,
            thread_id,
            MyTextMessage(
                "❌ Could not determine user ID. Reply to a user's message with /ban"
            ),
        )
    return True


async def _handle_unban_command(data: ServerData, thread_id: int, text: str) -> bool:
    """Handle /unban command with user ID"""
    try:
        user_id = int(text.split()[1])
        if data.ban_manager.unban_user(user_id):
            await data.telegram.send_topic_message(
                data.admin_chat_id,
                thread_id,
                MyTextMessage(f"✅ User {user_id} has been unbanned"),
            )
        else:
            await data.telegram.send_topic_message(
                data.admin_chat_id,
                thread_id,
                MyTextMessage(f"⚠️ User {user_id} was not banned"),
            )
    except (ValueError, IndexError):
        await data.telegram.send_topic_message(
            data.admin_chat_id,
            thread_id,
            MyTextMessage(
                "❌ Invalid command. Use: /unban <user_id>"
                " or reply to a message with /unban"
            ),
        )
    return True


async def _handle_unban_reply(data: ServerData, thread_id: int) -> bool:
    """Handle /unban command by replying to a message"""
    chat_id = data.anonymizer.get_chat_id(thread_id)
    if chat_id is not None:
        if data.ban_manager.unban_user(chat_id):
            await data.telegram.send_topic_message(
                data.admin_chat_id,
                thread_id,
                MyTextMessage(f"✅ User {chat_id} has been unbanned"),
            )
        else:
            await data.telegram.send_topic_message(
                data.admin_chat_id,
                thread_id,
                MyTextMessage(f"⚠️ User {chat_id} was not banned"),
            )
    else:
        await data.telegram.send_topic_message(
            data.admin_chat_id,
            thread_id,
            MyTextMessage(
                "❌ Could not determine user ID. Reply to a user's message with /unban"
            ),
        )
    return True


async def _handle_banned_command(data: ServerData, thread_id: int) -> bool:
    """Handle /banned command"""
    banned_users = data.ban_manager.get_banned_users()
    if banned_users:
        banned_list = ", ".join(map(str, sorted(banned_users)))
        await data.telegram.send_topic_message(
            data.admin_chat_id,
            thread_id,
            MyTextMessage(f"🚫 Banned users ({len(banned_users)}): {banned_list}"),
        )
    else:
        await data.telegram.send_topic_message(
            data.admin_chat_id,
            thread_id,
            MyTextMessage("✅ No users are currently banned"),
        )
    return True


async def _handle_help_command(data: ServerData, thread_id: int) -> bool:
    """Handle /help command"""
    help_text = """🛡️ **Ban Commands Help**

**Ban a user:**
• `/ban <user_id>` - Ban by user ID
• `/ban` - Reply to a user's message with this command

**Unban a user:**
• `/unban <user_id>` - Unban by user ID
• `/unban` - Reply to a user's message with this command

**Other commands:**
• `/banned` - List all banned users
• `/help` - Show this help

**How to get User ID:**
1. When a user sends a message, their ID is shown in the topic title
2. Reply to their message with `/ban` or `/unban`
3. Use `/ban <user_id>` if you know the ID

**Example:**
Reply to a spam message with `/ban` to ban that user instantly!"""

    await data.telegram.send_topic_message(
        data.admin_chat_id, thread_id, MyTextMessage(help_text)
    )
    return True


# pylint: disable=too-many-return-statements
async def _handle_admin_commands(
    data: ServerData, thread_id: int, message: MyTextMessage
) -> bool:
    """
    Handle admin commands like /ban, /unban, /banned, /help

    Returns:
        bool: True if command was handled, False otherwise
    """
    text = message.text.strip()

    if text.startswith("/ban "):
        return await _handle_ban_command(data, thread_id, text)
    if text == "/ban":
        return await _handle_ban_reply(data, thread_id)
    if text.startswith("/unban "):
        return await _handle_unban_command(data, thread_id, text)
    if text == "/unban":
        return await _handle_unban_reply(data, thread_id)
    if text == "/banned":
        return await _handle_banned_command(data, thread_id)
    if text in ("/help", "/banhelp"):
        return await _handle_help_command(data, thread_id)

    return False


async def _init_topic(data: ServerData, chat_id: int) -> int:
    topic_id = await data.telegram.create_topic(
        data.admin_chat_id, data.randomizer.get_random_topic_name()
    )

    await data.anonymizer.register_chat_topic_link(chat_id, topic_id)

    return topic_id


async def _process_could_not_send_message(
    data: ServerData, chat_id: int, message: MyMessageType
):
    topic_id = await _init_topic(data, chat_id)

    await data.telegram.send_message(
        chat_id,
        MyTextMessage(
            "Кажется что-то пошло не так и ваши новые сообщения будут"
            " отображаться как от нового пользователя у админов грибницы",
        ),
    )

    await data.telegram.send_topic_message(
        data.admin_chat_id,
        topic_id,
        MyTextMessage(
            "Не получилось послать сообщение в старый топик, поэтому мы создали новый"
            " и посылаем новые сообщения юзера сюда"
        ),
    )

    await data.telegram.send_topic_message(data.admin_chat_id, topic_id, message)


async def _process_user_message(data: ServerData, chat_id: int, message: MyMessageType):
    """
    Function that handles messages sent by users
    """
    # Check if user is banned - if so, ignore their messages
    if data.ban_manager.is_banned(chat_id):
        logger.info("Ignoring message from banned user %d", chat_id)
        return

    topic_id = data.anonymizer.get_topic_id(chat_id)

    if isinstance(message, MyTextMessage) and "abobba" in message.text:
        topic_id = None

    if topic_id is None:
        topic_id = await _init_topic(data, chat_id)

    try:
        await data.telegram.send_topic_message(data.admin_chat_id, topic_id, message)

    # The topic was deleted?
    except Exception:  # pylint: disable=broad-exception-caught
        await _process_could_not_send_message(data, chat_id, message)

    if isinstance(message, MyTextMessage) and "/start" in message.text:
        await data.telegram.send_message(
            chat_id,
            MyTextMessage(
                "Привет! У бота нет команд, он просто"
                " передает сообщения анонимно. Пишите,"
                " мы ответим вам так быстро, как сможем :)",
            ),
        )

        await data.telegram.send_topic_message(
            data.admin_chat_id,
            topic_id,
            MyTextMessage("Приветственное сообщение показано"),
        )


async def process_incomming_message(
    data: ServerData, chat_id: int, thread_id: int, message: MyMessageType
):
    try:
        if chat_id == data.admin_chat_id:
            await _process_admin_message(data, thread_id, message)
        else:
            await _process_user_message(data, chat_id, message)
    except Exception:
        logger.exception("Error during processing incomming message")
        raise
