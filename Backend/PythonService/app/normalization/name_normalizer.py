import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class NameNormalizationOptions:
    sort_tokens: bool = False
    remove_non_ascii: bool = True
    remove_short_tokens: bool = False


class NameNormalizer:
    LEGAL_SUFFIXES = {
        "pvt",
        "ltd",
        "private",
        "limited",
        "llp",
        "co",
        "company",
        "inc",
        "corp",
        "enterprises",
    }
    STOPWORDS = {"and", "the", "of", "for"}
    NOISE_WORDS = {"india", "global", "international"}
    TOKEN_MAPPINGS = {
        "tech": "technology",
        "technologies": "technology",
        "svc": "services",
        "solutions": "services",
        "systems": "technology",
        "ent": "enterprise",
        "mfg": "manufacturing",
        "one": "1",
        "first": "1st",
        "i": "1",
        "ii": "2",
        "iii": "3",
        "iv": "4",
        "v": "5",
        "vi": "6",
        "vii": "7",
        "viii": "8",
        "ix": "9",
        "x": "10",
    }
    PREFIX_PATTERN = re.compile(r"^\s*(m\s*/\s*s|m\s+s|messrs)\.?\s+", re.IGNORECASE)
    SPECIAL_CHAR_PATTERN = re.compile(r"[^a-z0-9\s]")
    WHITESPACE_PATTERN = re.compile(r"\s+")
    REPEATED_CHAR_PATTERN = re.compile(r"([a-z])\1{2,}")

    def __init__(self, options: NameNormalizationOptions | None = None):
        self.options = options or NameNormalizationOptions()

    def normalize(self, value: str | None) -> str:
        if value is None:
            return ""

        text = self._normalize_text(value)
        if not text:
            return ""

        tokens = text.split()
        tokens = self._merge_acronyms(tokens)
        tokens = self._stabilize_tokens(tokens)
        tokens = self._remove_duplicate_tokens(tokens)

        if self.options.sort_tokens:
            tokens = sorted(tokens)

        return " ".join(tokens)

    def _normalize_text(self, value: str) -> str:
        text = unicodedata.normalize("NFKD", value)
        text = "".join(char for char in text if not unicodedata.combining(char))
        text = text.lower()
        text = self.PREFIX_PATTERN.sub("", text)
        text = text.replace("&", " and ")
        text = re.sub(r"[-/]", " ", text)

        if self.options.remove_non_ascii:
            text = text.encode("ascii", "ignore").decode("ascii")

        text = self.SPECIAL_CHAR_PATTERN.sub(" ", text)
        text = self.REPEATED_CHAR_PATTERN.sub(r"\1", text)
        text = self.WHITESPACE_PATTERN.sub(" ", text)
        return text.strip()

    def _stabilize_tokens(self, tokens: list[str]) -> list[str]:
        current = tokens

        for _ in range(3):
            normalized = self._normalize_tokens_once(current)
            if normalized == current:
                return normalized
            current = normalized

        return current

    def _normalize_tokens_once(self, tokens: list[str]) -> list[str]:
        normalized = []

        for token in tokens:
            token = self.TOKEN_MAPPINGS.get(token, token)

            if token in self.LEGAL_SUFFIXES:
                continue
            if token in self.STOPWORDS:
                continue
            if token in self.NOISE_WORDS:
                continue
            if self.options.remove_short_tokens and len(token) < 2:
                continue

            normalized.append(token)

        return normalized

    def _merge_acronyms(self, tokens: list[str]) -> list[str]:
        merged = []
        acronym = []

        for token in tokens:
            if len(token) == 1 and token.isalpha():
                acronym.append(token)
                continue

            if acronym:
                merged.append("".join(acronym))
                acronym = []

            merged.append(token)

        if acronym:
            merged.append("".join(acronym))

        return merged

    def _remove_duplicate_tokens(self, tokens: list[str]) -> list[str]:
        seen = set()
        deduplicated = []

        for token in tokens:
            if token in seen:
                continue

            seen.add(token)
            deduplicated.append(token)

        return deduplicated


def normalize_name(value: str | None, options: NameNormalizationOptions | None = None) -> str:
    return NameNormalizer(options).normalize(value)
