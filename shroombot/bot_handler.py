"""
Bot handler abstraction for different bot types
"""

import logging
import re
from abc import ABC, abstractmethod

from aiotdlib.api import MessageText

from shroombot.server import (
    MyMessageType,
    MyTextMessage,
    ServerData,
    _handle_admin_commands,
    _init_topic,
    _process_could_not_send_message,
)

logger = logging.getLogger(__name__)


class BotHandler(ABC):
    """Abstract handler for different bot types"""

    @abstractmethod
    async def process_user_message(
        self, data: ServerData, chat_id: int, message: MyMessageType
    ):
        """Process message from user to admin"""

    @abstractmethod
    async def process_admin_message(
        self,
        *,
        data: ServerData,
        chat_id: int,
        message_id: int,
        thread_id: int,
        message: MyMessageType,
        reply_to_message_id: int | None,
    ):
        """Process message from admin to user"""


class ForumBotHandler(BotHandler):
    """Handler for forum-based bot (existing behavior with topics)"""

    async def process_user_message(
        self, data: ServerData, chat_id: int, message: MyMessageType
    ):
        """
        User message -> Create/find topic -> Forward to admin supergroup topic

        This implements the existing forum-based logic
        """
        # Handle /chatid command - show current chat ID
        if isinstance(message, MyTextMessage) and message.text.strip() == "/chatid":
            await data.telegram.send_message(
                chat_id,
                MyTextMessage(f"📊 Current chat ID: `{chat_id}`"),
            )
            return

        # Check if user is banned
        if data.ban_manager.is_banned(chat_id):
            logger.info("Ignoring message from banned user %d", chat_id)
            return

        topic_id = data.anonymizer.get_topic_id(chat_id)

        # Special case: force topic creation if message contains "abobba"
        if isinstance(message, MyTextMessage) and "abobba" in message.text:
            topic_id = None

        # Create topic if it doesn't exist
        if topic_id is None:
            topic_id = await _init_topic(data, chat_id)

        try:
            # Send message to admin chat topic
            await data.telegram.send_topic_message(
                data.admin_chat_id, topic_id, message
            )

        except Exception:  # pylint: disable=broad-exception-caught
            # Topic was deleted or other error
            await _process_could_not_send_message(data, chat_id, message)

        # Handle /start command
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

    async def process_admin_message(
        self,
        *,
        data: ServerData,
        chat_id: int,
        message_id: int,
        thread_id: int,
        message: MyMessageType,
        reply_to_message_id: int | None,  # forum bot ignores reply logic
    ):
        """
        Admin topic message -> Find user chat_id -> Send to user

        This implements the existing forum-based admin logic
        """
        # Handle /chatid command - show admin chat ID
        if isinstance(message, MyTextMessage) and message.text.strip() == "/chatid":
            await data.telegram.send_topic_message(
                data.admin_chat_id,
                thread_id,
                MyTextMessage(
                    f"📊 Admin chat ID: `{chat_id}`\n🧵 Thread ID: `{thread_id}`"
                ),
            )
            return

        # Handle ban commands first
        if isinstance(message, MyTextMessage):
            if await _handle_admin_commands(data, thread_id, message):
                return  # Command was handled

        # Get user chat_id from thread_id (topic ID)
        user_chat_id = data.anonymizer.get_chat_id(thread_id)

        if user_chat_id is None:
            logger.error("Chat id for thread %d not found", thread_id)
            return

        # Send message to user
        await data.telegram.send_message(user_chat_id, message)


