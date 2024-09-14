"""
Implementation of the core logic
"""


import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from aiotdlib.api import TextEntity

from shroombot.anonymizer import Anonymizer

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
    Stores objects used by se¬rver
    """

    telegram: TelegramApi
    anonymizer: Anonymizer
    randomizer: NameRandomizer
    admin_chat_id: int


async def _process_admin_message(
    data: ServerData, thread_id: int, message: MyMessageType
):
    """
    Function that handles messages sent by admins
    """
    chat_id = data.anonymizer.get_chat_id(thread_id)

    # Chat id must already be known if admin replies to a message
    if chat_id is None:
        logger.error("Chat id for thread %d not found", thread_id)
        return

    await data.telegram.send_message(chat_id, message)


async def _process_user_message(data: ServerData, chat_id: int, message: MyMessageType):
    """
    Function that handles messages sent by users
    """
    topic_id = data.anonymizer.get_topic_id(chat_id)

    if topic_id is None:
        topic_id = await data.telegram.create_topic(
            data.admin_chat_id, data.randomizer.get_random_topic_name()
        )

        await data.anonymizer.register_chat_topic_link(chat_id, topic_id)

    await data.telegram.send_topic_message(data.admin_chat_id, topic_id, message)

    if isinstance(message, MyTextMessage):
        if "/start" in message.text:
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
