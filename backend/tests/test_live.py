import httpx
import pytest

from app.parser import parse_document, select_specialties


@pytest.mark.live
def test_live_bseu_source() -> None:
    response = httpx.get("https://bseu.by/abiturient/xml/1.xml", timeout=20, follow_redirects=True)
    response.raise_for_status()
    rows = parse_document(response.content, response.headers.get("content-type"))
    selected = select_specialties(rows, ["Экономическая информатика"], "дневная", "платная")
    assert selected[0].admission_plan > 0
