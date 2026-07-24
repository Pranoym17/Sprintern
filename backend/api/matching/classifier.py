from api.ingestion.normalization import normalize_text
from api.models import InternshipStatus

POSITIVE_TITLE_PHRASES = (
    "intern",
    "internship",
    "co op",
    "student developer",
    "student engineer",
    "university program",
)
NEGATIVE_TITLE_PHRASES = (
    "senior",
    "staff",
    "principal",
    "manager",
    "director",
    "full time",
    "new grad",
    "new graduate",
)
POSITIVE_DESCRIPTION_PHRASES = (
    "internship program",
    "intern position",
    "co op program",
    "currently enrolled",
    "returning to school",
)


def contains_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def classify_internship(title: str, description: str | None) -> InternshipStatus:
    normalized_title = normalize_text(title)
    title_positive = any(
        contains_phrase(normalized_title, phrase) for phrase in POSITIVE_TITLE_PHRASES
    )
    title_negative = any(
        contains_phrase(normalized_title, phrase) for phrase in NEGATIVE_TITLE_PHRASES
    )
    if title_positive and title_negative:
        return InternshipStatus.AMBIGUOUS
    if title_positive:
        return InternshipStatus.CONFIRMED
    if title_negative:
        return InternshipStatus.REJECTED

    normalized_description = normalize_text(description or "")
    if any(
        contains_phrase(normalized_description, phrase) for phrase in POSITIVE_DESCRIPTION_PHRASES
    ):
        return InternshipStatus.CONFIRMED
    return InternshipStatus.AMBIGUOUS
