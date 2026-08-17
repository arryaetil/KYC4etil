"""End-to-end rookproef door een echte browser.

Waarom dit bestaat: een groene testsuite en een geslaagde build zeggen niets
over of de interface het dóet. De mappenlaag werd in augustus 2026 gedeployd
met 463 groene backendtests en 93 groene frontendtests, terwijl niemand er ooit
op had geklikt. Dit script sluit dat gat: het logt in, klikt de kritieke paden
door en maakt screenshots die je zelf kunt bekijken.

Gebruik:

    UI_CHECK_URL=http://localhost:5173 \\
    UI_CHECK_EMAIL=admin@etil.nl \\
    UI_CHECK_PASSWORD=... \\
    python -m scripts.ui_check

Tegen productie draaien mag ook — het script maakt alleen een eigen wegwerpmap
aan en ruimt die daarna op, ook als er onderweg iets misgaat:

    UI_CHECK_URL=https://frontend-production-3080.up.railway.app ...

Het wachtwoord staat in de Railway-omgeving van de backendservice
(`railway variables -s backend --kv | grep DEMO_ADMIN_PASSWORD`). Zet het nooit
in de repository.

Exitcode 0 als alles klopt, 1 bij de eerste mislukte controle. Screenshots
komen in `scripts/ui_check_output/`.
"""
import os
import sys
from pathlib import Path

# Naam met een prefix die achteraan sorteert en herkenbaar is als afval, zodat
# een half afgebroken run niet tussen echte mappen verdwijnt.
TESTMAP = "ZZ ui-check wegwerpmap"
UITVOER = Path(__file__).resolve().parent / "ui_check_output"


class Controle:
    """Verzamelt bevindingen zodat één misser de rest niet blokkeert."""

    def __init__(self) -> None:
        self.regels: list[tuple[bool, str]] = []

    def meld(self, ok: bool, tekst: str) -> bool:
        self.regels.append((bool(ok), tekst))
        print(f"  {'OK  ' if ok else 'FOUT'}  {tekst}", flush=True)
        return bool(ok)

    def overgeslagen(self, tekst: str) -> None:
        print(f"  --    {tekst} (overgeslagen)", flush=True)

    @property
    def mislukt(self) -> list[str]:
        return [tekst for ok, tekst in self.regels if not ok]


def _login(page, url: str, email: str, wachtwoord: str, c: Controle) -> None:
    page.goto(url)
    page.fill("#email", email)
    page.fill("#password", wachtwoord)
    page.click('button:has-text("Inloggen")')
    page.wait_for_selector("text=Onderzoek", timeout=30000)
    c.meld(True, f"ingelogd als {email}")


def _ruim_op(page, c: Controle) -> None:
    """Verwijder een achtergebleven wegwerpmap.

    Draait ook na een mislukking, zodat een afgebroken run geen rommel in het
    overzicht van de reviewer achterlaat.
    """
    try:
        page.goto(page.url.split("#")[0])
        page.wait_for_timeout(1500)
        for archief in (False, True):
            if archief:
                if not page.is_visible("text=Archief bekijken"):
                    continue
                page.click("text=Archief bekijken")
                page.wait_for_timeout(1200)
            if not page.is_visible(f"text={TESTMAP}"):
                continue
            page.locator(f'button[aria-label="Acties voor \\"{TESTMAP}\\""]').click()
            page.wait_for_timeout(300)
            page.click('[role="menuitem"]:has-text("Verwijderen")')
            page.wait_for_selector('[role="dialog"]')
            page.click('button:has-text("Verwijderen")')
            page.wait_for_timeout(1200)
            c.meld(not page.is_visible(f"text={TESTMAP}"), "wegwerpmap opgeruimd")
    except Exception as exc:  # pragma: no cover - alleen opruimhulp
        print(f"  !     opruimen mislukt ({type(exc).__name__}); "
              f'verwijder "{TESTMAP}" zo nodig handmatig', flush=True)


