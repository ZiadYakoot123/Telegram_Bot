from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import phonenumbers


@dataclass(slots=True)
class ContactRecord:
    user_id: int
    username: str | None
    phone: str | None
    last_interaction: datetime | None


def filter_by_last_interaction(records: list[ContactRecord], days: int) -> list[ContactRecord]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return [r for r in records if r.last_interaction and r.last_interaction >= cutoff]


def filter_telegram_numbers_by_country(phone_numbers: list[str], country_codes: set[str]) -> list[str]:
    normalized_codes = {code.upper() for code in country_codes}
    output: list[str] = []

    for number in phone_numbers:
        try:
            parsed = phonenumbers.parse(number, None)
            region = phonenumbers.region_code_for_number(parsed)
            if region and region.upper() in normalized_codes:
                output.append(number)
        except phonenumbers.NumberParseException:
            continue

    return output


def deduplicate_targets(targets: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []

    for target in targets:
        key = target.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(target)

    return unique
