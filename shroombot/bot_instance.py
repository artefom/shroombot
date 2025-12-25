"""
Bot instance encapsulation - combines Client, ServerData, and Handler
"""

import base64
import logging
from dataclasses import dataclass
from pathlib import Path

from aiotdlib.client import Client

from shroombot.anonymizer import Anonymizer
from shroombot.ban_manager import BanManager
from shroombot.bot_config import BotConfig, BotType
from shroombot.bot_handler import BotHandler, ForumBotHandler, SimpleBotHandler
from shroombot.server import ServerData
from shroombot.shroomgen import (
    GenericNameRandomizer,
    ShroomNameRandomizer,
    default_shroom_names,
)
from shroombot.telegram import LiveTelegramApi

logger = logging.getLogger(__name__)


@dataclass
class BotInstance:
    """Represents a single bot instance with all its components"""

    config: BotConfig
    client: Client
    server_data: ServerData
    handler: BotHandler

    @classmethod
    async def create(cls, config: BotConfig) -> "BotInstance":
        """
        Factory method to create a bot instance from configuration

        Args:
            config: Bot configuration

        Returns:
            Initialized BotInstance
        """
        logger.info(
            "Creating bot instance: %s (type: %s)", config.bot_id, config.bot_type
        )

        # Determine files directory
        files_dir = config.files_dir
        if files_dir is None:
            files_dir = f"/tmp/bot_{config.bot_id}_files"
            logger.info("No files_dir specified, using default: %s", files_dir)

        # Create aiotdlib Client
        client = Client(
            api_id=config.api_id,
            api_hash=config.api_hash,
            bot_token=config.bot_token,
            files_directory=Path(files_dir),
        )

        # Create anonymizer with encryption
        encryption_key = base64.b64decode(config.encryption_key)
        anonymizer = await Anonymizer.from_file(config.mapping_file, encryption_key)

        # Create ban manager
        ban_manager = BanManager(config.ban_file)

        # Create name randomizer based on type
        if config.name_type == "mushroom":
            randomizer = ShroomNameRandomizer(default_shroom_names())
        else:  # generic
            randomizer = GenericNameRandomizer()

        # Create ServerData
        server_data = ServerData(
            telegram=LiveTelegramApi(client),
            anonymizer=anonymizer,
            randomizer=randomizer,
            ban_manager=ban_manager,
            admin_chat_id=config.admin_chat_id,
        )

        # Create handler based on bot type
        if config.bot_type == BotType.FORUM:
            handler = ForumBotHandler()
        elif config.bot_type == BotType.SIMPLE:
            handler = SimpleBotHandler()
        else:
            raise NotImplementedError("Unexpected bot type")

        logger.info("Bot instance created successfully: %s", config.bot_id)

        return cls(
            config=config,
            client=client,
            server_data=server_data,
            handler=handler,
        )

    async def start(self):
        """Start the bot client (enter async context manager)"""
        logger.info("Starting bot instance: %s", self.config.bot_id)

        # pylint: disable=unnecessary-dunder-call
        await self.client.__aenter__()

    async def stop(self):
        """Stop the bot client (exit async context manager)"""
        logger.info("Stopping bot instance: %s", self.config.bot_id)
        await self.client.__aexit__(None, None, None)
