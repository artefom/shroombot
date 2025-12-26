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

    def _get_name_letter(self) -> str:
        letter = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        number = random.choice("1234567890")

        return f"{letter}{number}"

    def get_random_topic_name(self) -> str:
        title = random.choice(["User", "Guest", "Visitor", "Anonymous"])

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

        greek_l = random.choice(greek)

        return f"{title} {greek_l} {self._get_name_letter()}"
