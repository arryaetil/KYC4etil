"""De actie op een bronkaart volgt de twijfel, niet het brontype."""
from app.research.ranking import _menselijke_waarde
from app.research.validation import SourceDocument, valideer_bron


def _bron(**velden):
    document = SourceDocument(
        naam="Voorbeeld Zorg",
        company_website_url="https://voorbeeldzorg.nl",
        url=velden.pop("url", "https://voorbeeldzorg.nl/over-ons/team"),
        titel=velden.pop("titel", "Ons team"),
        tekst="Voorbeeld Zorg — ons team",
        brontype=velden.pop("brontype", "officiele_website"),
        gevraagd_jaar=2025,
        **velden,
    )
    return valideer_bron(document)


def _actie(**velden) -> str:
    return _menselijke_waarde(_bron(**velden))["actie"]


def test_een_concerncijfer_stuurt_naar_de_uitsplitsing():
    """"Controleer het citaat en de scope" zei niet wát er mis kan zijn."""
    actie = _actie(
        documenttype="jaarverslag", wp_gevonden=4900,
        eenheid="werkzame_personen", bewijsfragment="4.900 medewerkers",
        scope_class="concern", verslagjaar=2025,
    )
    assert "4900 geldt breder dan deze vestiging" in actie
    assert "uitsplitsing" in actie


def test_een_fte_getal_stuurt_naar_het_aantal_personen():
    actie = _actie(
        documenttype="jaarverslag", wp_gevonden=312, eenheid="fte",
        bewijsfragment="312 fte", scope_class="vestiging", verslagjaar=2025,
    )
    assert "FTE-getal en geen WP" in actie


def test_een_getal_zonder_citaat_stuurt_naar_de_passage():
    actie = _actie(
        documenttype="teampagina", wp_gevonden=47,
        eenheid="werkzame_personen", scope_class="vestiging",
    )
    assert "geen zin vastgelegd waar dat staat" in actie


def test_de_eenheid_gaat_voor_op_het_ontbrekende_citaat():
    """Twee opdrachten tegelijk is geen opdracht: alleen de eerste twijfel telt.

    Een FTE-getal is onbruikbaar hoe goed het ook onderbouwd is, dus dat moet de
    reviewer als eerste weten.
    """
    actie = _actie(
        documenttype="jaarverslag", wp_gevonden=312, eenheid="fte",
        scope_class="concern", verslagjaar=2025,
    )
    assert "FTE-getal" in actie
    assert "uitsplitsing" not in actie


def test_teampagina_zonder_getal_waarschuwt_voor_een_deellijst():
    """"Tel de genoemde teamleden" is bij een concern werk dat niets oplevert."""
    actie = _actie(documenttype="teampagina")
    assert "alleen als deze pagina het volledige personeel toont" in actie


def test_een_deugdelijk_vestigingscijfer_houdt_de_gewone_actie():
    actie = _actie(
        documenttype="jaarverslag", wp_gevonden=47,
        eenheid="werkzame_personen", bewijsfragment="47 medewerkers",
        scope_class="vestiging", verslagjaar=2025,
        url="https://voorbeeldzorg.nl/jaarverslag-2025.pdf",
        titel="Jaarverslag 2025 Voorbeeld Zorg",
    )
    assert "Controleer het citaat en de scope" in actie
