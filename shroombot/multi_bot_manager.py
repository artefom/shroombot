"""
Multi-bot manager for orchestrating multiple bot instances
"""

import logging

from aiotdlib.api import (
    MessageBasicGroupChatCreate,
    MessageChatAddMembers,
    MessageChatUpgradeFrom,
    MessageChatUpgradeTo,
    MessageContent,
    MessageDocument,
    MessageForumTopicCreated,
    MessageForumTopicIsHiddenToggled,
    MessagePhoto,
    MessageReplyToMessage,
    MessageSticker,
    MessageText,
    UpdateNewMessage,
)
from aiotdlib.api.api import API

from shroombot.bot_config import MultiBotConfig
from shroombot.bot_instance import BotInstance
from shroombot.server import (
    MyDocumentMessage,
    MyMessageType,
    MyPhotoMessage,
    MyStickerMessage,
    MyTextMessage,
)

logger = logging.getLogger(__name__)


class MultiBotManager:
    """Manages multiple bot instances running concurrently"""

    def __init__(self, config: MultiBotConfig):
        self.config = config
        self.bot_instances: list[BotInstance] = []

    async def initialize(self):
        """Create all bot instances from configuration"""
        logger.info("Initializing %d bot(s)", len(self.config.bots))

        for bot_config in self.config.bots:
            try:
                instance = await BotInstance.create(bot_config)
                self.bot_instances.append(instance)
                logger.info(
                    "Initialized bot: %s (type: %s)",
                    bot_config.bot_id,
                    bot_config.bot_type,
                )
            except Exception as e:
                logger.error("Failed to initialize bot %s: %s", bot_config.bot_id, e)
                raise

        logger.info("All bots initialized successfully")

    async def start_all(self):
        """Start all bot clients and register message handlers"""
        for instance in self.bot_instances:
            await instance.start()
            self._register_message_handler(instance)
            logger.info("Started bot: %s", instance.config.bot_id)

    async def stop_all(self):
        """Start all bot clients and register message handlers"""
        for instance in self.bot_instances:
            await instance.stop()
            logger.info("Stopped bot: %s", instance.config.bot_id)

    def _register_message_handler(self, instance: BotInstance):
        """
        Register message handler for a bot instance

        Each bot gets its own message handler that routes messages
        through its specific handler (ForumBotHandler or SimpleBotHandler)
        """

        async def message_handler(_, update: UpdateNewMessage):
            try:
                message = update.message

                # Convert message content to internal format
                content = self._convert_message_content(message.content)

                if content is None:
                    # Unsupported or ignored message type
                    return

                # Determine if message is from admin or user
                is_admin_message = message.chat_id == instance.server_data.admin_chat_id

                if is_admin_message:
                    reply_to_message_id: int | None = None
                    if isinstance(message.reply_to, MessageReplyToMessage):
                        reply_to_message_id = message.reply_to.message_id

                    # Admin message -> route to user
                    await instance.handler.process_admin_message(
                        data=instance.server_data,
                        chat_id=message.chat_id,
                        message_id=message.id,
                        thread_id=message.message_thread_id,
                        message=content,
                        reply_to_message_id=reply_to_message_id,
                    )
                else:
                    # User message -> route to admin
                    await instance.handler.process_user_message(
                        instance.server_data, message.chat_id, content
                    )

            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception(
                    "Error in message handler for bot %s", instance.config.bot_id
                )

        # Register the handler for UPDATE_NEW_MESSAGE events
        instance.client.add_event_handler(message_handler, API.Types.UPDATE_NEW_MESSAGE)

    def _convert_message_content(self, content: MessageContent) -> MyMessageType | None:
        """
        Convert Telegram message content to internal format

        Returns None for unsupported or ignored message types
        """
        # Ignore forum topic management messages
        if isinstance(
            content,
            (
                MessageForumTopicCreated,
                MessageForumTopicIsHiddenToggled,
                MessageChatUpgradeFrom,
                MessageChatAddMembers,
                MessageBasicGroupChatCreate,
                MessageChatUpgradeTo,
            ),
        ):
            return None

        msg: MyMessageType | None = None

        # Text messages
        if isinstance(content, MessageText):
            msg = MyTextMessage(text=content.text.text, entities=content.text.entities)

        # Document messages
        if isinstance(content, MessageDocument):
            msg = MyDocumentMessage(
                id=content.document.document.remote.id, caption=content.caption.text
            )

        # Photo messages
        if isinstance(content, MessagePhoto):
            msg = MyPhotoMessage(
                id=content.photo.sizes[0].photo.remote.id, caption=content.caption.text
            )

        # Sticker messages
        if isinstance(content, MessageSticker):
            msg = MyStickerMessage(
                id=content.sticker.sticker.remote.id, emoji=content.sticker.emoji
            )

        # Unsupported type - log warning
        if msg is None:
            logger.warning("Unsupported message type: %s", content.__class__.__name__)

        return msg
