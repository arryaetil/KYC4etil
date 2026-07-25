"""Tokenverbruik van de bronreviewer wordt bijgehouden."""
import pytest

from app.research import usage
from app.research.query_planner import QueryContext
from app.research.source_reviewer import IntelligentSourceReviewer
from app.research.validation import SourceDocument


@pytest.mark.asyncio
async def test_bronreview_registreert_tokenverbruik(monkeypatch):
    from app.config import get_settings

    class UsageResponse:
        output_text = (
            '{"beslissing": "tonen_aan_reviewer", "identity_class": '
            '"exact_entity", "scope_class": "vestiging", '
            '"gevonden_organisatie": "Voorbeeld Zorg", "reden": "match"}'
        )
        usage = type("Usage", (), {"input_tokens": 200, "output_tokens": 40})()

    class UsageResponses:
        async def create(self, **kwargs):
            return UsageResponse()

    class UsageOpenAI:
        def __init__(self, api_key):
            self.responses = UsageResponses()

    import openai
    settings = get_settings()
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(openai, "AsyncOpenAI", UsageOpenAI)

    usage.start_usage_tracking()
    document = SourceDocument(
        naam="Voorbeeld Zorg",
        company_website_url="https://anderdomein.nl",
        url="https://onbekend.nl/artikel",
        titel="Artikel",
        tekst="Voorbeeld Zorg heeft 47 medewerkers.",
        brontype="media",
        wp_gevonden=47,
        eenheid="werkzame_personen",
        bewijsfragment="47 medewerkers.",
    )
    context = QueryContext(
        naam="Voorbeeld Zorg", website_url="https://voorbeeldzorg.nl",
    )

    await IntelligentSourceReviewer().review(context, document)

    assert usage.get_usage_totals() == (200, 40)
