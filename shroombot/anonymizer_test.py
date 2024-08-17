"""
Testing if anonymizer correctly works and loads/saves data from/to disk
"""

import os
from tempfile import TemporaryDirectory

import pytest
from cryptography.fernet import Fernet

from shroombot.anonymizer import Anonymizer, CouldNotDecrypt


@pytest.mark.asyncio
async def test_anonymizer():
    encryption_key = Fernet.generate_key()
    encryption_key_false = Fernet.generate_key()

    with TemporaryDirectory() as temp_dir:
        file_path = os.path.join(temp_dir, "test.bin")

        anonymizer = await Anonymizer.from_file(file_path, encryption_key)

        assert anonymizer.get_chat_id(2) is None
        assert anonymizer.get_topic_id(1) is None
        assert anonymizer.get_chat_id(4) is None
        assert anonymizer.get_topic_id(3) is None

        await anonymizer.register_chat_topic_link(1, 2)
        await anonymizer.register_chat_topic_link(3, 4)

        assert anonymizer.get_chat_id(2) == 1
        assert anonymizer.get_topic_id(1) == 2
        assert anonymizer.get_chat_id(4) == 3
        assert anonymizer.get_topic_id(3) == 4

        del anonymizer

        anonymizer = await Anonymizer.from_file(file_path, encryption_key)

        # Data must be loaded
        assert anonymizer.get_chat_id(2) == 1
        assert anonymizer.get_topic_id(1) == 2
        assert anonymizer.get_chat_id(4) == 3
        assert anonymizer.get_topic_id(3) == 4

        del anonymizer

        with pytest.raises(CouldNotDecrypt):
            anonymizer = await Anonymizer.from_file(file_path, encryption_key_false)

        with pytest.raises(CouldNotDecrypt):
            anonymizer = await Anonymizer.from_file(file_path, b"123")
