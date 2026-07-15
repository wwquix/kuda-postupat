from dataclasses import dataclass
from typing import Final, Protocol

from ..parser import ParsedSpecialty

BSEU_ADAPTER_KEY: Final = "bseu"


@dataclass(frozen=True)
class ParsedAdmissionDocument:
    rows: tuple[ParsedSpecialty, ...]
    selected: tuple[ParsedSpecialty, ...]


class MonitoringAdapter(Protocol):
    key: str
    university_code: str
    source_url: str
    source_page_url: str

    def parse(self, raw: bytes, content_type: str | None) -> ParsedAdmissionDocument: ...
