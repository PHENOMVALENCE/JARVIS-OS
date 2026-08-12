"""Bilingual handling for English and Swahili.

Whisper transcribes Swahili well and Microsoft publishes Tanzanian Swahili
voices, so speaking Swahili and being answered in Swahili works end to end.

The honest limit is the language model in the middle: a small local model
reasons noticeably worse in Swahili than in English. Commands are unaffected,
because those are matched deterministically here rather than generated, so
"fungua Notepad" is as reliable as "open Notepad".
"""

from __future__ import annotations

import re

SWAHILI = "sw"
ENGLISH = "en"

# Function words carry the signal: they are frequent, short, and rarely appear
# in the other language. Content words are far more likely to be borrowed.
_SWAHILI_MARKERS = {
    "na", "ya", "wa", "kwa", "ni", "si", "za", "la", "cha", "vya", "pa",
    "nini", "nani", "wapi", "lini", "vipi", "gani", "kwanini", "mbona",
    "tafadhali", "asante", "habari", "sasa", "leo", "kesho", "jana",
    "hapa", "pale", "hii", "hiyo", "huyu", "yule", "hali", "ndiyo", "hapana",
    "fungua", "funga", "cheza", "simamisha", "tafuta", "onyesha", "andika",
    "niambie", "nisaidie", "nataka", "unaweza", "saa", "ngapi", "hewa",
    "mvua", "jua", "muziki", "tuma", "piga", "soma", "sikiliza", "kumbusha",
    "pandisha", "shusha", "sauti", "mtandaoni", "mtandao", "ikoje", "maana",
    "picha", "skrini", "tarehe", "baada", "kumi", "tano", "moja", "mbili",
    "programu", "faili", "barua", "nyimbo", "wimbo",
}

_ENGLISH_MARKERS = {
    "the", "is", "are", "and", "what", "who", "where", "when", "how", "why",
    "please", "open", "close", "play", "stop", "search", "find", "show",
    "tell", "me", "my", "you", "can", "could", "would", "for", "with", "to",
    "of", "in", "on", "at", "it", "that", "this", "weather", "time", "today",
}

VOICES = {
    ENGLISH: {"edge": "en-GB-RyanNeural", "piper": "en_GB-alan-medium"},
    SWAHILI: {"edge": "sw-TZ-DaudiNeural", "piper": "en_GB-alan-medium"},
}

SWAHILI_VOICES = {
    "sw-TZ-DaudiNeural": "Tanzanian male",
    "sw-TZ-RehemaNeural": "Tanzanian female",
    "sw-KE-RafikiNeural": "Kenyan male",
    "sw-KE-ZuriNeural": "Kenyan female",
}

REPLY_IN_SWAHILI = (
    "Jibu kwa Kiswahili sanifu, kwa sentensi fupi na za kawaida. "
    "Usitumie Kiingereza isipokuwa kwa majina ya programu au maneno ya kiufundi."
)


def detect(text: str) -> str:
    """Guess the language of a short utterance from its function words."""
    words = re.findall(r"[a-z']+", str(text).lower())
    if not words:
        return ENGLISH
    swahili = sum(1 for word in words if word in _SWAHILI_MARKERS)
    english = sum(1 for word in words if word in _ENGLISH_MARKERS)
    if swahili > english:
        return SWAHILI
    # Swahili verbs commonly carry subject prefixes English words do not, which
    # rescues short commands like "nionyeshe" that have no marker words.
    if not english and any(re.match(r"^(?:ni|u|tu|wa|ki|vi|ha|na)[a-z]{3,}$", w) for w in words):
        return SWAHILI
    return ENGLISH


def voice_for(language: str, engine: str, configured: str) -> str:
    """The voice to speak a reply in, keeping the user's choice for English."""
    if language != SWAHILI:
        return configured
    return VOICES[SWAHILI].get(engine, configured)


# Deterministic command translation. These map onto existing router phrasings
# rather than a separate command set, so Swahili and English share one path.
_COMMAND_TERMS = (
    (r"\bfungua\b", "open"),
    (r"\bfunga\b", "close"),
    (r"\bcheza\b", "play"),
    (r"\bsimamisha\b|\bsitisha\b", "pause"),
    (r"\btafuta mtandaoni\b|\btafuta kwenye mtandao\b", "search online for"),
    (r"\btafuta\b", "find"),
    (r"\bonyesha\b|\bnionyeshe\b", "show"),
    (r"\bniambie\b", "tell me"),
    (r"\bkumbusha nikumbushe\b|\bnikumbushe\b|\bkumbusha\b", "remind me"),
    (r"\bhali ya hewa\b", "the weather"),
    (r"\bsaa ngapi\b", "what time is it"),
    (r"\btarehe gani\b|\bleo ni tarehe\b", "what is the date"),
    (r"\bpandisha sauti\b", "volume up"),
    (r"\bshusha sauti\b", "volume down"),
    (r"\bpicha ya skrini\b", "take a screenshot"),
    (r"\bbaada ya\b", "in"),
    (r"\bsasa hivi\b|\bsasa\b", "now"),
    (r"\bleo\b", "today"),
    (r"\bkesho\b", "tomorrow"),
    (r"\bikoje\b", ""),
)

NUMBERS = {
    "sifuri": 0, "moja": 1, "mbili": 2, "tatu": 3, "nne": 4, "tano": 5,
    "sita": 6, "saba": 7, "nane": 8, "tisa": 9, "kumi": 10, "ishirini": 20,
    "thelathini": 30, "arobaini": 40, "hamsini": 50, "sitini": 60,
}

# Swahili puts the count after the unit: "dakika kumi" is "minutes ten".
# English scheduling phrases expect the opposite order, so swap them.
_UNITS = {"dakika": "minutes", "saa": "hours", "sekunde": "seconds", "siku": "days"}
_UNIT_THEN_COUNT = re.compile(
    r"\b(?P<unit>" + "|".join(_UNITS) + r")\s+(?P<count>\d+|" + "|".join(NUMBERS) + r")\b",
    re.IGNORECASE,
)


def _swap_unit_and_count(text: str) -> str:
    def swap(match: re.Match) -> str:
        raw = match.group("count").lower()
        count = raw if raw.isdigit() else str(NUMBERS[raw])
        return f"{count} {_UNITS[match.group('unit').lower()]}"

    return _UNIT_THEN_COUNT.sub(swap, text)


def to_command_english(text: str) -> str:
    """Rewrite a Swahili command into the English the router already knows."""
    value = _swap_unit_and_count(str(text))
    for pattern, replacement in _COMMAND_TERMS:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
    # Any bare unit that survived the swap still needs translating.
    for swahili, english in _UNITS.items():
        value = re.sub(rf"\b{swahili}\b", english, value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()
