"""De website-agent: een multi-turn tool-use-loop over de eigen site.

Het model kiest zelf welke pagina's het bezoekt (team, over-ons, specialisten)
binnen een paginabudget en uitsluitend op het eigen domein. Levert de site niets
op, dan valt de graph terug op een open zoekopdracht."""
import asyncio
import json
from typing import Any, TypedDict
from urllib.parse import urlparse

from ..config import get_settings
from . import fetch, llm, wp_extractie
from .base import AgentFinding
from .prompts import AGENT_PROMPT, TOOLS

settings = get_settings()


class WebsiteResearchState(TypedDict, total=False):
    naam: str
    adres: str | None
    website_url: str | None
    gemeente: str | None
    best: AgentFinding | None


def _finding_from_website_data(data: dict[str, Any], website_url: str) -> AgentFinding:
    return AgentFinding(
        wp_gevonden=data["wp_gevonden"], context=data.get("context"),
        zekerheid=data.get("zekerheid", "laag"), reden=data.get("reden"),
        bron_url=website_url.rstrip("/"), bron_type="website",
        is_totaal_meerdere_vestigingen=data.get("is_totaal_meerdere_vestigingen", False),
        is_limburg_specifiek=data.get("is_limburg_specifiek"),
        is_fte=data.get("is_fte", False), peilmoment=data.get("peilmoment"),
        raw={**data, "research_graph": "website"},
    )


async def _tool_use_loop(naam: str, adres: str | None, start_url: str) -> dict | None:
    """Multi-turn tool-use-loop: het model beslist zelf welke pagina's te bezoeken
    (via bezoek_pagina) totdat het meld_resultaat aanroept of het paginabudget
    (settings.max_website_pages) op is."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    prompt = AGENT_PROMPT.format(naam=naam, adres=adres or "onbekend", start_url=start_url)
    eigen_domein = urlparse(start_url).netloc

    response = await llm._create_response(client,
        model=llm._extraction_model(), input=prompt, tools=TOOLS, max_output_tokens=1024,
    )

    bezochte_paginas = 0
    # +2 i.p.v. +1: één ronde per toegestane paginabezoek, plus één extra ronde
    # zodat het model kan reageren op de "paginabudget bereikt"-melding met meld_resultaat
    # (zonder die extra ronde wordt die laatste modelreactie nooit verwerkt).
    for _ in range(settings.max_website_pages + 2):
        function_calls = [item for item in response.output if getattr(item, "type", None) == "function_call"]
        if not function_calls:
            return None

        outputs = []
        for call in function_calls:
            args = json.loads(call.arguments)
            if call.name == "meld_resultaat":
                return args
            if call.name == "bezoek_pagina":
                gevraagde_url = urlparse(args["url"])
                if gevraagde_url.scheme not in ("http", "https") or gevraagde_url.netloc != eigen_domein:
                    outputs.append({"type": "function_call_output", "call_id": call.call_id,
                                    "output": json.dumps({"fout": f"Alleen pagina's op {eigen_domein} zijn toegestaan."})})
                    continue
                bezochte_paginas += 1
                if bezochte_paginas > settings.max_website_pages:
                    outputs.append({"type": "function_call_output", "call_id": call.call_id,
                                    "output": json.dumps({"fout": "paginabudget bereikt, rond af met meld_resultaat"})})
                    continue
                try:
                    pagina = await fetch._haal_pagina_op(args["url"])
                except Exception as exc:
                    pagina = {"fout": str(exc)[:500]}
                outputs.append({"type": "function_call_output", "call_id": call.call_id,
                                "output": json.dumps(pagina)[:20000]})

        response = await llm._create_response(client,
            model=llm._extraction_model(), previous_response_id=response.id,
            input=outputs, tools=TOOLS, max_output_tokens=1024,
        )

    return None


def _build_website_research_graph():
    from langgraph.graph import END, StateGraph

    async def inspect_website(state: WebsiteResearchState) -> dict[str, AgentFinding | None]:
        website_url = state.get("website_url")
        if not website_url:
            return {"best": None}
        data = await _tool_use_loop(state["naam"], state.get("adres"), website_url.rstrip("/"))
        await asyncio.sleep(1.0)  # rate limit per domein
        if data and data.get("wp_gevonden"):
            return {"best": _finding_from_website_data(data, website_url)}
        return {"best": None}

    async def web_search_fallback(state: WebsiteResearchState) -> dict[str, AgentFinding | None]:
        return {"best": await wp_extractie._web_search_wp(state["naam"], state.get("gemeente"))}

    def after_website(state: WebsiteResearchState) -> str:
        return END if state.get("best") is not None else "web_search_fallback"

    graph = StateGraph(WebsiteResearchState)
    graph.add_node("inspect_website", inspect_website)
    graph.add_node("web_search_fallback", web_search_fallback)
    graph.set_entry_point("inspect_website")
    graph.add_conditional_edges("inspect_website", after_website)
    graph.add_edge("web_search_fallback", END)
    return graph.compile()


async def _run_website_research_graph(
    naam: str, adres: str | None, website_url: str | None, gemeente: str | None
) -> AgentFinding | None:
    graph = _build_website_research_graph()
    result = await graph.ainvoke({
        "naam": naam,
        "adres": adres,
        "website_url": website_url,
        "gemeente": gemeente,
        "best": None,
    })
    return result.get("best")


class LiveWebsiteAgent:
    async def run(self, naam: str, adres: str | None, website_url: str | None,
                  gemeente: str | None = None) -> AgentFinding | None:
        return await _run_website_research_graph(naam, adres, website_url, gemeente)

    async def extra_bronnen(self, naam: str, gemeente: str | None,
                            uitsluiten: set[str] | None = None) -> list[AgentFinding]:
        return await wp_extractie.verzamel_extra_media_bronnen(naam, gemeente, uitsluiten)
