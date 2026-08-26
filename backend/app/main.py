import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .database import Base, SessionLocal, engine, ensure_lightweight_migrations
from .models import Batch, PipelineRun
from .routers import auth, batches, monitoring, research, mappen
from .scheduler import start_scheduler

settings = get_settings()

Base.metadata.create_all(bind=engine)
ensure_lightweight_migrations()

app = FastAPI(title="KYC4etil Bronnenwerkbank", version="0.2.0",
              description="Werkbank voor brononderzoek en menselijke bronbeoordeling")


@app.middleware("http")
async def vertaal_onverwachte_fouten(request, call_next):
    """Een fout die niemand had voorzien moet nog steeds een antwoord zijn.

    Zonder dit handelt Starlette hem af buiten de CORS-laag om: de browser
    krijgt een reactie zonder CORS-headers en meldt "Failed to fetch". Dat leest
    als een netwerkstoring terwijl de server gewoon antwoordde, en het verbergt
    wát er misging — de traceback stond alleen in de serverlog.
    """
    try:
        return await call_next(request)
    except Exception:
        logging.getLogger("api").exception(
            "onverwachte fout bij %s %s", request.method, request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Er ging iets mis bij deze actie. "
                               "De fout is vastgelegd."},
        )


# Na de foutvertaler toegevoegd, en daarmee eromheen: anders mist het
# 500-antwoord zijn CORS-headers en is het in de browser onleesbaar.
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                   allow_headers=["*"], expose_headers=["Content-Disposition"])

app.include_router(auth.router)
app.include_router(batches.router)
app.include_router(mappen.router)
app.include_router(monitoring.router)
app.include_router(research.router)
app.include_router(research.bron_router)


@app.on_event("startup")
def reset_stuck_batches() -> None:
    """Zet batches die tijdens een service-herstart liepen terug naar 'error'."""
    import logging
    _log = logging.getLogger("startup")
    if settings.jwt_secret == "change-me":
        _log.critical(
            "BEVEILIGINGSWAARSCHUWING: JWT_SECRET staat op de standaardwaarde 'change-me'. "
            "Stel JWT_SECRET in als omgevingsvariabele voor productie."
        )
    if settings.email_demo_recipient:
        _log.warning(
            "email_demo_recipient is ingesteld op '%s'. "
            "Alle chat-uitnodigingen gaan naar dit adres i.p.v. het bedrijf. "
            "Leeghalen voor productie via EMAIL_DEMO_RECIPIENT=",
            settings.email_demo_recipient,
        )
    db = SessionLocal()
    try:
        stuck = db.query(Batch).filter_by(status="running").all()
        for batch in stuck:
            batch.status = "error"
            db.add(PipelineRun(batch_id=batch.id, stap="startup_recovery",
                               status="error", duur_ms=0,
                               error="Batch onderbroken door service-herstart"))
        if stuck:
            db.commit()

    except Exception as exc:
        import logging
        logging.getLogger("startup").error("Startup event fout: %s", exc)
    finally:
        db.close()


@app.on_event("startup")
def start_jaarverslag_scheduler() -> None:
    start_scheduler()


@app.on_event("shutdown")
async def sluit_gedeelde_browser() -> None:
    """Crawl4AI houdt één browser open voor de hele proceslevensduur; zonder
    dit blijft Chromium achter bij een herstart van de service."""
    from .providers.fetch import sluit_crawler

    await sluit_crawler()


@app.get("/health")
def health():
    return {"status": "ok", "provider_mode": settings.provider_mode}
