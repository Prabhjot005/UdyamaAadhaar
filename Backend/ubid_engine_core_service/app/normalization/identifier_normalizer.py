import re
from dataclasses import dataclass


PAN_PATTERN = re.compile(r"^[A-Z]{3}[PCHFATBLJG][A-Z][0-9]{4}[A-Z]$")
GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PINCODE_PATTERN = re.compile(r"^[1-9][0-9]{5}$")


GST_STATE_NAMES = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
}

GST_STATE_PIN_PREFIXES = {
    "01": ("18", "19"),
    "02": ("17",),
    "03": ("14", "15", "16"),
    "04": ("16",),
    "05": ("24", "26"),
    "06": ("12", "13"),
    "07": ("11",),
    "08": ("30", "31", "32", "33", "34"),
    "09": ("20", "21", "22", "23", "24", "25", "26", "27", "28"),
    "10": ("80", "81", "82", "83", "84", "85"),
    "11": ("73",),
    "12": ("79",),
    "13": ("79",),
    "14": ("79",),
    "15": ("79",),
    "16": ("79",),
    "17": ("79",),
    "18": ("78",),
    "19": ("70", "71", "72", "73", "74"),
    "20": ("81", "82", "83", "84"),
    "21": ("75", "76", "77"),
    "22": ("49",),
    "23": ("45", "46", "47", "48"),
    "24": ("36", "37", "38", "39"),
    "26": ("36", "39"),
    "27": ("40", "41", "42", "43", "44"),
    "29": ("56", "57", "58", "59"),
    "30": ("40",),
    "31": ("68",),
    "32": ("67", "68", "69"),
    "33": ("60", "61", "62", "63", "64"),
    "34": ("60",),
    "35": ("74",),
    "36": ("50",),
    "37": ("51", "52", "53"),
    "38": ("19",),
}

PIN_REGIONS = {
    "1": "North",
    "2": "North",
    "3": "West",
    "4": "West",
    "5": "South",
    "6": "South",
    "7": "East",
    "8": "East",
}


@dataclass(frozen=True)
class PanNormalizationResult:
    normalized_pan: str
    is_valid: bool


@dataclass(frozen=True)
class GstinNormalizationResult:
    normalized_gstin: str
    is_valid: bool
    embedded_pan: str
    state_code: str
    state_name: str | None
    pincode_alignment: bool | None = None


@dataclass(frozen=True)
class PincodeNormalizationResult:
    normalized_pincode: str
    is_valid: bool
    region: str | None


class PanNormalizer:
    PREFIX_PATTERN = re.compile(r"\bpan(?:\s*(?:no|number))?\b", re.IGNORECASE)

    def normalize(self, value: str | None) -> PanNormalizationResult:
        pan = self.extract(value)
        return PanNormalizationResult(normalized_pan=pan, is_valid=bool(PAN_PATTERN.fullmatch(pan)))

    def extract(self, value: str | None) -> str:
        if value is None:
            return ""

        text = self.PREFIX_PATTERN.sub(" ", value)
        text = re.sub(r"[:.\-\s]", "", text)
        text = re.sub(r"[^A-Za-z0-9]", "", text).upper()
        match = re.search(r"[A-Z]{5}[0-9]{4}[A-Z]", text)
        return match.group(0) if match else text


class GstinNormalizer:
    PREFIX_PATTERN = re.compile(r"\bgstin\b|\bgst\s*(?:no|number)\b", re.IGNORECASE)

    def normalize(self, value: str | None, pincode: str | None = None) -> GstinNormalizationResult:
        gstin = self.extract(value)
        is_valid = bool(GSTIN_PATTERN.fullmatch(gstin))
        embedded_pan = gstin[2:12] if len(gstin) >= 12 else ""
        state_code = gstin[:2] if len(gstin) >= 2 else ""
        alignment = self._align_with_pincode(state_code, pincode) if is_valid and pincode else None

        return GstinNormalizationResult(
            normalized_gstin=gstin,
            is_valid=is_valid and bool(PAN_PATTERN.fullmatch(embedded_pan)),
            embedded_pan=embedded_pan,
            state_code=state_code,
            state_name=GST_STATE_NAMES.get(state_code),
            pincode_alignment=alignment,
        )

    def extract(self, value: str | None) -> str:
        if value is None:
            return ""

        text = self.PREFIX_PATTERN.sub(" ", value)
        text = re.sub(r"[:.\-\s]", "", text)
        text = re.sub(r"[^A-Za-z0-9]", "", text).upper()
        match = re.search(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]", text)
        return match.group(0) if match else text

    def _align_with_pincode(self, state_code: str, pincode: str | None) -> bool | None:
        pin_result = PincodeNormalizer().normalize(pincode)
        if not pin_result.is_valid:
            return None

        prefixes = GST_STATE_PIN_PREFIXES.get(state_code)
        if not prefixes:
            return None

        return pin_result.normalized_pincode.startswith(prefixes)


class PincodeNormalizer:
    PREFIX_PATTERN = re.compile(r"\b(?:pin|pincode|p\s*\.?\s*i\s*\.?\s*n|postal\s+code)\b", re.IGNORECASE)

    def normalize(self, value: str | None) -> PincodeNormalizationResult:
        pincode = self.extract(value)
        is_valid = bool(PINCODE_PATTERN.fullmatch(pincode))
        region = PIN_REGIONS.get(pincode[0]) if is_valid else None
        return PincodeNormalizationResult(normalized_pincode=pincode, is_valid=is_valid, region=region)

    def extract(self, value: str | None) -> str:
        if value is None:
            return ""

        text = self.PREFIX_PATTERN.sub(" ", value)
        candidates = re.findall(r"(?<!\d)[1-9][0-9]{5}(?!\d)", text)
        if not candidates:
            return ""

        for candidate in reversed(candidates):
            if text.rstrip().endswith(candidate):
                return candidate

        return candidates[-1]


def normalize_pan(value: str | None) -> PanNormalizationResult:
    return PanNormalizer().normalize(value)


def normalize_gstin(value: str | None, pincode: str | None = None) -> GstinNormalizationResult:
    return GstinNormalizer().normalize(value, pincode)


def normalize_pincode(value: str | None) -> PincodeNormalizationResult:
    return PincodeNormalizer().normalize(value)
