"""
Ban manager for handling banned users
"""

import csv
import logging
from pathlib import Path
from typing import Set

logger = logging.getLogger(__name__)


class BanManager:
    """
    Manages banned users using CSV file storage
    """

    def __init__(self, ban_file_path: str):
        self.ban_file_path = Path(ban_file_path)
        self._banned_users: Set[int] = set()
        self._load_banned_users()

    def _load_banned_users(self):
        """Load banned users from CSV file"""
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
                            self._banned_users.add(user_id)
                        except ValueError:
                            logger.warning("Invalid user ID in ban file: %s", row[0])
            logger.info("Loaded %d banned users from file", len(self._banned_users))
        except (OSError, IOError, ValueError) as e:
            logger.error("Error loading banned users: %s", e)

    def _save_banned_users(self):
        """Save banned users to CSV file"""
        try:
            with open(self.ban_file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                for user_id in sorted(self._banned_users):
                    writer.writerow([user_id])
            logger.info("Saved %d banned users to file", len(self._banned_users))
        except (OSError, IOError) as e:
            logger.error("Error saving banned users: %s", e)
            raise

    def ban_user(self, user_id: int) -> bool:
        """
        Ban a user by ID

        Returns:
            bool: True if user was banned, False if already banned
        """
        if user_id in self._banned_users:
            return False

        self._banned_users.add(user_id)
        self._save_banned_users()
        logger.info("Banned user %d", user_id)
        return True

    def unban_user(self, user_id: int) -> bool:
        """
        Unban a user by ID

        Returns:
            bool: True if user was unbanned, False if not banned
        """
        if user_id not in self._banned_users:
            return False

        self._banned_users.remove(user_id)
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

    def get_banned_users(self) -> Set[int]:
        """
        Get set of all banned user IDs

        Returns:
            Set[int]: Set of banned user IDs
        """
        return self._banned_users.copy()

    def get_banned_count(self) -> int:
        """
        Get number of banned users

        Returns:
            int: Number of banned users
        """
        return len(self._banned_users)