def _controleer_mappen(page, c: Controle) -> None:
    print("\n== mappenpagina ==")
    page.wait_for_timeout(1500)
    page.screenshot(path=str(UITVOER / "01-mappen.png"))
    c.meld(page.is_visible("text=Nieuwe map"), 'knop "Nieuwe map" zichtbaar')

    menu = page.locator('button[aria-label^="Acties voor"]').first
    if menu.count() == 0:
        c.overgeslagen("actiemenu: nog geen mappen aanwezig")
    else:
        # Zonder hover: acties die pas bij hover verschijnen zijn op touch
        # onvindbaar én blijven klikbaar. Dat was een echte fout.
        c.meld(menu.is_visible(), "actiemenu zichtbaar zonder hover")
        menu.click()
        page.wait_for_timeout(400)
        page.screenshot(path=str(UITVOER / "02-menu.png"))
        for actie in ("Hernoemen", "Archiveren", "Verwijderen"):
            c.meld(
                page.is_visible(f'[role="menuitem"]:has-text("{actie}")'),
                f'menu-item "{actie}"',
            )
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        c.meld(not page.is_visible('[role="menu"]'), "Escape sluit het menu")


def _controleer_levenscyclus(page, c: Controle) -> None:
    print("\n== map aanmaken, archiveren, terugzetten ==")
    page.click("text=Nieuwe map")
    page.wait_for_selector('[role="dialog"]')
    page.fill("#mapnaam", TESTMAP)
    page.click('button:has-text("Map aanmaken")')
    page.wait_for_timeout(1500)
    if not c.meld(page.is_visible(f"text={TESTMAP}"), "nieuwe map verschijnt"):
        return

    knop = f'button[aria-label="Acties voor \\"{TESTMAP}\\""]'
    page.locator(knop).click()
    page.wait_for_timeout(300)
    page.click('[role="menuitem"]:has-text("Archiveren")')
    page.wait_for_selector('[role="dialog"]')
    page.screenshot(path=str(UITVOER / "03-archiveren.png"))
    c.meld(
        page.is_visible("text=herstelt") or page.is_visible("text=herstellen"),
        "archiveerdialoog legt uit dat herstellen kan",
    )
    page.click('button:has-text("Archiveren")')
    page.wait_for_timeout(1500)
    c.meld(not page.is_visible(f"text={TESTMAP}"), "map weg uit het overzicht")
    c.meld(page.is_visible("text=Archief bekijken"), "archiefknop verschenen")

    page.click("text=Archief bekijken")
    page.wait_for_timeout(1200)
    page.screenshot(path=str(UITVOER / "04-archief.png"))
    c.meld(page.is_visible(f"text={TESTMAP}"), "map staat in het archief")
    page.locator(knop).click()
    page.wait_for_timeout(300)
    c.meld(
        page.is_visible('[role="menuitem"]:has-text("Terugzetten")'),
        'archief biedt "Terugzetten"',
    )
    c.meld(
        not page.is_visible('[role="menuitem"]:has-text("Hernoemen")'),
        "geen hernoemen in het archief",
    )
    page.click('[role="menuitem"]:has-text("Terugzetten")')
    page.wait_for_timeout(1500)
    page.click("text=Alle mappen")
    page.wait_for_timeout(1200)
    c.meld(page.is_visible(f"text={TESTMAP}"), "map is teruggezet")


