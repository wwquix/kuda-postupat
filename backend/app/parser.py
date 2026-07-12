import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup


class ParserError(ValueError):
    """The upstream document is present but cannot be parsed safely."""


@dataclass(frozen=True)
class ParsedSpecialty:
    display_name: str
    study_form: str
    funding_type: str
    admission_plan: int
    applications_total: int
    distribution: dict[str, int]
    source_updated_at: datetime | None


DASHES = str.maketrans({"–": "-", "—": "-", "−": "-", "‑": "-"})
FUNDING_IDS = {"18": "бюджет", "19": "платная"}
HEADER_ALIASES = {
    "name": ("специальность", "наименование специальности"),
    "form": ("форма обучения", "форма"),
    "funding": ("основа обучения", "финансирование", "бюджет/платно"),
    "plan": ("план приема", "план", "мест"),
    "total": ("подано", "всего заявлений", "количество заявлений"),
}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).replace("\xa0", " ").translate(DASHES)
    return re.sub(r"\s+", " ", value).strip().lower().replace("ё", "е")


def normalize_form(value: str) -> str:
    value = normalize_text(value)
    if value.startswith(("дн", "очн")):
        return "дневная"
    if value.startswith(("заоч", "з/о")):
        return "заочная" if "сокращ" not in value else value
    return value


def normalize_funding(value: str) -> str:
    value = normalize_text(value)
    if value in FUNDING_IDS:
        return FUNDING_IDS[value]
    if any(token in value for token in ("плат", "внебюдж", "договор")):
        return "платная"
    if "бюдж" in value:
        return "бюджет"
    return value


def parse_int(value: str | None, *, field: str) -> int:
    cleaned = re.sub(r"[^0-9-]", "", (value or "").replace("\xa0", ""))
    if not cleaned or cleaned == "-":
        raise ParserError(f"Поле «{field}» не содержит целого числа")
    return int(cleaned)


def decode_bytes(raw: bytes, content_type: str | None = None) -> tuple[str, str]:
    if not raw or not raw.strip():
        raise ParserError("Источник вернул пустую страницу")
    candidates: list[str] = []
    header_match = re.search(r"charset\s*=\s*[\"']?([\w-]+)", content_type or "", re.I)
    head_match = re.search(rb"encoding=[\"']([\w-]+)|charset\s*=\s*([\w-]+)", raw[:2048], re.I)
    if raw.startswith(b"\xef\xbb\xbf"):
        candidates.append("utf-8-sig")
    if header_match:
        candidates.append(header_match.group(1))
    if head_match:
        encoding = next(group for group in head_match.groups() if group)
        candidates.append(encoding.decode("ascii", errors="ignore"))
    candidates.extend(["utf-8", "cp1251"])
    for encoding in dict.fromkeys(candidates):
        try:
            text = raw.decode(encoding)
            if "\ufffd" not in text:
                return text, encoding
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("cp1251", errors="replace"), "cp1251-replace"


def _parse_source_time(value: str | None) -> datetime | None:
    if not value:
        return None
    matches = re.findall(r"\d{2}\.\d{2}\.\d{4}(?:\s+\d{1,2}:\d{2})?", value)
    if not matches:
        return None
    candidate = matches[-1]
    fmt = "%d.%m.%Y %H:%M" if ":" in candidate else "%d.%m.%Y"
    return datetime.strptime(candidate, fmt)


def _distribution_from_attributes(attrs: dict[str, str]) -> dict[str, int]:
    distribution: dict[str, int] = {}
    for key, value in attrs.items():
        match = re.fullmatch(r"G_(Less_)?(\d+)(?:_(\d+))?", key, re.I)
        if not match:
            continue
        if match.group(1):
            label = f"0-{int(match.group(2)) - 1}"
        elif match.group(3):
            label = f"{int(match.group(2))}-{int(match.group(3))}"
        else:
            continue
        distribution[label] = parse_int(value, field=key)
    if not distribution:
        raise ParserError("В источнике не найдены обязательные столбцы распределения по баллам")
    return distribution


