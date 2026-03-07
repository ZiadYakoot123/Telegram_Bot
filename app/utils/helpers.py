from __future__ import annotations

import random
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence, TypeVar


T = TypeVar("T")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def chunked(items: Sequence[T], size: int) -> Iterator[list[T]]:
    if size <= 0:
        raise ValueError("size must be > 0")
    for i in range(0, len(items), size):
        yield list(items[i : i + size])


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
