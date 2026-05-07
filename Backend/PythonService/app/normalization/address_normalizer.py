import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AddressNormalizationOptions:
    extract_landmarks: bool = True


@dataclass(frozen=True)
class AddressNormalizationResult:
    normalized_address: str
    landmarks: list[str] = field(default_factory=list)


class AddressNormalizer:
    SPECIAL_CHAR_PATTERN = re.compile(r"[!@#$%\^*()_+={}\[\]|\\:;\"'<>?]")
    WHITESPACE_PATTERN = re.compile(r"\s+")
    COMMA_SPACING_PATTERN = re.compile(r"\s*,\s*")
    TOKEN_BOUNDARY_PATTERN = re.compile(r"(?<!/)\b([a-z]+)\.?\b(?!/)", re.IGNORECASE)
    HYPHEN_PHASE_PATTERN = re.compile(r"\b([a-z]+)-(?=[a-z0-9])", re.IGNORECASE)

    TOKEN_MAPPINGS = {
        "rd": "road",
        "st": "street",
        "ln": "lane",
        "bypass": "bypass",
        "hwy": "highway",
        "mgt": "marg",
        "pth": "path",
        "extn": "extension",
        "flt": "flat",
        "apt": "apartment",
        "bldg": "building",
        "off": "office",
        "ste": "suite",
        "no": "number",
        "sy": "survey",
        "fl": "floor",
        "flr": "floor",
        "grnd": "ground floor",
        "bsmt": "basement",
        "indl": "industrial",
        "est": "estate",
        "ph": "phase",
        "sec": "sector",
        "blk": "block",
        "hll": "halli",
        "pl": "palya",
        "krl": "kere",
        "ngr": "nagar",
        "pura": "pura",
        "opp": "opposite",
        "bhd": "behind",
        "nr": "near",
        "adj": "adjacent",
    }
    PHRASE_MAPPINGS = {
        "gr fl": "ground floor",
        "next to": "next to",
    }
    LOCAL_EXACT_MAPPINGS = {
        "jngr": "jayanagar",
        "bommanahll": "bommanahalli",
        "bilekhalli": "bilekahalli",
    }
    LOCAL_SUFFIX_MAPPINGS = {
        "hll": "halli",
        "pl": "palya",
        "krl": "kere",
        "ngr": "nagar",
    }
    LANDMARK_PREFIXES = (
        "opposite ",
        "behind ",
        "near ",
        "adjacent ",
        "next to ",
    )

    def __init__(self, options: AddressNormalizationOptions | None = None):
        self.options = options or AddressNormalizationOptions()

    def normalize(self, value: str | None) -> str:
        return self.normalize_with_metadata(value).normalized_address

    def normalize_with_metadata(self, value: str | None) -> AddressNormalizationResult:
        if value is None:
            return AddressNormalizationResult(normalized_address="")

        text = self._preprocess(value)
        if not text:
            return AddressNormalizationResult(normalized_address="")

        address_segments = []
        landmarks = []

        for segment in self._split_segments(text):
            normalized_segment = self._normalize_segment(segment)
            if not normalized_segment:
                continue

            if self.options.extract_landmarks and self._is_landmark_segment(normalized_segment):
                landmarks.append(normalized_segment.upper())
                continue

            address_segments.append(normalized_segment.upper())

        return AddressNormalizationResult(
            normalized_address=", ".join(address_segments),
            landmarks=landmarks,
        )

    def _preprocess(self, value: str) -> str:
        text = value.strip().lower()
        text = self.SPECIAL_CHAR_PATTERN.sub("", text)
        text = text.replace(".", " ")
        text = self.HYPHEN_PHASE_PATTERN.sub(r"\1 ", text)
        text = self.COMMA_SPACING_PATTERN.sub(", ", text)
        text = self.WHITESPACE_PATTERN.sub(" ", text)
        return text.strip(" ,")

    def _split_segments(self, text: str) -> list[str]:
        return [segment.strip() for segment in text.split(",") if segment.strip()]

    def _normalize_segment(self, segment: str) -> str:
        segment = self._apply_phrase_mappings(segment)
        segment = self.TOKEN_BOUNDARY_PATTERN.sub(self._replace_token, segment)
        segment = self.WHITESPACE_PATTERN.sub(" ", segment)
        return segment.strip()

    def _apply_phrase_mappings(self, segment: str) -> str:
        for phrase, replacement in self.PHRASE_MAPPINGS.items():
            segment = re.sub(rf"\b{re.escape(phrase)}\b", replacement, segment)
        return segment

    def _replace_token(self, match: re.Match[str]) -> str:
        token = match.group(1).lower()

        if token in self.LOCAL_EXACT_MAPPINGS:
            return self.LOCAL_EXACT_MAPPINGS[token]
        if token in self.TOKEN_MAPPINGS:
            return self.TOKEN_MAPPINGS[token]

        return self._expand_local_suffix(token)

    def _expand_local_suffix(self, token: str) -> str:
        for suffix, replacement in self.LOCAL_SUFFIX_MAPPINGS.items():
            if token.endswith(suffix) and len(token) > len(suffix):
                return f"{token[:-len(suffix)]}{replacement}"

        return token

    def _is_landmark_segment(self, segment: str) -> bool:
        return segment.startswith(self.LANDMARK_PREFIXES)


def normalize_address(value: str | None, options: AddressNormalizationOptions | None = None) -> str:
    return AddressNormalizer(options).normalize(value)


def normalize_address_with_metadata(
    value: str | None,
    options: AddressNormalizationOptions | None = None,
) -> AddressNormalizationResult:
    return AddressNormalizer(options).normalize_with_metadata(value)
