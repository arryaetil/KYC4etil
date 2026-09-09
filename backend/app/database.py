from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import get_settings

settings = get_settings()
database_url = settings.effective_database_url
engine_options = {
    "connect_args": (
        {"check_same_thread": False}
        if database_url.startswith("sqlite")
        else {}
    ),
}
if not database_url.startswith("sqlite"):
    # Houd de API responsief tijdens langlopende research. Een korte timeout
    # voorkomt dat honderden webrequests elk 30 seconden op een volle pool
    # blijven wachten; pre-ping ruimt verbroken Railway-connecties op.
    engine_options.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 5,
        "pool_pre_ping": True,
        "pool_recycle": 300,
    })

engine = create_engine(database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


DEMOMAP_NAAM = "Demo runs"


def _vul_demomap(conn) -> None:
    """Zet elke bestaande lijst in één map, zodat er niets verdwijnt.

    De mappenlaag is later toegevoegd dan de lijsten. Zonder deze stap zou de
    nieuwe pagina leeg openen terwijl er tientallen batches in de database
    staan — die zouden dan alleen nog via een directe URL bereikbaar zijn.
    De monitoringlijst blijft er bewust buiten: die heeft een eigen module.
    """
    import uuid as _uuid_mod
    from datetime import datetime, timezone

    map_id = str(_uuid_mod.uuid4())
    conn.execute(
        text(
            "INSERT INTO mappen (id, naam, created_at) "
            "VALUES (:id, :naam, :created_at)"
        ),
        {
            "id": map_id,
            "naam": DEMOMAP_NAAM,
            "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
        },
    )
    conn.execute(
        text(
            "UPDATE batches SET map_id = :map_id "
            "WHERE map_id IS NULL "
            "AND (is_monitoringlijst IS NULL OR is_monitoringlijst = FALSE)"
        ),
        {"map_id": map_id},
    )


def _add_column_if_missing(conn, table: str, name: str, ddl_type: str) -> bool:
    """Voeg één kolom toe. Geeft terug of dat daadwerkelijk gebeurd is.

    Twee processen kunnen tegelijk opstarten en dezelfde kolom willen
    toevoegen; dan is "bestaat al" de gewenste uitkomst en geen fout.
    """
    try:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}"))
        return True
    except (OperationalError, ProgrammingError) as exc:
        message = str(exc).lower()
        if "duplicate column" in message or "already exists" in message:
            return False
        raise


def _scalaire_standaardwaarde(kolom):
    """De vaste waarde die het model aan deze kolom geeft, of None.

    Alleen een échte constante (`default=False`, `default=0`). Een callable
    zoals `_now` of `_uuid` hoort niet met terugwerkende kracht over bestaande
    rijen te worden uitgesmeerd — dat zou een tijdstip verzinnen.
    """
    standaard = kolom.default
    if standaard is None or not getattr(standaard, "is_scalar", False):
        return None
    return standaard.arg


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_lightweight_migrations() -> None:
    """Breng de database bij met wat er in `models.py` staat.

    Dit stond hier als honderdtwintig regels `ALTER TABLE`, één per kolom, met
    de hand bijgehouden. Dat werkt zolang niemand het vergeet, en precies dat
    is het probleem: een veld toevoegen aan een model deed lokaal niets (daar
    maakt `create_all` de tabel opnieuw) en brak pas op Railway, waar de tabel
    al bestond. De lijst was dus een tweede beschrijving van hetzelfde schema,
    die stilzwijgend uit de pas kon lopen met de eerste.

    Nu wordt het verschil afgeleid: elke kolom die het model kent en de
    database niet, wordt toegevoegd. Alleen toevoegen — nooit wijzigen, nooit
    weggooien. Een kolom die verdwijnt uit een model blijft dus in de database
    staan, en dat hoort ook: die keuze is niet aan een opstartroutine.

    Wat hieronder wél met de hand staat, is het eenmalige werk dat geen enkele
    schemavergelijking kan bedenken: bestaande rijen ergens in zetten.
    """
    inspector = inspect(engine)
    tabellen = set(inspector.get_table_names())
    if "companies" not in tabellen:
        return

    toegevoegd: set[tuple[str, str]] = set()
    with engine.begin() as conn:
        for tabel in Base.metadata.sorted_tables:
            if tabel.name not in tabellen:
                continue  # nieuwe tabellen komen uit create_all
            bestaand = {kolom["name"] for kolom in inspector.get_columns(tabel.name)}
            for kolom in tabel.columns:
                if kolom.name in bestaand:
                    continue
                ddl_type = kolom.type.compile(dialect=engine.dialect)
                if not _add_column_if_missing(
                    conn, tabel.name, kolom.name, ddl_type,
                ):
                    continue
                toegevoegd.add((tabel.name, kolom.name))
                # Een nieuwe kolom is leeg, terwijl het model een vaste waarde
                # belooft. `afgewerkt` en `is_monitoringlijst` kwamen daardoor
                # als NULL terug in plaats van False.
                standaard = _scalaire_standaardwaarde(kolom)
                if standaard is not None:
                    conn.execute(
                        text(
                            f"UPDATE {tabel.name} SET {kolom.name} = :waarde "
                            f"WHERE {kolom.name} IS NULL"
                        ),
                        {"waarde": standaard},
                    )

        # Indexen horen bij de kolom, niet bij een aparte lijst. `create_all`
        # maakt ze alleen mee bij een nieuwe tabel; op een bestaande tabel
        # moeten ze los.
        for tabel in Base.metadata.sorted_tables:
            if tabel.name not in tabellen:
                continue
            for index in tabel.indexes:
                index.create(bind=conn, checkfirst=True)

    # Eenmalig, en alleen op het moment dat de kolom ontstaat.
    if ("batches", "created_at") in toegevoegd:
        # Geen verzonnen datum per rij, maar één moment: vanaf nu bekend.
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE batches SET created_at = CURRENT_TIMESTAMP "
                "WHERE created_at IS NULL"
            ))
    if ("batches", "map_id") in toegevoegd:
        # Alles wat er al stond bij elkaar in één map, zodat de mappenpagina
        # niet leeg opent en geen enkele bestaande lijst buiten beeld raakt.
        # Daarna bepaalt de gebruiker zelf waar een lijst hoort.
        with engine.begin() as conn:
            _vul_demomap(conn)
