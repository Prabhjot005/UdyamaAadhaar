NORMALIZED_SOURCE_FIELDS = {"name", "address", "otherAddress", "other_address", "pincode", "pan", "panNumber", "gstin"}


from app.normalization.address_normalizer import normalize_address_with_metadata
from app.normalization.identifier_normalizer import normalize_gstin, normalize_pan, normalize_pincode
from app.normalization.name_normalizer import normalize_name


def normalize_department_record(record: dict) -> dict:
    normalized_name = normalize_name(record.get("name"))
    normalized_address = normalize_address_with_metadata(record.get("address"))
    normalized_other_address = normalize_address_with_metadata(record.get("otherAddress") or record.get("other_address"))
    normalized_pincode = normalize_pincode(record.get("pincode") or record.get("address") or record.get("otherAddress") or record.get("other_address"))
    normalized_pan = normalize_pan(record.get("panNumber") or record.get("pan"))
    normalized_gstin = normalize_gstin(record.get("gstin"), normalized_pincode.normalized_pincode)

    return {
        **{
            key: value
            for key, value in record.items()
            if key not in NORMALIZED_SOURCE_FIELDS
        },
        "normalized_name": normalized_name,
        "normalized_address": normalized_address.normalized_address,
        "normalized_other_address": normalized_other_address.normalized_address,
        "normalized_landmarks": normalized_address.landmarks,
        "normalized_other_landmarks": normalized_other_address.landmarks,
        "normalized_pincode": normalized_pincode.normalized_pincode,
        "normalized_pan": normalized_pan.normalized_pan,
        "normalized_gstin": normalized_gstin.normalized_gstin,
        "normalized_gstin_state": normalized_gstin.state_name,
    }