def _controleer_lijsten(page, c: Controle) -> None:
    print("\n== lijsten en organisaties ==")
    mappen = page.locator('button[aria-label^="Acties voor"]')
    if mappen.count() == 0:
        return c.overgeslagen("geen map om te openen")

    # De wegwerpmap is leeg; open een map die lijsten bevat.
    tegels = page.locator("li:has(button[aria-label^='Acties voor'])")
    for index in range(tegels.count()):
        tegel = tegels.nth(index)
        if TESTMAP in (tegel.inner_text() or ""):
            continue
        if "Nog geen lijsten" in (tegel.inner_text() or ""):
            continue
        tegel.locator("button").first.click()
        break
    else:
        return c.overgeslagen("geen gevulde map aanwezig")

    page.wait_for_timeout(2000)
    page.screenshot(path=str(UITVOER / "05-lijsten.png"))
    c.meld(page.is_visible("text=Alle mappen"), "terugknop naar mappen")
    c.meld(page.is_visible("text=Lijst uploaden"), "uploaden kan in een map")

    lijst = page.locator("li button.focus-ring").first
    if lijst.count() == 0:
        return c.overgeslagen("map bevat geen lijsten")
    lijst.click()
    page.wait_for_timeout(2500)
    page.screenshot(path=str(UITVOER / "06-organisaties.png"))
    c.meld(page.is_visible("text=Alle lijsten"), "terugknop naar lijsten")
    page.click("text=Alle lijsten")
    page.wait_for_timeout(1200)
    page.click("text=Alle mappen")
    page.wait_for_timeout(1200)


def _controleer_monitoring(page, c: Controle) -> None:
    print("\n== monitoring ==")
    if not page.is_visible("text=Jaarverslagenmonitoring"):
        return c.overgeslagen("monitoringtab niet zichtbaar")
    page.click("text=Jaarverslagenmonitoring")
    page.wait_for_timeout(2500)
    page.screenshot(path=str(UITVOER / "07-monitoring.png"))
    # Alleen dat de module laadt; de inhoud hangt van de data af.
    c.meld(
        not page.is_visible("text=Application error"),
        "monitoringmodule laadt zonder fout",
    )
    # De indeling op verslagjaar is de kernvraag van deze module; zonder een
    # eigen assertie zou een lege of stukgelopen kopregel groen blijven.
    c.meld(
        page.is_visible("text=/met verslag \\d{4}/"),
        "kopregel noemt hoeveel organisaties het verslag over het doeljaar hebben",
    )
    c.meld(
        page.is_visible("text=/\\d+ ouder/")
        and page.is_visible("text=/\\d+ ontbreekt/"),
        "kopregel splitst verouderd en ontbrekend uit",
    )
    filter_opties = page.locator(
        "select[aria-label='Filter op status'] option",
    ).all_inner_texts()
    c.meld(
        any(tekst.startswith("Verslag ") for tekst in filter_opties)
        and "Alleen een ouder verslag" in filter_opties,
        "statusfilter biedt de jaarbuckets aan",
    )
    c.meld(
        "Nieuwe vondst" not in filter_opties,
        "de oude delta-status staat niet meer als hoofdfilter",
    )
    page.click("text=Onderzoek")
    page.wait_for_timeout(1500)


def main() -> int:
    url = os.environ.get("UI_CHECK_URL", "http://localhost:5173").rstrip("/")
    email = os.environ.get("UI_CHECK_EMAIL", "admin@etil.nl")
    wachtwoord = os.environ.get("UI_CHECK_PASSWORD")
    if not wachtwoord:
        print(
            "UI_CHECK_PASSWORD ontbreekt.\n"
            "  Haal het op met: railway variables -s backend --kv "
            "| grep DEMO_ADMIN_PASSWORD",
        )
        return 2

    from playwright.sync_api import sync_playwright

    UITVOER.mkdir(exist_ok=True)
    c = Controle()
    print(f"== rookproef tegen {url} ==")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(20000)
        try:
            _login(page, url, email, wachtwoord, c)
            _controleer_mappen(page, c)
            _controleer_levenscyclus(page, c)
            _controleer_lijsten(page, c)
            _controleer_monitoring(page, c)
        except Exception as exc:
            c.meld(False, f"{type(exc).__name__}: {str(exc)[:160]}")
            page.screenshot(path=str(UITVOER / "99-fout.png"))
        finally:
            _ruim_op(page, c)
            browser.close()

    geslaagd = len(c.regels) - len(c.mislukt)
    print(f"\n{geslaagd}/{len(c.regels)} controles OK")
    print(f"screenshots: {UITVOER}")
    if c.mislukt:
        print("\nMISLUKT:")
        for tekst in c.mislukt:
            print(f"  - {tekst}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
