"""
Bot handler abstraction for different bot types
"""

import logging

from shroombot.server import MyMessageType, MyTextMessage, ServerData

logger = logging.getLogger(__name__)


async def _process_user_message(data: ServerData, chat_id: int, message: MyMessageType):
    """
    User message -> Forward to admin chat with User ID prefix
    Store message_id mapping
    """

    # Check if user is banned
    if data.ban_manager.is_banned(chat_id):
        logger.info("Ignoring message from banned user %d", chat_id)
        return

    # Get or generate anonymous name for this user
    user_name = data.anonymizer.get_user_name(chat_id)

    if user_name is None:
        user_name = data.randomizer.get_random_topic_name()
        await data.anonymizer.register_chat_user_name_link(chat_id, user_name)

    # Add user name prefix to message
    prefixed_message = _add_user_name_prefix(message, user_name)

    # Forward to admin chat (no topic)
    sent_message_id = await data.telegram.send_message(
        data.admin_chat_id, prefixed_message
    )

    # Store mapping: forwarded_message_id -> user_chat_id
    # Note: send_message returns the Message object
    await data.anonymizer.register_chat_topic_link(chat_id, sent_message_id)

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


async def _process_admin_message(  # pylint: disable=too-many-branches
    data: ServerData,
    chat_id: int,
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
    user_chat_id = data.anonymizer.get_chat_id(reply_to_message_id)

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

    # Handle ban/unban commands as reply (without arguments)
    if isinstance(message, MyTextMessage) and message.text.strip() in (
        "/ban",
        "/unban",
    ):
        await _handle_ban_cmd(data, user_chat_id, message.text)

    # Send reply to user
    await data.telegram.send_message(user_chat_id, message)


def _add_user_name_prefix(message: MyMessageType, user_name: str) -> MyMessageType:
    """Add anonymous user name prefix to message"""
    prefix = f"👤 {user_name}\n\n"

    if isinstance(message, MyTextMessage):
        return MyTextMessage(text=prefix + message.text, entities=message.entities)
    # For other message types (photo, document, sticker), return as-is
    # The caption/emoji already contains the content
    return message


async def _handle_ban_cmd(data: ServerData, user_chat_id: int, cmd: str):
    cmd = cmd.strip()

    user_name = data.anonymizer.get_user_name(user_chat_id) or f"ID {user_chat_id}"

    if cmd == "/ban":
        if data.ban_manager.ban_user(user_chat_id):
            await data.telegram.send_message(
                data.admin_chat_id,
                MyTextMessage(f"✅ Пользователь {user_name} заблокирован"),
            )
        else:
            await data.telegram.send_message(
                data.admin_chat_id,
                MyTextMessage(f"⚠️ Пользователь {user_name} уже был заблокирован"),
            )

    if cmd == "/unban":
        if data.ban_manager.unban_user(user_chat_id):
            await data.telegram.send_message(
                data.admin_chat_id,
                MyTextMessage(f"✅ Пользователь {user_name} разблокирован"),
            )
        else:
            await data.telegram.send_message(
                data.admin_chat_id,
                MyTextMessage(f"⚠️ Пользователь {user_name} не был заблокирован"),
            )


async def process_incomming_message_simple(
    data: ServerData,
    chat_id: int,
    thread_id: int,
    message: MyMessageType,
    reply_to_message_id: int | None = None,
):
    try:
        if chat_id == data.admin_chat_id:
            await _process_admin_message(data, thread_id, message, reply_to_message_id)
        else:
            await _process_user_message(data, chat_id, message)
    except Exception:
        logger.exception("Error during processing incomming message")
        raise