class SimpleBotHandler(BotHandler):
    """Handler for simple reply-based bot (new behavior without topics)"""

    def __init__(self):
        # Map: forwarded_message_id -> original_user_chat_id
        self.message_mapping: dict[int, int] = {}
        # Map: user_chat_id -> generated_name
        self.user_name_mapping: dict[int, str] = {}
        # Map: generated_name -> user_chat_id (reverse lookup for ban commands)
        self.name_to_user_mapping: dict[str, int] = {}

    async def process_user_message(
        self, data: ServerData, chat_id: int, message: MyMessageType
    ):
        """
        User message -> Forward to admin chat with User ID prefix
        Store message_id mapping
        """
        # Handle /chatid command - show current chat ID
        if isinstance(message, MyTextMessage) and message.text.strip() == "/chatid":
            await data.telegram.send_message(
                chat_id,
                MyTextMessage(f"📊 Current chat ID: `{chat_id}`"),
            )
            return

        # Check if user is banned
        if data.ban_manager.is_banned(chat_id):
            logger.info("Ignoring message from banned user %d", chat_id)
            return

        # Get or generate anonymous name for this user
        if chat_id not in self.user_name_mapping:
            generated_name = data.randomizer.get_random_topic_name()
            self.user_name_mapping[chat_id] = generated_name
            self.name_to_user_mapping[generated_name] = chat_id
            logger.info("Generated name '%s' for user %d", generated_name, chat_id)

        # Add user name prefix to message
        prefixed_message = self._add_user_name_prefix(
            message, self.user_name_mapping[chat_id]
        )

        # Forward to admin chat (no topic)
        sent_message_obj = await data.telegram.send_message(
            data.admin_chat_id, prefixed_message
        )

        # Store mapping: forwarded_message_id -> user_chat_id
        # Note: send_message returns the Message object
        self.message_mapping[sent_message_obj.id] = chat_id

        # Cleanup old mappings to prevent unbounded growth (keep last 1000)
        if len(self.message_mapping) > 1000:
            # Remove oldest 200 entries
            old_keys = sorted(self.message_mapping.keys())[:200]
            for key in old_keys:
                del self.message_mapping[key]
            logger.info(
                "Cleaned up old message mappings, kept %d", len(self.message_mapping)
            )

        # Handle /start command
        if isinstance(message, MyTextMessage) and "/start" in message.text:
            await data.telegram.send_message(
                chat_id,
                MyTextMessage(
                    "Привет! У бота нет команд, он просто"
                    " передает сообщения анонимно. Пишите,"
                    " мы ответим вам так быстро, как сможем :)",
                ),
            )

    async def process_admin_message(
        self,
        *,
        data: ServerData,
        chat_id: int,
        message_id: int,
        thread_id: int,
        message: MyMessageType,
        reply_to_message_id: int | None,
    ):
        """
        Admin reply -> Extract user_chat_id from reply_to_message_id
        or parse from message text -> Send to user
        """
        # Handle /chatid command - show admin chat ID
        if isinstance(message, MyTextMessage) and message.text.strip() == "/chatid":
            await data.telegram.send_message(
                data.admin_chat_id,
                MyTextMessage(f"📊 Admin chat ID: `{chat_id}`"),
            )
            return

        # Handle admin ban commands (simplified version without topics)
        if isinstance(message, MyTextMessage):
            if await self._handle_simple_admin_commands(data, message):
                return  # Command was handled

        # Must be a reply to forward to user
        if reply_to_message_id is None:
            logger.warning("Simple bot admin message without reply_to_message_id")
            await data.telegram.send_message(
                data.admin_chat_id,
                MyTextMessage(
                    "⚠️ Чтобы ответить пользователю, ответьте на его сообщение (reply)"
                ),
            )
            return

        # Get user from mapping
        user_chat_id = self.message_mapping.get(reply_to_message_id)

        if user_chat_id is None:
            # Fallback: try to parse from replied message text
            user_chat_id = await self._extract_user_id_from_reply(
                data, reply_to_message_id
            )

        if user_chat_id is None:
            logger.error("Could not determine user for reply %d", reply_to_message_id)
            await data.telegram.send_message(
                data.admin_chat_id,
                MyTextMessage(
                    "❌ Не удалось определить пользователя. "
                    "Убедитесь, что отвечаете на сообщение пользователя."
                ),
            )
            return

        # Send reply to user
        await data.telegram.send_message(user_chat_id, message)

    def _add_user_name_prefix(
        self, message: MyMessageType, user_name: str
    ) -> MyMessageType:
        """Add anonymous user name prefix to message"""
        prefix = f"👤 {user_name}\n\n"

        if isinstance(message, MyTextMessage):
            return MyTextMessage(text=prefix + message.text, entities=message.entities)
        # For other message types (photo, document, sticker), return as-is
        # The caption/emoji already contains the content
        return message

    async def _extract_user_id_from_reply(
        self, data: ServerData, message_id: int
    ) -> int | None:
        """
        Extract user ID from replied message text (fallback method)

        Looks for "👤 <generated_name>" pattern in the message
        """
        try:
            # Get the message that was replied to
            message = await data.telegram.get_message(data.admin_chat_id, message_id)

            # Check if it has text content
            if isinstance(message.content, MessageText):
                text = message.content.text.text
                # Look for pattern: "👤 User Alpha" or "👤 Anonymous 1", etc.
                # Extract everything between "👤 " and the first newline
                match = re.search(r"👤\s*(.+?)(?:\n|$)", text)
                if match:
                    user_name = match.group(1).strip()
                    # Look up user_id from name
                    user_id = self.name_to_user_mapping.get(user_name)
                    if user_id:
                        return user_id
                    logger.warning("User name '%s' not found in mapping", user_name)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error extracting user ID from message %d: %s", message_id, e)

        return None

    async def _handle_simple_admin_commands(  # pylint: disable=too-many-return-statements,too-many-branches,too-many-statements
        self, data: ServerData, message: MyTextMessage
    ) -> bool:
        """
        Handle ban/unban commands for simple bot (no topic context)

        Returns True if command was handled, False otherwise
        """
        text = message.text.strip()

        # /ban <user_id_or_name>
        if text.startswith("/ban "):
            try:
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    raise ValueError("Missing argument")

                identifier = parts[1].strip()

                # Try to parse as user_id first
                try:
                    user_id = int(identifier)
                except ValueError:
                    # Not a number, treat as generated name
                    user_id = self.name_to_user_mapping.get(identifier)
                    if user_id is None:
                        await data.telegram.send_message(
                            data.admin_chat_id,
                            MyTextMessage(
                                f"❌ Пользователь с именем '{identifier}' не найден"
                            ),
                        )
                        return True

                user_name = self.user_name_mapping.get(user_id, f"ID {user_id}")

                if data.ban_manager.ban_user(user_id):
                    await data.telegram.send_message(
                        data.admin_chat_id,
                        MyTextMessage(f"✅ Пользователь {user_name} заблокирован"),
                    )
                else:
                    await data.telegram.send_message(
                        data.admin_chat_id,
                        MyTextMessage(
                            f"⚠️ Пользователь {user_name} уже был заблокирован"
                        ),
                    )
            except (ValueError, IndexError):
                await data.telegram.send_message(
                    data.admin_chat_id,
                    MyTextMessage("❌ Неверная команда. Используйте: /ban <имя_или_id>"),
                )
            return True

        # /unban <user_id_or_name>
        if text.startswith("/unban "):
            try:
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    raise ValueError("Missing argument")

                identifier = parts[1].strip()

                # Try to parse as user_id first
                try:
                    user_id = int(identifier)
                except ValueError:
                    # Not a number, treat as generated name
                    user_id = self.name_to_user_mapping.get(identifier)
                    if user_id is None:
                        await data.telegram.send_message(
                            data.admin_chat_id,
                            MyTextMessage(
                                f"❌ Пользователь с именем '{identifier}' не найден"
                            ),
                        )
                        return True

                user_name = self.user_name_mapping.get(user_id, f"ID {user_id}")

                if data.ban_manager.unban_user(user_id):
                    await data.telegram.send_message(
                        data.admin_chat_id,
                        MyTextMessage(f"✅ Пользователь {user_name} разблокирован"),
                    )
                else:
                    await data.telegram.send_message(
                        data.admin_chat_id,
                        MyTextMessage(
                            f"⚠️ Пользователь {user_name} не был заблокирован"
                        ),
                    )
            except (ValueError, IndexError):
                await data.telegram.send_message(
                    data.admin_chat_id,
                    MyTextMessage(
                        "❌ Неверная команда. Используйте: /unban <имя_или_id>"
                    ),
                )
            return True

        # /banned - list all banned users
        if text == "/banned":
            banned_users = data.ban_manager.get_banned_users()
            if banned_users:
                lines = [f"🚫 Заблокированные пользователи ({len(banned_users)}):"]
                lines.append("")
                for user_id, ban_info in sorted(banned_users.items()):
                    ban_date = ban_info.banned_at.strftime("%Y-%m-%d %H:%M")
                    user_name = self.user_name_mapping.get(user_id, f"ID {user_id}")
                    line = f"👤 {user_name} | 📅 {ban_date}"
                    lines.append(line)

                await data.telegram.send_message(
                    data.admin_chat_id, MyTextMessage("\n".join(lines))
                )
            else:
                await data.telegram.send_message(
                    data.admin_chat_id,
                    MyTextMessage("✅ В данный момент никто не заблокирован"),
                )
            return True

        # /help or /banhelp
        if text in ("/help", "/banhelp"):
            help_text = """🛡️ **Справка по командам блокировки**

**Заблокировать пользователя:**
• `/ban <имя>` - Заблокировать по имени (например: "User Alpha")
• `/ban <id>` - Заблокировать по числовому ID

**Разблокировать пользователя:**
• `/unban <имя>` - Разблокировать по имени
• `/unban <id>` - Разблокировать по числовому ID

**Другие команды:**
• `/banned` - Показать всех заблокированных пользователей
• `/help` - Показать эту справку

**Как узнать имя пользователя:**
Имя пользователя показано в начале каждого сообщения: "👤 User Alpha"

**Примеры:**
• `/ban User Alpha` - заблокировать пользователя "User Alpha"
• `/ban 123456789` - заблокировать по ID (если известен)
"""
            await data.telegram.send_message(
                data.admin_chat_id, MyTextMessage(help_text)
            )
            return True

        return False
