"""
Connection to the telegram service
"""

from aiotdlib.api import (
    FormattedText,
    ForumTopicIcon,
    InputFileRemote,
    InputMessageDocument,
    InputMessagePhoto,
    InputMessageText,
    TextEntity,
)
from aiotdlib.client import Client

from shroombot.server import (
    MyDocumentMessage,
    MyMessageType,
    MyPhotoMessage,
    MyTextMessage,
    TelegramApi,
)


async def get_chat_id(client: Client, username: str) -> int:
    chat = await client.api.search_public_chat(username)
    return chat.id


def _as_fmt(text: str, entities: list[TextEntity]) -> FormattedText:
    return FormattedText(
        text=text, entities=entities
    )  # pyright: ignore[reportCallIssue]


def _as_maybe_fmt(text: str | None) -> FormattedText | None:
    if text is None:
        return None
    return FormattedText(text=text, entities=[])  # pyright: ignore[reportCallIssue]


def message_to_content(  # pylint: disable=inconsistent-return-statements
    message: MyMessageType,
) -> InputMessageText | InputMessagePhoto | InputMessageDocument:
    if isinstance(message, MyTextMessage):
        return InputMessageText(
            text=_as_fmt(message.text, message.entities)
        )  # pyright: ignore[reportCallIssue]

    if isinstance(message, MyPhotoMessage):
        return InputMessagePhoto(
            photo=InputFileRemote(id=message.id),  # pyright: ignore[reportCallIssue]
            width=40,
            height=40,
            added_sticker_file_ids=[],
            caption=_as_maybe_fmt(message.caption),
        )  # pyright: ignore[reportCallIssue]

    if isinstance(message, MyDocumentMessage):
        return InputMessageDocument(
            document=InputFileRemote(id=message.id),  # pyright: ignore[reportCallIssue]
            disable_content_type_detection=True,
            caption=_as_maybe_fmt(message.caption),
        )  # pyright: ignore[reportCallIssue]


class LiveTelegramApi(TelegramApi):
    def __init__(self, client: Client):
        self.client = client

    async def send_message(
        self,
        chat_id: int,
        message: MyMessageType,
    ):
        """
        Send message to specific chat and thread
        """

        await self.client.api.send_message(
            chat_id,
            message_to_content(message),
        )

    async def send_topic_message(
        self,
        chat_id: int,
        topic_id: int,
        message: MyMessageType,
    ):
        """
        Send message to specific chat and thread
        """
        await self.client.api.send_message(
            chat_id,
            message_to_content(message),
            message_thread_id=topic_id,
        )

    async def create_topic(self, chat_id: int, title: str) -> int:
        """
        Creates topic in a chat.

        Returns topic id
        """

        icon = ForumTopicIcon(color=0)  # pyright: ignore[reportCallIssue]

        topic_info = await self.client.api.create_forum_topic(chat_id, title, icon)

        return int(topic_info.message_thread_id)
