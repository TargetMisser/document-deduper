from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date

MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def readable_text(text: str) -> str:
    text = normalize_text(text)
    for month in MONTHS:
        pattern = r"\b" + r"\s*".join(re.escape(ch) for ch in month) + r"\b"
        text = re.sub(pattern, month, text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def comparable_text(text: str) -> str:
    text = readable_text(text).lower()
    text = re.sub(r"wolters kluwer one legale|\bcopyright\b|one legale", " ", text)
    text = re.sub(r"[^0-9a-zàèéìòù]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fingerprint(lines: list[str], sample_chars: int = 12000) -> str:
    sample = comparable_text("\n".join(lines))[:sample_chars]
    return hashlib.sha1(sample.encode("utf-8")).hexdigest()


def parse_date(text: str) -> date | None:
    text = readable_text(text).lower()
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b", text)
    if m:
        day, month, year = map(int, m.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None

    m = re.search(r"\b(\d{1,2})\s+([a-zàèéìòù]+)\s+(20\d{2})\b", text)
    if m:
        day = int(m.group(1))
        month = MONTHS.get(m.group(2))
        year = int(m.group(3))
        if month:
            try:
                return date(year, month, day)
            except ValueError:
                return None
    return None


def parse_number(text: str) -> str | None:
    m = re.search(r"\bn\.\s*([0-9]{1,8})\b", readable_text(text), re.I)
    return m.group(1) if m else None
