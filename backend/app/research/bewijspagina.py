"""Render een interne 'leesweergave' van een webbron met het bewijsfragment
gemarkeerd, zodat de reviewer een website kan bekijken zonder de werkbank te
verlaten — vergelijkbaar met de bestaande PDF-modal.

We serveren bewust geen kopie van de originele HTML/CSS/JS. Twee redenen:

1. Browsers passen de `#:~:text=`-tekstfragment-highlight niet toe binnen een
   iframe (een bewuste Chromium-restrictie, ongeacht origin), dus die route
   werkt hier sowieso niet.
2. Alle tekst hier komt geëscaped in de pagina terecht en er wordt geen
   externe `<script>`/`<style>` doorgegeven — dat maakt deze pagina veilig om
   same-origin in te sluiten, ook al komt de brontekst van een niet-vertrouwde
   externe site.

De hoogte van het bewijsfragment binnen de pagina wordt niet met JavaScript
bepaald maar met een simpele ankerlink (`#citaat`): de browser scrollt daar
vanzelf naartoe, zonder dat er een script hoeft te draaien.
"""
from html import escape


def _vind_citaat_paragraaf(paragrafen: list[str], citaat: str) -> int | None:
    """Zoekt de paragraaf die het bewijsfragment bevat.

    Vergelijkt met genormaliseerde witruimte, want de geëxtraheerde tekst kan
    net iets anders zijn opgemaakt dan de brontekst (regeleindes, dubbele
    spaties). Bij geen exacte match wordt de eerste 40 tekens als anker
    geprobeerd — kort genoeg om robuust te zijn tegen kleine afwijkingen aan
    het einde van het citaat.
    """
    normaliseer = lambda tekst: " ".join(tekst.split()).lower()
    citaat_norm = normaliseer(citaat)
    if not citaat_norm:
        return None

    for index, paragraaf in enumerate(paragrafen):
        if citaat_norm in normaliseer(paragraaf):
            return index

    anker = citaat_norm[:40]
    if len(anker) < 10:
        return None
    for index, paragraaf in enumerate(paragrafen):
        if anker in normaliseer(paragraaf):
            return index
    return None


def _markeer_citaat(paragraaf: str, citaat: str) -> str:
    """Wikkelt het (genormaliseerd) gevonden citaat in `<mark id="citaat">`."""
    genormaliseerd_paragraaf = " ".join(paragraaf.split())
    citaat_norm = " ".join(citaat.split())

    laag = genormaliseerd_paragraaf.lower()
    start = laag.find(citaat_norm.lower())
    if start == -1:
        anker = citaat_norm[:40].lower()
        start = laag.find(anker) if len(anker) >= 10 else -1
        lengte = len(anker)
    else:
        lengte = len(citaat_norm)

    if start == -1:
        return escape(genormaliseerd_paragraaf)

    voor = genormaliseerd_paragraaf[:start]
    match = genormaliseerd_paragraaf[start:start + lengte]
    na = genormaliseerd_paragraaf[start + lengte:]
    return (
        f"{escape(voor)}"
        f'<mark id="citaat">{escape(match)}</mark>'
        f"{escape(na)}"
    )


_PAGINA_TEMPLATE = """<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<title>{titel}</title>
<style>
  body {{
    margin: 0; padding: 0 0 3rem;
    font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    color: #1f2430; background: #fff;
  }}
  header {{
    position: sticky; top: 0; display: flex; align-items: baseline;
    justify-content: space-between; gap: 1rem;
    padding: 0.75rem 1.25rem; border-bottom: 1px solid #e2e4e9;
    background: #fafafa;
  }}
  header .titel {{ font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  header a {{ color: #1f2430; white-space: nowrap; font-size: 0.85em; }}
  main {{ max-width: 68ch; margin: 1.5rem auto; padding: 0 1.25rem; }}
  p {{ margin: 0 0 1.1em; }}
  mark {{ background: #fde68a; padding: 0.05em 0.15em; scroll-margin-top: 4rem; }}
  .toelichting {{ color: #6b7280; font-style: italic; }}
</style>
</head>
<body>
<header>
  <span class="titel">{titel}</span>
  <a href="{bron_url}" target="_blank" rel="noreferrer noopener">Origineel openen ↗</a>
</header>
<main>
{inhoud}
</main>
</body>
</html>"""


def render_bewijspagina(*, url: str, titel: str, tekst: str, citaat: str | None) -> str:
    """Bouwt de leesweergave-HTML. Puur (geen I/O), dus makkelijk te testen.

    Regels van 2 tekens of minder (taalwisselaars als "nl"/"en") worden
    genegeerd: dat is vrijwel altijd navigatie-ruis, nooit een bewijszin. Een
    JS-zware site zonder echte hoofdtekst (bv. alleen knoppen als "Bekijk")
    blijft daarna nog steeds schraal — dat is geen weergavefout, maar precies
    wat de extractor zag; zie research/urls.py en de Aviko-observatie in
    docs/OPENSTAANDE_OBSERVATIES_RESEARCH_EN_UI.md §4.
    """
    paragrafen = [regel for regel in tekst.split("\n") if len(regel.strip()) > 2]

    if not paragrafen:
        inhoud = (
            '<p class="toelichting">Deze pagina leverde geen leesbare '
            "hoofdtekst op. Bekijk de bron rechtstreeks via de link "
            "hierboven.</p>"
        )
    else:
        citaat_index = _vind_citaat_paragraaf(paragrafen, citaat) if citaat else None
        delen = []
        for index, paragraaf in enumerate(paragrafen):
            if index == citaat_index:
                delen.append(f"<p>{_markeer_citaat(paragraaf, citaat)}</p>")
            else:
                delen.append(f"<p>{escape(paragraaf)}</p>")
        inhoud = "\n".join(delen)
        if citaat and citaat_index is None:
            inhoud = (
                '<p class="toelichting">Het opgeslagen citaat is niet '
                "letterlijk teruggevonden in deze weergave — mogelijk is de "
                "pagina gewijzigd. Bekijk de bron rechtstreeks via de link "
                "hierboven.</p>\n" + inhoud
            )

    html_document = _PAGINA_TEMPLATE.format(
        titel=escape(titel or url), bron_url=escape(url), inhoud=inhoud,
    )
    return html_document
