"""Deterministische researchadapter voor de 20-bedrijven-testset."""
import json
from pathlib import Path

from .query_planner import QueryContext
from .types import CombinedSearchResult, PlannedQuery
from .urls import canonicaliseer_url
from .validation import SourceDocument

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "mock_data.json"


class MockResearchTools:
    def __init__(self) -> None:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        self.data = {key: value for key, value in data.items() if not key.startswith("_")}
        self.sources: dict[str, tuple[str, str, dict]] = {}

    def _entry_for_query(self, query: str) -> tuple[str, dict] | None:
        query_lower = query.lower()
        for naam, entry in self.data.items():
            if naam.lower() in query_lower:
                return naam, entry
        return None

    async def search(
        self,
        query: PlannedQuery,
        max_results: int,
    ) -> list[CombinedSearchResult]:
        matched = self._entry_for_query(query.query)
        if matched is None:
            return []
        naam, entry = matched
        source_key = {
            "website": "website",
            "document": "jaarverslag",
            "media": "media",
        }.get(query.pad)
        finding = entry.get(source_key) if source_key else None
        if not finding:
            return []
        url = finding["url"]
        self.sources[canonicaliseer_url(url)] = (naam, source_key, finding)
        return [CombinedSearchResult(
            title=f"{naam} — {source_key}",
            url=url,
            canonical_url=canonicaliseer_url(url),
            snippets=[finding["context"]],
            providers=["mock"],
            queries=[query.query],
        )][:max_results]

    async def inspect(
        self,
        context: QueryContext,
        query: PlannedQuery,
        result: CombinedSearchResult,
    ) -> SourceDocument | None:
        source = self.sources.get(result.canonical_url)
        if source is None:
            return None
        _, source_key, finding = source
        return SourceDocument(
            naam=context.naam,
            company_website_url=context.website_url,
            url=result.url,
            titel=result.title,
            tekst=finding["context"],
            brontype=(
                "officiele_website" if source_key == "website"
                else "jaarverslag" if source_key == "jaarverslag"
                else "media"
            ),
            documenttype=(
                "jaarverslag" if source_key == "jaarverslag"
                else "teampagina" if source_key == "website"
                else "nieuwsartikel"
            ),
            gevraagd_jaar=context.gevraagd_jaar if source_key == "jaarverslag" else None,
            verslagjaar=(
                context.gevraagd_jaar if source_key == "jaarverslag" else None
            ),
            informatie_peilmoment=finding.get("peilmoment"),
            wp_gevonden=finding.get("wp"),
            eenheid=(
                "fte" if finding.get("is_fte") else "werkzame_personen"
            ),
            bewijsfragment=finding.get("context"),
            scope_class=(
                "limburg" if finding.get("limburg_specifiek", True)
                else "nederland"
            ),
        )
