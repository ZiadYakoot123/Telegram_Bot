from __future__ import annotations

import random
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence, TypeVar


T = TypeVar("T")

# Zero-width characters for invisible entropy injection
ZERO_WIDTH_JOINER = "\u200d"
ZERO_WIDTH_SPACE = "\u200b"
WORD_JOINER = "\u2060"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def chunked(items: Sequence[T], size: int) -> Iterator[list[T]]:
    if size <= 0:
        raise ValueError("size must be > 0")
    for i in range(0, len(items), size):
        yield list(items[i : i + size])


def add_invisible_entropy(text: str) -> str:
    """
    Add invisible random entropy to text to prevent duplicate detection.
    Uses zero-width characters to encode a random number.
    """
    if not text:
        return text

    # Generate a random number (0-9999) and encode it as invisible chars
    random_num = random.randint(0, 9999)
    entropy_chars = [ZERO_WIDTH_SPACE, ZERO_WIDTH_JOINER, WORD_JOINER]

    # Create invisible marker using zero-width characters
    invisible_marker = "".join(random.choice(entropy_chars) for _ in range(3))

    # Append to text (invisible to humans)
    return text + invisible_marker


def add_random_number_suffix(text: str, digits: int = 4) -> str:
    """Append a visible random number to outgoing text."""
    if not text:
        return text
    width = max(1, digits)
    upper = (10**width) - 1
    value = random.randint(0, upper)
    return f"{text} [{value:0{width}d}]"


def random_hashtag(length: int = 8) -> str:
    chars = string.ascii_lowercase + string.digits
    return "#" + "".join(random.choices(chars, k=length))


def to_unique_list(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    return ordered