def _parse_xml(text: str) -> list[ParsedSpecialty]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ParserError(f"Некорректный XML: {exc}") from exc
    if root.tag.split("}")[-1].upper() != "DATAPACKET":
        raise ParserError("Неожиданный XML: корневой элемент не DATAPACKET")
    rows = [node for node in root.iter() if node.tag.split("}")[-1].upper() == "ROW"]
    if not rows:
        raise ParserError("XML не содержит конкурсных строк ROW")
    parsed = []
    for row in rows:
        attrs = row.attrib
        missing = [key for key in ("spname", "frname", "IDFINANCE", "AllCount") if key not in attrs]
        plan_key = "PlanBudj" if attrs.get("IDFINANCE") == "18" else "PlanVneBudj"
        if plan_key not in attrs:
            missing.append(plan_key)
        if missing:
            raise ParserError("В XML отсутствуют обязательные поля: " + ", ".join(missing))
        funding = normalize_funding(attrs["IDFINANCE"])
        if funding not in {"бюджет", "платная"}:
            continue
        parsed.append(
            ParsedSpecialty(
                display_name=re.sub(r"\s+", " ", attrs["spname"].replace("\xa0", " ")).strip(),
                study_form=normalize_form(attrs["frname"]),
                funding_type=funding,
                admission_plan=parse_int(attrs[plan_key], field="план приема"),
                applications_total=parse_int(attrs["AllCount"], field="подано заявлений"),
                distribution=_distribution_from_attributes(attrs),
                source_updated_at=_parse_source_time(attrs.get("genTime")),
            )
        )
    if not parsed:
        raise ParserError("XML не содержит поддерживаемых конкурсных строк")
    return parsed


def _find_header(headers: list[str], aliases: tuple[str, ...]) -> int | None:
    for index, header in enumerate(headers):
        if any(alias in header for alias in aliases):
            return index
    return None


def _parse_html(text: str) -> list[ParsedSpecialty]:
    soup = BeautifulSoup(text, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        raise ParserError("HTML не содержит конкурсной таблицы")
    parsed: list[ParsedSpecialty] = []
    table_with_schema = False
    for table in tables:
        rows = table.find_all("tr")
        if not rows:
            continue
        headers = [normalize_text(cell.get_text(" ", strip=True)) for cell in rows[0].find_all(["th", "td"])]
        indexes = {key: _find_header(headers, aliases) for key, aliases in HEADER_ALIASES.items()}
        if any(indexes[key] is None for key in ("name", "form", "funding", "plan", "total")):
            continue
        table_with_schema = True
        score_columns = {
            i: re.sub(r"[^0-9-]", "", header) for i, header in enumerate(headers) if re.search(r"\d+\s*-\s*\d+", header)
        }
        if not score_columns:
            raise ParserError("В таблице отсутствуют обязательные заголовки распределения по баллам")
        for row in rows[1:]:
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
            if len(cells) < len(headers):
                continue
            distribution = {
                label: parse_int(cells[index] or "0", field=label) for index, label in score_columns.items()
            }
            parsed.append(
                ParsedSpecialty(
                    display_name=re.sub(r"\s+", " ", cells[indexes["name"]].replace("\xa0", " ")).strip(),  # type: ignore[index]
                    study_form=normalize_form(cells[indexes["form"]]),  # type: ignore[index]
                    funding_type=normalize_funding(cells[indexes["funding"]]),  # type: ignore[index]
                    admission_plan=parse_int(cells[indexes["plan"]], field="план приема"),  # type: ignore[index]
                    applications_total=parse_int(cells[indexes["total"]], field="подано заявлений"),  # type: ignore[index]
                    distribution=distribution,
                    source_updated_at=_parse_source_time(table.get("data-updated-at")),
                )
            )
    if not table_with_schema:
        raise ParserError("Не найдены обязательные заголовки конкурсной таблицы")
    if not parsed:
        raise ParserError("Конкурсная таблица не содержит строк данных")
    return parsed


def parse_document(raw: bytes, content_type: str | None = None) -> list[ParsedSpecialty]:
    text, _encoding = decode_bytes(raw, content_type)
    stripped = text.lstrip("\ufeff\r\n\t ")
    return _parse_xml(text) if stripped.startswith("<?xml") or "<DATAPACKET" in stripped[:500] else _parse_html(text)


def select_specialties(
    rows: list[ParsedSpecialty], names: list[str], study_form: str, funding_type: str
) -> list[ParsedSpecialty]:
    wanted = {normalize_text(name) for name in names}
    form = normalize_form(study_form)
    funding = normalize_funding(funding_type)
    result = [
        row
        for row in rows
        if normalize_text(row.display_name) in wanted
        and normalize_form(row.study_form) == form
        and normalize_funding(row.funding_type) == funding
    ]
    missing = wanted - {normalize_text(row.display_name) for row in result}
    if missing:
        raise ParserError("Не найдены специальности для выбранной формы и основы: " + ", ".join(sorted(missing)))
    return result
