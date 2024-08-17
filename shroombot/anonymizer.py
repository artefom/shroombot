"""
Class that allows to get thread id based on chat id and vise-versa

stores the data encrypted to disk
"""

import asyncio
import json
import os
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel


def load_encrypted_json_file(file_path: str, encryption_key: bytes) -> dict:
    # Initialize the Fernet cipher with the given key
    cipher = Fernet(encryption_key)

    # Read the encrypted data from the file
    with open(file_path, "rb") as file:
        encrypted_data = file.read()

    # Decrypt the data
    decrypted_data = cipher.decrypt(encrypted_data)

    # Convert the decrypted data (bytes) to string and load as JSON
    json_data = json.loads(decrypted_data.decode("utf-8"))

    return json_data


def save_encrypted_json_file(file_path: str, data: dict, encryption_key: bytes):
    # Initialize the Fernet cipher with the given key
    cipher = Fernet(encryption_key)

    # Convert the dictionary to a JSON string
    json_data = json.dumps(data)

    # Encrypt the JSON string (encode it to bytes first)
    encrypted_data = cipher.encrypt(json_data.encode("utf-8"))

    # Write the encrypted data to the file
    with open(file_path, "wb") as file:
        file.write(encrypted_data)


# Example usage:
# Generate a new encryption key (this should be done once and stored securely)
# encryption_key = Fernet.generate_key()

# Load an encrypted JSON file
# decrypted_data = load_encrypted_json_file('path_to_encrypted_file', encryption_key)

# Save data to an encrypted JSON file
# save_encrypted_json_file('path_to_save_file', decrypted_data, encryption_key)


class MappingItem(BaseModel):
    chat_id: int
    topic_id: int


class EncryptedData(BaseModel):
    mappings: list[MappingItem]


class CouldNotDecrypt(Exception):
    pass


def is_file_empty(file_path: str) -> bool:
    """Check if the file at the given path is empty."""
    # Check if the file exists
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"The file at path '{file_path}' does not exist.")

    # Check if the file is empty
    return os.stat(file_path).st_size == 0


@dataclass
class Anonymizer:
    """
    Maps chat ids (that can be linked to users)
    to topics in a supergroup
    """

    topic_x_chat: dict[int, int]
    chat_x_topic: dict[int, int]
    lock: asyncio.Lock
    file_path: str
    encryption_key: bytes

    @staticmethod
    async def from_file(file_path: str, encryption_key: bytes) -> "Anonymizer":
        topic_x_chat = dict()
        chat_x_topic = dict()

        if os.path.exists(file_path):
            if not is_file_empty(file_path):
                try:
                    data = await asyncio.to_thread(
                        load_encrypted_json_file, file_path, encryption_key
                    )
                except (InvalidToken, ValueError) as exc:
                    raise CouldNotDecrypt() from exc

                data = EncryptedData.model_validate(data)

                for mapping in data.mappings:
                    topic_x_chat[mapping.topic_id] = mapping.chat_id
                    chat_x_topic[mapping.chat_id] = mapping.topic_id

        return Anonymizer(
            topic_x_chat=topic_x_chat,
            chat_x_topic=chat_x_topic,
            lock=asyncio.Lock(),
            file_path=file_path,
            encryption_key=encryption_key,
        )

    def get_topic_id(self, chat_id: int) -> int | None:
        """
        Return topic id based on chat id
        """

        return self.chat_x_topic.get(chat_id)

    async def register_chat_topic_link(self, chat_id: int, topic_id: int):
        assert chat_id not in self.chat_x_topic
        assert topic_id not in self.topic_x_chat

        async with self.lock:
            self.chat_x_topic[chat_id] = topic_id
            self.topic_x_chat[topic_id] = chat_id

            mappings = list()
            for m_chat_id, m_topic_id in self.chat_x_topic.items():
                mappings.append(MappingItem(chat_id=m_chat_id, topic_id=m_topic_id))

            await asyncio.to_thread(
                save_encrypted_json_file,
                self.file_path,
                EncryptedData(mappings=mappings).model_dump(),
                self.encryption_key,
            )

    def get_chat_id(self, topic_id: int) -> int | None:
        """
        Return chat id based on topic id
        """
        return self.topic_x_chat.get(topic_id)
