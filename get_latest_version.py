import os
import pathlib
from typing import Tuple, List, Union

import requests


def get_latest_version_number() -> str:
    """
    Gets the latest pip version number from the pypi server.
    Returns: (str) the version of the latest pip module
    """
    req = requests.get("https://pypi.org/pypi/surrealdb-beta/json")
    return req.json()["info"]["version"]


def write_version_to_file(version_number: str) -> None:
    """
    Writes the version to the VERSION.txt file.
    Args:
        version_number: (str) the version to be written to the file
    Returns: None
    """
    version_file_path: str = str(pathlib.Path(__file__).parent.absolute()) + "/surrealdb/VERSION.txt"

    if os.path.exists(version_file_path):
        os.remove(version_file_path)

    with open(version_file_path, "w") as f:
        f.write(f"VERSION='{version_number}'")


def unpack_version_number(version_string: str) -> Tuple[int, int, int]:
    """
    Unpacks the version number converting it into a Tuple of integers.
    Args:
        version_string: (str) the version to be unpacked
    Returns: (Tuple[int, int, int]) the version number
    """
    version_buffer: List[str] = version_string.split(".")
    return int(version_buffer[0]), int(version_buffer[1]), int(version_buffer[2])


def pack_version_number(version_buffer: Union[Tuple[int, int, int], List[int]]) -> str:
    """
    Packs the version number into a string.
    Args:
        version_buffer: (Union[Tuple[int, int, int], List[int]]) the version to be packed
    Returns: (str) the packed version number
    """
    return f"{version_buffer[0]}.{version_buffer[1]}.{version_buffer[2]}"


def increase_version_number(version_buffer: Union[Tuple[int, int, int], List[int]]) -> List[int]:
    """
    Increases the number of the version with an increment of 0.0.1.
    Args:
        version_buffer: (Union[Tuple[int, int, int], List[int]]) the verion to be increased
    Returns: (List[int]) the updated version
    """
    first: int = version_buffer[0]
    second: int = version_buffer[1]
    third: int = version_buffer[2]

    third += 1
    if third >= 10:
        third = 0
        second += 1
        if second >= 10:
            second = 0
            first += 1

    return [first, second, third]


if __name__ == "__main__":
    write_version_to_file(
        version_number=pack_version_number(
            version_buffer=increase_version_number(
                version_buffer=unpack_version_number(
                    version_string=get_latest_version_number()
                )
            )
        )
    )
