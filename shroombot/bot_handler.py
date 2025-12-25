"""
Bot handler abstraction for different bot types
"""

import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from aiotdlib.api import MessageText

from shroombot.server import (
    MyMessageType,
    MyTextMessage,
    ServerData,
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


class SimpleBotHandler(BotHandler):
    """Handler for simple reply-based bot (new behavior without topics)"""

    def __init__(self):
        # Persistent name storage (if provided)
        self.name_store: Any = NotImplemented

    @property
    def message_mapping(self) -> dict[int, int]:
        return self.name_store.message_mapping

    def _get_user_name(self, user_chat_id: int) -> str | None:
        return self.name_store.get_name(user_chat_id)

    def _get_user_id_by_name(self, name: str) -> int | None:
        return self.name_store.get_user_id(name)

    def _save_name_mapping(self, user_chat_id: int, name: str):
        self.name_store.save_mapping(user_chat_id, name)

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
        user_name = self._get_user_name(chat_id)
        if user_name is None:
            generated_name = data.randomizer.get_random_topic_name()
            self._save_name_mapping(chat_id, generated_name)
            logger.info("Generated name '%s' for user %d", generated_name, chat_id)
            user_name = generated_name

        # Add user name prefix to message
        prefixed_message = self._add_user_name_prefix(message, user_name)

        # Forward to admin chat (no topic)
        sent_message_obj = await data.telegram.send_message(
            data.admin_chat_id, prefixed_message
        )

        # Store mapping: forwarded_message_id -> user_chat_id
        # Note: send_message returns the Message object
        self.name_store.save_message_mapping(sent_message_obj.id, chat_id)

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

    async def process_admin_message(  # pylint: disable=too-many-branches
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

        # Handle ban/unban commands as reply (without arguments)
        if isinstance(message, MyTextMessage):
            cmd = message.text.strip()
            if cmd in ("/ban", "/unban") and reply_to_message_id:
                # Ban/unban by replying to user's message
                user_chat_id = self.message_mapping.get(reply_to_message_id)

                if user_chat_id is None:
                    # Fallback: try to parse from replied message text
                    user_chat_id = await self._extract_user_id_from_reply(
                        data, reply_to_message_id
                    )

                if user_chat_id is None:
                    await data.telegram.send_message(
                        data.admin_chat_id,
                        MyTextMessage(
                            "❌ Не удалось определить пользователя. "
                            "Убедитесь, что отвечаете на сообщение пользователя."
                        ),
                    )
                    return

                user_name = self._get_user_name(user_chat_id) or f"ID {user_chat_id}"

                if cmd == "/ban":
                    if data.ban_manager.ban_user(user_chat_id):
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
                else:  # /unban
                    if data.ban_manager.unban_user(user_chat_id):
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
                return

        # Handle admin ban commands (with arguments: /ban <name_or_id>)
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
                    user_id = self._get_user_id_by_name(user_name)
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
                    user_id = self._get_user_id_by_name(identifier)
                    if user_id is None:
                        await data.telegram.send_message(
                            data.admin_chat_id,
                            MyTextMessage(
                                f"❌ Пользователь с именем '{identifier}' не найден"
                            ),
                        )
                        return True

                user_name = self._get_user_name(user_id) or f"ID {user_id}"

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
                    user_id = self._get_user_id_by_name(identifier)
                    if user_id is None:
                        await data.telegram.send_message(
                            data.admin_chat_id,
                            MyTextMessage(
                                f"❌ Пользователь с именем '{identifier}' не найден"
                            ),
                        )
                        return True

                user_name = self._get_user_name(user_id) or f"ID {user_id}"

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
                    user_name = self._get_user_name(user_id) or f"ID {user_id}"
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
• Ответьте на сообщение пользователя командой `/ban` (рекомендуется)
• `/ban <имя>` - Заблокировать по имени (например: "User Alpha")
• `/ban <id>` - Заблокировать по числовому ID

**Разблокировать пользователя:**
• Ответьте на сообщение пользователя командой `/unban`
• `/unban <имя>` - Разблокировать по имени
• `/unban <id>` - Разблокировать по числовому ID

**Другие команды:**
• `/banned` - Показать всех заблокированных пользователей
• `/help` - Показать эту справку

**Как узнать имя пользователя:**
Имя пользователя показано в начале каждого сообщения: "👤 User Alpha"

**Примеры:**
• Ответьте (reply) на сообщение пользователя и напишите `/ban`
• `/ban User Alpha` - заблокировать пользователя "User Alpha"
• `/ban 123456789` - заблокировать по ID (если известен)
"""
            await data.telegram.send_message(
                data.admin_chat_id, MyTextMessage(help_text)
            )
            return True

        return False
