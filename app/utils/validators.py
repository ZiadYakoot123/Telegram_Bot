from __future__ import annotations

import re
from typing import Iterable


USERNAME_RE = re.compile(r"^@?[A-Za-z0-9_]{5,32}$")
PHONE_RE = re.compile(r"^\+?[1-9][0-9]{6,14}$")


def is_valid_username(value: str) -> bool:
    return bool(USERNAME_RE.fullmatch(value.strip()))


def is_valid_phone(value: str) -> bool:
    return bool(PHONE_RE.fullmatch(value.strip()))


def parse_csv_ints(raw: str) -> list[int]:
    values: list[int] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            values.append(int(item))
        except ValueError:
            continue
    return values


def ensure_admin(user_id: int, admin_ids: Iterable[int]) -> bool:
    return user_id in set(admin_ids)
