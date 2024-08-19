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
