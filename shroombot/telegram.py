"""
Connection to the telegram service
"""

from aiotdlib import Client
from aiotdlib.api import FormattedText, ForumTopicIcon, InputMessageText

from shroombot.server import TelegramApi


async def get_chat_id(client: Client, username: str) -> int:
    chat = await client.api.search_public_chat(username)
    return chat.id


class LiveTelegramApi(TelegramApi):
    def __init__(self, client: Client):
        self.client = client

    async def send_message(
        self,
        chat_id: int,
        text: str,
    ):
        """
        Send message to specific chat and thread
        """
        content = InputMessageText(
            text=FormattedText(
                text=text,
                entities=[],
            )  # pyright: ignore[reportCallIssue]
        )
        await self.client.api.send_message(
            chat_id,
            content,
        )

    async def send_topic_message(
        self,
        chat_id: int,
        topic_id: int,
        text: str,
    ):
        """
        Send message to specific chat and thread
        """
        content = InputMessageText(
            text=FormattedText(
                text=text,
                entities=[],
            )  # pyright: ignore[reportCallIssue]
        )
        await self.client.api.send_message(
            chat_id,
            content,
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
