"""
Implementation of the core logic
"""


import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from aiotdlib.api import Message, TextEntity

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
    ) -> Message:
        """
        Send message to specific chat and thread

        Returns the sent message object
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

    @abstractmethod
    async def get_message(self, chat_id: int, message_id: int) -> Message:
        """
        Get message by ID

        Returns message object
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
        if data.ban_manager.ban_user(user_id, thread_id):
            await data.telegram.send_topic_message(
                data.admin_chat_id,
                thread_id,
                MyTextMessage(
                    f"✅ Пользователь заблокирован\n📱 "
                    f"User ID: {user_id}\n🧵 Thread ID: {thread_id}"
                ),
            )
        else:
            await data.telegram.send_topic_message(
                data.admin_chat_id,
                thread_id,
                MyTextMessage(f"⚠️ Пользователь {user_id} уже был заблокирован"),
            )
    except (ValueError, IndexError):
        await data.telegram.send_topic_message(
            data.admin_chat_id,
            thread_id,
            MyTextMessage(
                "❌ Неверная команда. Используйте: /ban "
                "<user_id> или ответьте на сообщение с /ban"
            ),
        )
    return True


async def _handle_ban_reply(data: ServerData, thread_id: int) -> bool:
    """Handle /ban command by replying to a message"""
    chat_id = data.anonymizer.get_chat_id(thread_id)
    if chat_id is not None:
        if data.ban_manager.ban_user(chat_id, thread_id):
            await data.telegram.send_topic_message(
                data.admin_chat_id,
                thread_id,
                MyTextMessage(
                    f"✅ Пользователь заблокирован\n📱"
                    f" User ID: {chat_id}\n🧵 Thread ID: {thread_id}"
                ),
            )
        else:
            await data.telegram.send_topic_message(
                data.admin_chat_id,
                thread_id,
                MyTextMessage(f"⚠️ Пользователь {chat_id} уже был заблокирован"),
            )
    else:
        await data.telegram.send_topic_message(
            data.admin_chat_id,
            thread_id,
            MyTextMessage(
                "❌ Не удалось определить ID пользователя."
                " Ответьте на сообщение пользователя с /ban"
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
                MyTextMessage(f"✅ Пользователь {user_id} разблокирован"),
            )
        else:
            await data.telegram.send_topic_message(
                data.admin_chat_id,
                thread_id,
                MyTextMessage(f"⚠️ Пользователь {user_id} не был заблокирован"),
            )
    except (ValueError, IndexError):
        await data.telegram.send_topic_message(
            data.admin_chat_id,
            thread_id,
            MyTextMessage(
                "❌ Неверная команда. Используйте:"
                " /unban <user_id> или ответьте на сообщение с /unban"
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
                MyTextMessage(f"✅ Пользователь {chat_id} разблокирован"),
            )
        else:
            await data.telegram.send_topic_message(
                data.admin_chat_id,
                thread_id,
                MyTextMessage(f"⚠️ Пользователь {chat_id} не был заблокирован"),
            )
    else:
        await data.telegram.send_topic_message(
            data.admin_chat_id,
            thread_id,
            MyTextMessage(
                "❌ Не удалось определить ID пользователя."
                " Ответьте на сообщение пользователя с /unban"
            ),
        )
    return True


async def _handle_banned_command(data: ServerData, thread_id: int) -> bool:
    """Handle /banned command"""
    banned_users = data.ban_manager.get_banned_users()
    if banned_users:
        lines = [f"🚫 Заблокированные пользователи ({len(banned_users)}):"]
        lines.append("")

        for user_id, ban_info in sorted(banned_users.items()):
            # Format: User ID | Ban date | Thread ID (if available)
            ban_date = ban_info.banned_at.strftime("%Y-%m-%d %H:%M")
            line = f"📱 {user_id} | 📅 {ban_date}"
            if ban_info.thread_id:
                line += f" | 🧵 {ban_info.thread_id}"
            lines.append(line)

        await data.telegram.send_topic_message(
            data.admin_chat_id,
            thread_id,
            MyTextMessage("\n".join(lines)),
        )
    else:
        await data.telegram.send_topic_message(
            data.admin_chat_id,
            thread_id,
            MyTextMessage("✅ В данный момент никто не заблокирован"),
        )
    return True


async def _handle_help_command(data: ServerData, thread_id: int) -> bool:
    """Handle /help command"""
    help_text = """🛡️ **Справка по командам блокировки**

**Заблокировать пользователя:**
• `/ban <user_id>` - Заблокировать по ID пользователя
• `/ban` - Ответить на сообщение пользователя этой командой

**Разблокировать пользователя:**
• `/unban <user_id>` - Разблокировать по ID пользователя
• `/unban` - Ответить на сообщение пользователя этой командой

**Другие команды:**
• `/banned` - Показать всех заблокированных пользователей
• `/help` - Показать эту справку

**Как получить ID пользователя:**
1. Ответьте на его сообщение командой `/ban` или `/unban`
2. Используйте `/ban <user_id>` если знаете ID

**Пример:**
Ответьте на спам-сообщение командой `/ban`
чтобы мгновенно заблокировать этого пользователя!
"""

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
