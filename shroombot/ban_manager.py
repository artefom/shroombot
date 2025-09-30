"""
Ban manager for handling banned users
"""

import csv
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class BanInfo:
    """Information about a banned user"""

    user_id: int
    banned_at: datetime
    thread_id: Optional[int] = None  # The thread ID where they were banned from


class BanManager:
    """
    Manages banned users using CSV file storage with timestamps
    """

    def __init__(self, ban_file_path: str):
        self.ban_file_path = Path(ban_file_path)
        self._banned_users: Dict[int, BanInfo] = {}
        self._load_banned_users()

    def _load_banned_users(self):
        """Load banned users from CSV file with format: user_id,timestamp,thread_id"""
        if not self.ban_file_path.exists():
            logger.info("Ban file does not exist, starting with empty ban list")
            return

        try:
            with open(self.ban_file_path, "r", newline="", encoding="utf-8") as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    if row and row[0].strip():  # Skip empty rows
                        try:
                            user_id = int(row[0].strip())
                            # Parse timestamp (default to now if not present or invalid)
                            try:
                                banned_at = (
                                    datetime.fromisoformat(row[1].strip())
                                    if len(row) > 1
                                    else datetime.now()
                                )
                            except (ValueError, IndexError):
                                banned_at = datetime.now()
                            # Parse thread_id (optional)
                            thread_id = None
                            if len(row) > 2 and row[2].strip():
                                try:
                                    thread_id = int(row[2].strip())
                                except ValueError:
                                    pass

                            self._banned_users[user_id] = BanInfo(
                                user_id=user_id,
                                banned_at=banned_at,
                                thread_id=thread_id,
                            )
                        except ValueError:
                            logger.warning("Invalid user ID in ban file: %s", row[0])
            logger.info("Loaded %d banned users from file", len(self._banned_users))
        except (OSError, IOError, ValueError) as e:
            logger.error("Error loading banned users: %s", e)

    def _save_banned_users(self):
        """Save banned users to CSV file with format: user_id,timestamp,thread_id"""
        try:
            with open(self.ban_file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                for user_id in sorted(self._banned_users.keys()):
                    ban_info = self._banned_users[user_id]
                    writer.writerow(
                        [
                            ban_info.user_id,
                            ban_info.banned_at.isoformat(),
                            ban_info.thread_id if ban_info.thread_id else "",
                        ]
                    )
            logger.info("Saved %d banned users to file", len(self._banned_users))
        except (OSError, IOError) as e:
            logger.error("Error saving banned users: %s", e)
            raise

    def ban_user(self, user_id: int, thread_id: Optional[int] = None) -> bool:
        """
        Ban a user by ID

        Args:
            user_id: The user's chat ID to ban
            thread_id: Optional thread ID where the ban was initiated

        Returns:
            bool: True if user was banned, False if already banned
        """
        if user_id in self._banned_users:
            return False

        self._banned_users[user_id] = BanInfo(
            user_id=user_id, banned_at=datetime.now(), thread_id=thread_id
        )
        self._save_banned_users()
        logger.info("Banned user %d (thread: %s)", user_id, thread_id)
        return True

    def unban_user(self, user_id: int) -> bool:
        """
        Unban a user by ID

        Returns:
            bool: True if user was unbanned, False if not banned
        """
        if user_id not in self._banned_users:
            return False

        del self._banned_users[user_id]
        self._save_banned_users()
        logger.info("Unbanned user %d", user_id)
        return True

    def is_banned(self, user_id: int) -> bool:
        """
        Check if a user is banned

        Returns:
            bool: True if user is banned, False otherwise
        """
        return user_id in self._banned_users

    def get_banned_users(self) -> Dict[int, BanInfo]:
        """
        Get dictionary of all banned users with their info

        Returns:
            Dict[int, BanInfo]: Dictionary mapping user IDs to BanInfo objects
        """
        return self._banned_users.copy()

    def get_ban_info(self, user_id: int) -> Optional[BanInfo]:
        """
        Get ban information for a specific user

        Returns:
            BanInfo: Ban information if user is banned, None otherwise
        """
        return self._banned_users.get(user_id)

    def get_banned_count(self) -> int:
        """
        Get number of banned users

        Returns:
            int: Number of banned users
        """
        return len(self._banned_users)
