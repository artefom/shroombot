"""
Generates names of random mushrooms from a file
"""


import random
from dataclasses import dataclass
from importlib.resources import files

import shroombot
from shroombot.server import NameRandomizer

FILES = files(shroombot)


def default_shroom_names() -> list[str]:
    with FILES.joinpath("shrooms.csv").open() as file:
        return [line.strip() for line in file.readlines()]


@dataclass
class ShroomNameRandomizer(NameRandomizer):
    pool: list[str]

    def get_random_topic_name(self) -> str:
        return random.choice(self.pool)


class GenericNameRandomizer(NameRandomizer):
    """Randomizer for generic user names"""

    def __init__(self):
        # Generate a pool of generic names
        self.names = self._generate_name_pool()
        self.used_names: set[str] = set()

    def _generate_name_pool(self) -> list[str]:
        """Generate a pool of generic names"""
        names = []

        # Greek alphabet style
        greek = [
            "Alpha",
            "Beta",
            "Gamma",
            "Delta",
            "Epsilon",
            "Zeta",
            "Eta",
            "Theta",
            "Iota",
            "Kappa",
        ]
        names.extend([f"User {letter}" for letter in greek])

        # Anonymous style
        for i in range(1, 21):
            names.append(f"Anonymous {i}")

        # Guest style
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        names.extend([f"Guest {letter}" for letter in letters[:20]])

        # Visitor style
        for i in range(1, 21):
            names.append(f"Visitor {i}")

        return names

    def get_random_topic_name(self) -> str:
        """Get a random generic name, avoiding recent duplicates"""
        available = [n for n in self.names if n not in self.used_names]

        # If all names have been used, reset the pool
        if not available:
            self.used_names.clear()
            available = self.names

        # Select a random name
        name = random.choice(available)
        self.used_names.add(name)

        # Keep only the last 50 used names to prevent unbounded growth
        if len(self.used_names) > 50:
            self.used_names = set(list(self.used_names)[-50:])

        return name
