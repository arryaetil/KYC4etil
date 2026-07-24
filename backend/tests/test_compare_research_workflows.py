import pytest

from scripts.compare_research_workflows import vergelijk


@pytest.mark.asyncio
async def test_mockresearch_scheidt_bruikbare_wp_van_brede_context():
    resultaat = await vergelijk()

    assert resultaat["aantal"] == 20
    assert resultaat["coverage"] == 0.85
    assert resultaat["exact_match"] == 0.85
    assert {rij["naam"] for rij in resultaat["afwijkend"]} == {
        "NS Groep",
        "DSM-Firmenich",
        "Koninklijke BAM Groep N.V.",
    }
    assert all(rij["research_wp"] is None for rij in resultaat["afwijkend"])
    assert all(rij["research_wp_raw"] is not None for rij in resultaat["afwijkend"])
    assert all(rij["scope"] == "nederland" for rij in resultaat["afwijkend"])
