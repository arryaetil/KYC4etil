"""Vastleggen wie wat deed, buiten de bronbeslissingen om.

Eén plek, zodat elke aanroep dezelfde vorm heeft en er niet per router een
eigen variant ontstaat. Loggen mag nooit de handeling zelf laten mislukken: een
lijst die is geüpload blijft geüpload, ook als het schrijven van de regel
misgaat.
"""
import logging

from sqlalchemy.orm import Session

from .models import Handeling, User

logger = logging.getLogger(__name__)

# De soorten die we vastleggen. Een vaste lijst en geen vrije tekst: zo blijft
# terugzoeken mogelijk, en valt meteen op als iemand een nieuwe handeling
# toevoegt zonder erover na te denken.
LIJST_GEUPLOAD = "lijst_geupload"
LIJST_VERWIJDERD = "lijst_verwijderd"
LIJST_HERSTELD = "lijst_hersteld"
ORGANISATIE_TOEGEVOEGD = "organisatie_toegevoegd"
GEBRUIKER_AANGEMAAKT = "gebruiker_aangemaakt"
GEBRUIKER_VERWIJDERD = "gebruiker_verwijderd"
WACHTWOORD_GEWIJZIGD = "wachtwoord_gewijzigd"
ONDERZOEK_GESTART = "onderzoek_gestart"
MONITORING_GESTART = "monitoring_gestart"


def leg_vast(
    db: Session,
    soort: str,
    omschrijving: str,
    door: User | None = None,
    onderwerp_id: str | None = None,
) -> None:
    """Schrijf één regel. Faalt stil, met een logregel.

    Niet committen: de aanroeper doet dat samen met zijn eigen wijziging, zodat
    er geen regel achterblijft over iets wat uiteindelijk niet is gebeurd.
    """
    try:
        db.add(Handeling(
            soort=soort,
            omschrijving=omschrijving,
            door_id=door.id if door else None,
            door_naam=door.naam if door else None,
            onderwerp_id=onderwerp_id,
        ))
    except Exception as exc:
        logger.warning("handeling niet vastgelegd (%s): %s", soort, exc)
