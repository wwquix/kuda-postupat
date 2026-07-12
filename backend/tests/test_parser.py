from pathlib import Path

import pytest

from app.parser import ParserError, decode_bytes, parse_document, select_specialties


def test_normal_html_parsing(fixtures_dir: Path) -> None:
    rows = parse_document((fixtures_dir / "normal.html").read_bytes(), "text/html; charset=utf-8")
    selected = select_specialties(rows, ["Экономическая информатика"], "дневная", "платная")
    assert selected[0].admission_plan == 3
    assert selected[0].applications_total == 6
    assert selected[0].distribution["270-279"] == 2


def test_utf8_decoding(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "normal.html").read_bytes()
    text, encoding = decode_bytes(raw, "text/html; charset=utf-8")
    assert "Экономическая информатика" in text
    assert encoding == "utf-8"


def test_windows_1251_decoding_and_parsing(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "normal.html").read_text(encoding="utf-8").encode("cp1251")
    rows = parse_document(raw, "text/html; charset=windows-1251")
    assert rows[0].display_name == "Экономическая информатика"


def test_whitespace_and_reordered_columns(fixtures_dir: Path) -> None:
    rows = parse_document((fixtures_dir / "reordered.html").read_bytes())
    selected = select_specialties(rows, ["экономическая\u00a0информатика"], "дн.", "платно")
    assert selected[0].display_name == "Экономическая информатика"
    assert selected[0].distribution["290-299"] == 1


def test_live_xml_shape(fixtures_dir: Path) -> None:
    rows = parse_document((fixtures_dir / "live_shape.xml").read_bytes(), "text/xml")
    assert rows[0].funding_type == "платная"
    assert rows[0].admission_plan == 60
    assert rows[0].source_updated_at is not None


def test_missing_specialty(fixtures_dir: Path) -> None:
    rows = parse_document((fixtures_dir / "normal.html").read_bytes())
    with pytest.raises(ParserError, match="Не найдены специальности"):
        select_specialties(rows, ["Несуществующая"], "дневная", "платная")


def test_missing_required_headers(fixtures_dir: Path) -> None:
    with pytest.raises(ParserError, match="обязательные заголовки"):
        parse_document((fixtures_dir / "missing_headers.html").read_bytes())


@pytest.mark.parametrize("raw", [b"", b"   \r\n"])
def test_empty_page(raw: bytes) -> None:
    with pytest.raises(ParserError, match="пустую страницу"):
        parse_document(raw)
