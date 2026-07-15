from ..config import Settings
from ..parser import parse_document, select_specialties
from .contract import BSEU_ADAPTER_KEY, ParsedAdmissionDocument


class BseuMonitoringAdapter:
    key = BSEU_ADAPTER_KEY
    university_code = "bseu"

    def __init__(self, settings: Settings):
        self.source_url = settings.data_url
        self.source_page_url = settings.source_page_url
        self._specialty_names = settings.specialty_names
        self._study_form = settings.study_form
        self._funding_type = settings.funding_type

    def parse(self, raw: bytes, content_type: str | None) -> ParsedAdmissionDocument:
        rows = parse_document(raw, content_type)
        selected = select_specialties(
            rows,
            self._specialty_names,
            self._study_form,
            self._funding_type,
        )
        return ParsedAdmissionDocument(rows=tuple(rows), selected=tuple(selected))
