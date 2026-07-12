import httpx
import pytest

from app.config import Settings
from app.scraper import AdmissionScraper


class FakeClient:
    outcomes: list[object] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, headers):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.mark.asyncio
async def test_http_500_is_retried_and_raised(monkeypatch) -> None:
    request = httpx.Request("GET", "https://example.test")
    FakeClient.outcomes = [httpx.Response(500, request=request), httpx.Response(500, request=request)]
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr("app.scraper.asyncio.sleep", lambda _delay: _immediate())
    scraper = AdmissionScraper(Settings(request_retries=2, source_data_url="https://example.test"))
    with pytest.raises(httpx.HTTPStatusError):
        await scraper._fetch({})


@pytest.mark.asyncio
async def test_timeout_is_retried_and_raised(monkeypatch) -> None:
    FakeClient.outcomes = [httpx.ReadTimeout("timeout"), httpx.ReadTimeout("timeout")]
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr("app.scraper.asyncio.sleep", lambda _delay: _immediate())
    scraper = AdmissionScraper(Settings(request_retries=2, source_data_url="https://example.test"))
    with pytest.raises(httpx.ReadTimeout):
        await scraper._fetch({})


async def _immediate() -> None:
    return None
